"""Flask entrypoint for the Office Hours Scheduler.

Exposes the JSON API used by the React SPA (``POST /api/optimize`` and
``GET /api/share/<token>``) and serves the prebuilt SPA shell from
``frontend/dist/``. All request validation lives in this module; the heavy
lifting (parsing + GA-based optimization) is delegated to ``optimize``.

Share tokens are stateless: the result dict is gzip-compressed and
URL-safe-base64-encoded, so existing ``/r/<token>`` links survive deploys
without any server-side store.
"""

from __future__ import annotations

import base64
import gzip
import json
from pathlib import Path
from typing import Any

from flask import Flask, abort, jsonify, request, send_from_directory

from optimize import (
    _normalize_day,
    optimize_from_records,
    optimize_from_records_v2,
    parse_manual_students,
    parse_manual_students_v2,
    parse_manual_teachers,
    parse_manual_teachers_v2,
    parse_student_csv_text,
    parse_student_csv_text_v2,
    parse_teacher_csv_text,
    parse_teacher_csv_text_v2,
)

ROOT_DIR = Path(__file__).resolve().parent
FRONTEND_DIST = ROOT_DIR / "frontend" / "dist"

app = Flask(__name__, static_folder=None)

# 5 MB cap on a single request so a malicious upload can't exhaust memory.
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

DEFAULT_SLOT_MINUTES = 30
DEFAULT_DAY_START_HOUR = 8
DEFAULT_DAY_END_HOUR = 20
SUPPORTED_SLOT_MINUTES = (15, 30, 60)


# ---------------------------------------------------------------------------
# Share tokens (kept identical to the legacy format so existing /r/<token>
# links keep working).
# ---------------------------------------------------------------------------


def _encode_share_token(payload: dict[str, Any]) -> str:
    """Serialize a result dict into a stateless, URL-safe share token.

    The token is gzip-compressed JSON, base64-encoded with ``=`` padding
    stripped so it can sit in a URL path segment unescaped.
    """
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    compressed = gzip.compress(raw, compresslevel=9)
    return base64.urlsafe_b64encode(compressed).decode("ascii").rstrip("=")


def _decode_share_token(token: str) -> dict[str, Any]:
    """Inverse of :func:`_encode_share_token`.

    Raises ``ValueError`` on any decode failure (bad base64, bad gzip, bad
    JSON) so the route can return a single 404 regardless of the cause.
    """
    pad = "=" * ((4 - len(token) % 4) % 4)
    try:
        compressed = base64.urlsafe_b64decode(token + pad)
        raw = gzip.decompress(compressed)
        return json.loads(raw.decode("utf-8"))
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid share token.") from exc


# ---------------------------------------------------------------------------
# Optimize pipeline
# ---------------------------------------------------------------------------


def _coerce_int(value: Any, default: int, *, minimum: int, maximum: int, label: str) -> int:
    """Coerce a JSON value to a bounded integer or raise ``ValueError``.

    Empty/missing values fall back to ``default``. ``label`` is embedded in
    the error message so the route surfaces a useful 400 to the SPA.
    """
    if value is None or value == "":
        return default
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be an integer.") from exc
    if result < minimum or result > maximum:
        raise ValueError(f"{label} must be between {minimum} and {maximum}.")
    return result


def _resolve_slot_minutes(value: Any) -> int:
    """Validate the slot-granularity setting against ``SUPPORTED_SLOT_MINUTES``."""
    if value is None or value == "":
        return DEFAULT_SLOT_MINUTES
    try:
        slot_minutes = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Slot length must be an integer.") from exc
    if slot_minutes not in SUPPORTED_SLOT_MINUTES:
        raise ValueError(
            "Slot length must be one of: " + ", ".join(str(m) for m in SUPPORTED_SLOT_MINUTES)
        )
    return slot_minutes


def _v2_rows_from_payload(
    payload: dict[str, Any],
    *,
    parse_csv,
    parse_manual,
) -> list[tuple]:
    """Resolve a request-side payload into v2 rows.

    The payload accepts any of:
      * ``rows_v2``: a list of [id, day, start, end, strength] tuples (preferred,
        what the SPA sends).
      * ``csv_text``: raw CSV text (uploaded files are read client-side and posted
        as text so the API stays JSON-only).
    """
    if not isinstance(payload, dict):
        return []

    rows = payload.get("rows_v2")
    if rows:
        return _normalize_rows(rows)

    csv_text = payload.get("csv_text") or ""
    if csv_text.strip():
        return parse_csv(csv_text)

    manual_text = payload.get("manual_text") or ""
    if manual_text.strip():
        return parse_manual(manual_text)

    return []


def _normalize_rows(rows: Any) -> list[tuple]:
    """Validate and convert a JSON list-of-lists into clean tuples.

    Raises ``ValueError`` (which the route turns into HTTP 400) for any
    structural problem: non-list input, wrong field count, non-integer slot
    indices, unsupported day, blank id, start>=end, or invalid strength.
    """
    if not isinstance(rows, list):
        raise ValueError("rows_v2 must be a list.")
    out: list[tuple] = []
    for raw in rows:
        if not isinstance(raw, (list, tuple)):
            raise ValueError("Each row must be a list of fields.")
        if len(raw) < 4 or len(raw) > 5:
            raise ValueError("Each row must have 4 or 5 fields (id, day, start, end[, strength]).")
        entity_id = str(raw[0]).strip()
        if not entity_id:
            raise ValueError("Row is missing an id.")
        day = _normalize_day(str(raw[1]))  # raises ValueError on unsupported day
        try:
            start = int(raw[2])
            end = int(raw[3])
        except (TypeError, ValueError) as exc:
            raise ValueError("start/end slot indices must be integers.") from exc
        if start < 0 or end < 0:
            raise ValueError("start/end slot indices must be non-negative.")
        if start >= end:
            raise ValueError(f"Row for '{entity_id}' has start_slot >= end_slot.")
        strength = "hard"
        if len(raw) == 5 and raw[4]:
            strength = str(raw[4]).strip().lower()
            if strength not in ("hard", "soft"):
                raise ValueError("strength must be 'hard' or 'soft'.")
        out.append((entity_id, day, start, end, strength))
    return out


def _run_optimize_from_json(body: dict[str, Any]) -> dict[str, Any]:
    """Validate a ``/api/optimize`` JSON body and run the appropriate pipeline.

    Routes to the legacy single-teacher boolean stack when the request shape
    matches its constraints (default 30-min slots, single teacher, all-hard
    rows on both sides) so legacy result keys are preserved. Any richer
    payload falls through to the v2 weighted/multi-teacher stack.
    """
    settings = body.get("settings") or {}
    students_payload = body.get("students") or {}
    teachers_payload = body.get("teachers") or {}

    slot_length_slots = _coerce_int(
        settings.get("slot_length_slots"),
        2,
        minimum=1,
        maximum=48,
        label="Office hour length",
    )
    num_blocks = _coerce_int(
        settings.get("num_blocks"),
        1,
        minimum=1,
        maximum=20,
        label="Number of office hour blocks",
    )
    slot_minutes = _resolve_slot_minutes(settings.get("slot_minutes"))
    num_teachers = _coerce_int(
        settings.get("num_teachers"),
        1,
        minimum=1,
        maximum=10,
        label="Number of teachers",
    )

    student_rows = _v2_rows_from_payload(
        students_payload,
        parse_csv=parse_student_csv_text_v2,
        parse_manual=parse_manual_students_v2,
    )
    teacher_rows = _v2_rows_from_payload(
        teachers_payload,
        parse_csv=parse_teacher_csv_text_v2,
        parse_manual=parse_manual_teachers_v2,
    )

    is_legacy_shape = (
        slot_minutes == DEFAULT_SLOT_MINUTES
        and num_teachers == 1
        and all(row[4] == "hard" for row in student_rows)
        and all(row[4] == "hard" for row in teacher_rows)
        and len({row[0] for row in teacher_rows}) <= 1
    )

    if is_legacy_shape and student_rows and teacher_rows:
        legacy_student_rows = [(s, d, st, en) for s, d, st, en, _ in student_rows]
        legacy_teacher_rows = [(d, st, en) for _, d, st, en, _ in teacher_rows]
        return optimize_from_records(
            student_rows=legacy_student_rows,
            teacher_rows=legacy_teacher_rows,
            slot_length_slots=slot_length_slots,
            num_blocks=num_blocks,
        )

    slots_per_day = (24 * 60) // slot_minutes
    return optimize_from_records_v2(
        student_rows=student_rows,
        teacher_rows=teacher_rows,
        slot_length_slots=slot_length_slots,
        num_blocks=num_blocks,
        slots_per_day=slots_per_day,
    )


# ---------------------------------------------------------------------------
# JSON API
# ---------------------------------------------------------------------------


@app.route("/api/optimize", methods=["POST"])
def api_optimize():
    """Run the optimizer and return ``{result, share_token}`` on success.

    Validation errors surface as HTTP 400 with ``{"error": "..."}``;
    unexpected exceptions are logged and returned as HTTP 500.
    """
    if not request.is_json:
        return jsonify({"error": "Expected application/json body."}), 400
    body = request.get_json(silent=True) or {}

    try:
        result = _run_optimize_from_json(body)
    except (ValueError, UnicodeDecodeError) as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:  # pragma: no cover - defensive
        app.logger.exception("Unexpected optimization error")
        return jsonify({"error": "Unexpected error while running optimization."}), 500

    try:
        share_token = _encode_share_token(result)
    except (TypeError, ValueError):
        share_token = ""

    return jsonify({"result": result, "share_token": share_token})


@app.route("/api/share/<token>", methods=["GET"])
def api_share(token: str):
    """Return the previously-encoded result for a share token, or HTTP 404."""
    try:
        result = _decode_share_token(token)
    except ValueError:
        return jsonify({"error": "Invalid share token."}), 404
    return jsonify({"result": result})


# ---------------------------------------------------------------------------
# Static / SPA shell
# ---------------------------------------------------------------------------


def _spa_index_response():
    """Serve the prebuilt SPA shell, or a placeholder if it hasn't been built."""
    index = FRONTEND_DIST / "index.html"
    if index.is_file():
        return send_from_directory(FRONTEND_DIST, "index.html")
    return _frontend_missing_page()


def _frontend_missing_page():
    """Self-contained HTML page shown when ``frontend/dist/`` is absent.

    Kept inline (no Jinja, no template file) so this works even before any
    frontend build has been run.
    """
    body = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Frontend not built</title>
<style>body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:#0f172a;color:#e2e8f0;
display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}
.box{max-width:560px;background:#1e293b;border:1px solid #334155;border-radius:14px;padding:24px}
code{background:#0f172a;border:1px solid #334155;border-radius:6px;padding:2px 6px}
a{color:#60a5fa}</style></head>
<body><div class="box">
<h1 style="margin-top:0">Office Hours Scheduler</h1>
<p>The React frontend has not been built yet.</p>
<p>For development, in another terminal run:</p>
<pre><code>cd frontend
npm install
npm run dev</code></pre>
<p>Then open <a href="http://localhost:5173">http://localhost:5173</a>.</p>
<p>For production-style serving from Flask, run <code>npm run build</code> first.</p>
</div></body></html>"""
    return body, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/")
def index():
    """Serve the SPA shell at the root path."""
    return _spa_index_response()


@app.route("/r/<token>")
def share_result(token: str):  # noqa: ARG001 - SPA renders the share view client-side
    """Serve the SPA shell for share links.

    The token is intentionally ignored server-side; the SPA reads it from
    ``window.location.pathname`` and fetches via ``/api/share/<token>``.
    """
    return _spa_index_response()


@app.route("/favicon.svg")
def favicon_svg():
    """Serve the favicon copied into ``frontend/dist/`` by Vite."""
    favicon = FRONTEND_DIST / "favicon.svg"
    if favicon.is_file():
        return send_from_directory(FRONTEND_DIST, "favicon.svg")
    abort(404)


@app.route("/assets/<path:filename>")
def assets(filename: str):
    """Serve hashed JS/CSS bundles produced by the Vite build."""
    assets_dir = FRONTEND_DIST / "assets"
    if not assets_dir.is_dir():
        abort(404)
    return send_from_directory(assets_dir, filename)


if __name__ == "__main__":
    app.run(debug=True)
