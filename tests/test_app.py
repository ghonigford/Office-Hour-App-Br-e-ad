"""Integration tests for the Flask JSON API + SPA shell.

These tests exercise the routes registered in ``app.py``:

  * ``POST /api/optimize``      — JSON in / JSON out, with both legacy-shape
                                  and v2-weighted/multi-teacher payloads.
  * ``GET  /api/share/<token>`` — round-trip of the gzip+base64 share token.
  * ``GET  /``                  — SPA shell.
  * ``GET  /r/<token>``         — same SPA shell (the SPA decodes the token
                                  client-side and renders the read-only view).
  * ``GET  /favicon.svg``       — served from ``frontend/dist/`` when present.
  * ``GET  /assets/<path>``     — served from ``frontend/dist/assets/`` when
                                  present.

The static-asset routes are tested with ``monkeypatch`` pointing
``app.FRONTEND_DIST`` at a tmp directory so the tests are deterministic
regardless of whether ``npm run build`` has been run locally.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import app as app_module
from app import _normalize_rows, app as flask_app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def client():
    flask_app.config.update(TESTING=True)
    with flask_app.test_client() as test_client:
        yield test_client


def _post_optimize(client, body: dict):
    """Helper: POST a JSON body to /api/optimize."""
    return client.post(
        "/api/optimize",
        data=json.dumps(body),
        content_type="application/json",
    )


def _legacy_payload(**overrides) -> dict:
    """Three students all free 09:00-11:00 Mon, one teacher Mon 09:00-12:00."""
    base = {
        "settings": {
            "slot_minutes": 30,
            "day_start_hour": 8,
            "day_end_hour": 20,
            "num_teachers": 1,
            "slot_length_slots": 2,
            "num_blocks": 1,
        },
        "students": {
            "rows_v2": [
                ["s1", "mon", 18, 22, "hard"],
                ["s2", "mon", 19, 23, "hard"],
                ["s3", "mon", 18, 23, "hard"],
            ]
        },
        "teachers": {
            "rows_v2": [["prof1", "mon", 18, 24, "hard"]],
        },
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# SPA shell + static assets
# ---------------------------------------------------------------------------


class TestSpaShell:
    def test_get_index_returns_html_200(self, client) -> None:
        response = client.get("/")
        assert response.status_code == 200
        assert response.mimetype == "text/html"
        body = response.get_data(as_text=True)
        # Either the built SPA (links into /assets/) or the placeholder page,
        # but both contain "Office Hours Scheduler" in the title.
        assert "Office Hours Scheduler" in body

    def test_get_share_path_returns_same_spa_shell(self, client) -> None:
        # ``/r/<anything>`` must serve the SPA shell so the client can decode
        # the token; the server does NOT 404 on bad share tokens at this route.
        response = client.get("/r/anything-the-spa-will-look-at")
        assert response.status_code == 200
        assert response.mimetype == "text/html"

    def test_index_does_not_render_legacy_form_fields(self, client) -> None:
        # The legacy Jinja form is gone; make sure no one reintroduces it
        # without updating these tests.
        body = client.get("/").get_data(as_text=True)
        for legacy in (
            'name="students_csv"',
            'name="teachers_csv"',
            'name="students_manual"',
            'name="teachers_manual"',
        ):
            assert legacy not in body


class TestStaticAssets:
    def test_favicon_404_when_dist_missing(self, client, monkeypatch, tmp_path) -> None:
        monkeypatch.setattr(app_module, "FRONTEND_DIST", tmp_path / "no-such-dist")
        response = client.get("/favicon.svg")
        assert response.status_code == 404

    def test_favicon_served_from_dist(self, client, monkeypatch, tmp_path) -> None:
        dist = tmp_path / "dist"
        dist.mkdir()
        (dist / "favicon.svg").write_bytes(b"<svg></svg>")
        monkeypatch.setattr(app_module, "FRONTEND_DIST", dist)
        response = client.get("/favicon.svg")
        assert response.status_code == 200
        assert response.data == b"<svg></svg>"

    def test_assets_404_when_dist_missing(self, client, monkeypatch, tmp_path) -> None:
        monkeypatch.setattr(app_module, "FRONTEND_DIST", tmp_path / "no-such-dist")
        response = client.get("/assets/whatever.js")
        assert response.status_code == 404

    def test_assets_404_when_file_missing_in_existing_dist(
        self, client, monkeypatch, tmp_path
    ) -> None:
        dist = tmp_path / "dist"
        (dist / "assets").mkdir(parents=True)
        monkeypatch.setattr(app_module, "FRONTEND_DIST", dist)
        response = client.get("/assets/missing.js")
        assert response.status_code == 404

    def test_assets_served_from_dist(self, client, monkeypatch, tmp_path) -> None:
        dist = tmp_path / "dist"
        (dist / "assets").mkdir(parents=True)
        (dist / "assets" / "index-abc123.js").write_text("console.log('hi')")
        monkeypatch.setattr(app_module, "FRONTEND_DIST", dist)
        response = client.get("/assets/index-abc123.js")
        assert response.status_code == 200
        assert b"console.log" in response.data

    def test_index_uses_dist_when_available(
        self, client, monkeypatch, tmp_path
    ) -> None:
        dist = tmp_path / "dist"
        dist.mkdir()
        (dist / "index.html").write_text(
            "<!doctype html><html><body>real built SPA</body></html>"
        )
        monkeypatch.setattr(app_module, "FRONTEND_DIST", dist)
        response = client.get("/")
        assert response.status_code == 200
        assert b"real built SPA" in response.data

    def test_index_falls_back_to_placeholder_when_dist_missing(
        self, client, monkeypatch, tmp_path
    ) -> None:
        monkeypatch.setattr(app_module, "FRONTEND_DIST", tmp_path / "no-such-dist")
        response = client.get("/")
        assert response.status_code == 200
        body = response.get_data(as_text=True)
        # The placeholder explicitly tells the developer how to fix it.
        assert "frontend has not been built" in body
        assert "npm run dev" in body


# ---------------------------------------------------------------------------
# POST /api/optimize — happy paths
# ---------------------------------------------------------------------------


class TestApiOptimizeLegacyShape:
    def test_three_students_one_block_returns_legacy_result(self, client) -> None:
        response = _post_optimize(client, _legacy_payload())
        assert response.status_code == 200
        body = response.get_json()
        assert "result" in body and "share_token" in body
        result = body["result"]
        # All three students reachable in one block.
        assert result["students_covered"] == 3
        assert result["total_students"] == 3
        assert result["coverage_ratio"] == pytest.approx(1.0)
        assert result["num_blocks_selected"] == 1
        assert result["num_blocks_requested"] == 1
        assert len(result["blocks"]) == 1
        block = result["blocks"][0]
        assert block["slot_day"] == "mon"
        # Legacy result keys must be present.
        assert "students_covered_in_block" in block
        assert "available_student_ids" in block
        assert sorted(result["covered_student_ids"]) == ["s1", "s2", "s3"]

    def test_legacy_shape_does_not_set_v2_only_keys(self, client) -> None:
        # When all rows are hard, num_teachers=1, slot_minutes=30, and there's
        # only one teacher_id, _run_optimize_from_json takes the legacy
        # branch and the v2-only result keys must not appear.
        response = _post_optimize(client, _legacy_payload())
        result = response.get_json()["result"]
        assert "weighted_coverage" not in result
        assert "weighted_coverage_ratio" not in result
        assert "slots_per_day" not in result

    def test_two_blocks_disjoint_groups(self, client) -> None:
        body = _legacy_payload(
            students={
                "rows_v2": [
                    ["a1", "mon", 18, 20, "hard"],
                    ["a2", "mon", 18, 20, "hard"],
                    ["b1", "mon", 28, 30, "hard"],
                    ["b2", "mon", 28, 30, "hard"],
                ]
            },
            teachers={"rows_v2": [["prof1", "mon", 18, 32, "hard"]]},
        )
        body["settings"]["slot_length_slots"] = 2
        body["settings"]["num_blocks"] = 2
        response = _post_optimize(client, body)
        assert response.status_code == 200
        result = response.get_json()["result"]
        assert result["students_covered"] == 4
        assert result["total_students"] == 4
        assert result["num_blocks_selected"] == 2

    def test_share_token_is_returned_and_nonempty(self, client) -> None:
        response = _post_optimize(client, _legacy_payload())
        token = response.get_json()["share_token"]
        assert isinstance(token, str)
        assert len(token) > 10
        # URL-safe base64 alphabet only.
        assert all(c.isalnum() or c in "-_" for c in token)


class TestApiOptimizeV2Weighted:
    def test_soft_strength_triggers_v2_pipeline(self, client) -> None:
        body = _legacy_payload(
            students={
                "rows_v2": [
                    ["s1", "mon", 18, 22, "hard"],
                    ["s2", "mon", 19, 23, "hard"],
                    ["s3", "mon", 18, 23, "soft"],  # one soft → v2 pipeline
                ]
            },
        )
        response = _post_optimize(client, body)
        assert response.status_code == 200
        result = response.get_json()["result"]
        # V2-only result keys are populated.
        assert "weighted_coverage" in result
        assert "weighted_coverage_ratio" in result
        assert "slots_per_day" in result
        assert result["slots_per_day"] == 48
        # Each block has v2 keys too.
        for block in result["blocks"]:
            assert "host" in block
            assert "students_covered_hard" in block
            assert "students_covered_soft" in block

    def test_multi_teacher_assigns_one_host_per_block(self, client) -> None:
        body = {
            "settings": {
                "slot_minutes": 30,
                "num_teachers": 2,
                "slot_length_slots": 2,
                "num_blocks": 2,
            },
            "students": {
                "rows_v2": [
                    ["s1", "mon", 18, 22, "hard"],
                    ["s2", "tue", 18, 22, "hard"],
                ]
            },
            "teachers": {
                "rows_v2": [
                    ["prof1", "mon", 18, 24, "hard"],
                    ["prof2", "tue", 18, 24, "hard"],
                ]
            },
        }
        response = _post_optimize(client, body)
        assert response.status_code == 200
        result = response.get_json()["result"]
        assert result["num_blocks_selected"] >= 1
        # Hosts are present and from the configured teacher set.
        configured = {"prof1", "prof2"}
        for block in result["blocks"]:
            assert block["host"] in configured

    def test_finer_15_min_granularity(self, client) -> None:
        # With 15-min slots, slot 72 == 18:00 (= 18*4). A 4-slot block = 1h.
        body = {
            "settings": {
                "slot_minutes": 15,
                "slot_length_slots": 4,
                "num_blocks": 1,
                "num_teachers": 1,
            },
            "students": {
                "rows_v2": [
                    ["s1", "mon", 72, 80, "hard"],
                    ["s2", "mon", 76, 84, "hard"],
                ]
            },
            "teachers": {"rows_v2": [["prof1", "mon", 72, 84, "hard"]]},
        }
        response = _post_optimize(client, body)
        assert response.status_code == 200
        result = response.get_json()["result"]
        assert result["slots_per_day"] == 96  # (24*60)/15
        assert result["num_blocks_selected"] == 1

    def test_coarser_60_min_granularity(self, client) -> None:
        body = {
            "settings": {
                "slot_minutes": 60,
                "slot_length_slots": 1,
                "num_blocks": 1,
                "num_teachers": 1,
            },
            "students": {
                "rows_v2": [
                    ["s1", "mon", 9, 11, "hard"],
                    ["s2", "mon", 10, 12, "hard"],
                ]
            },
            "teachers": {"rows_v2": [["prof1", "mon", 9, 12, "hard"]]},
        }
        response = _post_optimize(client, body)
        assert response.status_code == 200
        result = response.get_json()["result"]
        assert result["slots_per_day"] == 24

    def test_uncovered_student_ids_present_when_some_unreachable(self, client) -> None:
        body = {
            "settings": {
                "slot_minutes": 30,
                "slot_length_slots": 2,
                "num_blocks": 1,
                "num_teachers": 1,
            },
            "students": {
                "rows_v2": [
                    ["reachable", "mon", 18, 22, "hard"],
                    # Available outside the teacher's window — cannot be reached.
                    ["unreachable", "fri", 36, 40, "hard"],
                ]
            },
            "teachers": {"rows_v2": [["prof1", "mon", 18, 24, "soft"]]},
        }
        response = _post_optimize(client, body)
        assert response.status_code == 200
        result = response.get_json()["result"]
        assert "uncovered_student_ids" in result
        assert "unreachable" in result["uncovered_student_ids"]


class TestApiOptimizeCsvText:
    def test_student_csv_text_input(self, client) -> None:
        body = {
            "settings": {"slot_length_slots": 2, "num_blocks": 1, "num_teachers": 1},
            "students": {
                "csv_text": (
                    "id,day,start_slot,end_slot\n"
                    "s1,mon,18,22\n"
                    "s2,mon,19,23\n"
                )
            },
            "teachers": {"rows_v2": [["prof1", "mon", 18, 24, "hard"]]},
        }
        response = _post_optimize(client, body)
        assert response.status_code == 200
        result = response.get_json()["result"]
        assert sorted(result["student_ids"]) == ["s1", "s2"]
        assert result["num_blocks_selected"] == 1

    def test_teacher_csv_text_input_legacy_3col(self, client) -> None:
        body = {
            "settings": {"slot_length_slots": 2, "num_blocks": 1, "num_teachers": 1},
            "students": {"rows_v2": [["s1", "mon", 18, 22, "hard"]]},
            "teachers": {"csv_text": "day,start_slot,end_slot\nmon,18,24\n"},
        }
        response = _post_optimize(client, body)
        assert response.status_code == 200
        assert response.get_json()["result"]["num_blocks_selected"] == 1

    def test_teacher_csv_text_input_v2_with_strength(self, client) -> None:
        body = {
            "settings": {"slot_length_slots": 2, "num_blocks": 1, "num_teachers": 2},
            "students": {"rows_v2": [["s1", "mon", 18, 22, "hard"]]},
            "teachers": {
                "csv_text": (
                    "teacher_id,day,start_slot,end_slot,strength\n"
                    "prof1,mon,18,24,hard\n"
                    "prof2,tue,18,24,soft\n"
                )
            },
        }
        response = _post_optimize(client, body)
        assert response.status_code == 200
        result = response.get_json()["result"]
        assert "weighted_coverage" in result  # multi-teacher → v2

    def test_invalid_student_csv_returns_400(self, client) -> None:
        body = {
            "settings": {"slot_length_slots": 2, "num_blocks": 1, "num_teachers": 1},
            "students": {
                "csv_text": "totally,bogus,header,row\noops,oops,oops,oops\n"
            },
            "teachers": {"rows_v2": [["prof1", "mon", 18, 24, "hard"]]},
        }
        response = _post_optimize(client, body)
        assert response.status_code == 400
        assert "error" in response.get_json()


class TestApiOptimizeSourcePrecedence:
    def test_rows_v2_takes_precedence_over_csv_text(self, client) -> None:
        # The csv_text is intentionally invalid — it would error if used.
        body = {
            "settings": {"slot_length_slots": 2, "num_blocks": 1, "num_teachers": 1},
            "students": {
                "rows_v2": [["s1", "mon", 18, 22, "hard"]],
                "csv_text": "this,is,broken\nfoo,bar,baz\n",
            },
            "teachers": {"rows_v2": [["prof1", "mon", 18, 24, "hard"]]},
        }
        response = _post_optimize(client, body)
        assert response.status_code == 200
        result = response.get_json()["result"]
        assert result["student_ids"] == ["s1"]


# ---------------------------------------------------------------------------
# POST /api/optimize — error / validation paths
# ---------------------------------------------------------------------------


class TestApiOptimizeRequestErrors:
    def test_non_json_body_returns_400(self, client) -> None:
        # Plain text content type — Flask's request.is_json is False.
        response = client.post(
            "/api/optimize",
            data="hello",
            content_type="text/plain",
        )
        assert response.status_code == 400
        body = response.get_json()
        assert body and "error" in body
        assert "json" in body["error"].lower()

    def test_empty_json_body_returns_missing_data_error(self, client) -> None:
        response = client.post("/api/optimize", json={})
        assert response.status_code == 400
        # The optimizer surfaces the underlying ValueError ("No student
        # availability rows..."), which is the correct user-facing message.
        body = response.get_json()
        assert body and "error" in body

    def test_missing_students_returns_400(self, client) -> None:
        response = _post_optimize(
            client,
            {
                "settings": {"slot_length_slots": 2, "num_blocks": 1, "num_teachers": 1},
                "teachers": {"rows_v2": [["prof1", "mon", 18, 24, "hard"]]},
            },
        )
        assert response.status_code == 400
        assert "student" in response.get_json()["error"].lower()

    def test_missing_teachers_returns_400(self, client) -> None:
        response = _post_optimize(
            client,
            {
                "settings": {"slot_length_slots": 2, "num_blocks": 1, "num_teachers": 1},
                "students": {"rows_v2": [["s1", "mon", 18, 22, "hard"]]},
            },
        )
        assert response.status_code == 400
        assert "teacher" in response.get_json()["error"].lower()


class TestApiOptimizeValidationErrors:
    @pytest.fixture
    def base_body(self):
        return {
            "settings": {"slot_length_slots": 2, "num_blocks": 1, "num_teachers": 1},
            "students": {"rows_v2": [["s1", "mon", 18, 22, "hard"]]},
            "teachers": {"rows_v2": [["prof1", "mon", 18, 24, "hard"]]},
        }

    def test_zero_slot_length_returns_400(self, client, base_body) -> None:
        base_body["settings"]["slot_length_slots"] = 0
        response = _post_optimize(client, base_body)
        assert response.status_code == 400
        assert "Office hour length" in response.get_json()["error"]

    def test_too_long_slot_length_returns_400(self, client, base_body) -> None:
        base_body["settings"]["slot_length_slots"] = 100
        response = _post_optimize(client, base_body)
        assert response.status_code == 400
        assert "Office hour length" in response.get_json()["error"]

    def test_zero_num_blocks_returns_400(self, client, base_body) -> None:
        base_body["settings"]["num_blocks"] = 0
        response = _post_optimize(client, base_body)
        assert response.status_code == 400
        assert "Number of office hour blocks" in response.get_json()["error"]

    def test_too_many_num_blocks_returns_400(self, client, base_body) -> None:
        base_body["settings"]["num_blocks"] = 21
        response = _post_optimize(client, base_body)
        assert response.status_code == 400
        assert "Number of office hour blocks" in response.get_json()["error"]

    def test_non_integer_num_blocks_returns_400(self, client, base_body) -> None:
        base_body["settings"]["num_blocks"] = "abc"
        response = _post_optimize(client, base_body)
        assert response.status_code == 400
        assert "integer" in response.get_json()["error"].lower()

    def test_unsupported_slot_minutes_returns_400(self, client, base_body) -> None:
        base_body["settings"]["slot_minutes"] = 7
        response = _post_optimize(client, base_body)
        assert response.status_code == 400
        msg = response.get_json()["error"]
        assert "15" in msg and "30" in msg and "60" in msg

    def test_non_integer_slot_minutes_returns_400(self, client, base_body) -> None:
        base_body["settings"]["slot_minutes"] = "thirty"
        response = _post_optimize(client, base_body)
        assert response.status_code == 400
        assert "integer" in response.get_json()["error"].lower()

    def test_too_many_teachers_returns_400(self, client, base_body) -> None:
        base_body["settings"]["num_teachers"] = 11
        response = _post_optimize(client, base_body)
        assert response.status_code == 400
        assert "Number of teachers" in response.get_json()["error"]

    def test_zero_teachers_returns_400(self, client, base_body) -> None:
        base_body["settings"]["num_teachers"] = 0
        response = _post_optimize(client, base_body)
        assert response.status_code == 400
        assert "Number of teachers" in response.get_json()["error"]

    def test_invalid_day_in_rows_returns_400(self, client, base_body) -> None:
        base_body["students"]["rows_v2"] = [["s1", "sat", 18, 22, "hard"]]
        response = _post_optimize(client, base_body)
        assert response.status_code == 400
        assert "Unsupported day" in response.get_json()["error"]


class TestNormalizeRows:
    def test_accepts_4_field_row_defaults_to_hard(self) -> None:
        rows = _normalize_rows([["s1", "mon", 18, 22]])
        assert rows == [("s1", "mon", 18, 22, "hard")]

    def test_accepts_5_field_row_with_explicit_strength(self) -> None:
        rows = _normalize_rows([["s1", "mon", 18, 22, "soft"]])
        assert rows == [("s1", "mon", 18, 22, "soft")]

    def test_strips_and_lowercases_string_fields(self) -> None:
        rows = _normalize_rows([["  s1 ", " MON ", 18, 22, " HARD "]])
        assert rows == [("s1", "mon", 18, 22, "hard")]

    def test_blank_strength_field_defaults_to_hard(self) -> None:
        # An empty string in position 4 should fall back to "hard".
        rows = _normalize_rows([["s1", "mon", 18, 22, ""]])
        assert rows == [("s1", "mon", 18, 22, "hard")]

    def test_rejects_non_list(self) -> None:
        with pytest.raises(ValueError, match="rows_v2 must be a list"):
            _normalize_rows("not-a-list")

    def test_rejects_non_list_row(self) -> None:
        with pytest.raises(ValueError, match="Each row must be a list"):
            _normalize_rows(["not-a-row"])

    def test_rejects_too_few_fields(self) -> None:
        with pytest.raises(ValueError, match="4 or 5 fields"):
            _normalize_rows([["s1", "mon", 18]])

    def test_rejects_too_many_fields(self) -> None:
        with pytest.raises(ValueError, match="4 or 5 fields"):
            _normalize_rows([["s1", "mon", 18, 22, "hard", "extra"]])

    def test_rejects_non_integer_slots(self) -> None:
        with pytest.raises(ValueError, match="integers"):
            _normalize_rows([["s1", "mon", "eighteen", 22]])

    def test_rejects_invalid_strength(self) -> None:
        with pytest.raises(ValueError, match="hard.+soft"):
            _normalize_rows([["s1", "mon", 18, 22, "maybe"]])

    def test_rejects_unsupported_day(self) -> None:
        with pytest.raises(ValueError, match="Unsupported day"):
            _normalize_rows([["s1", "sat", 18, 22, "hard"]])

    def test_rejects_blank_id(self) -> None:
        with pytest.raises(ValueError, match="missing an id"):
            _normalize_rows([["   ", "mon", 18, 22, "hard"]])

    def test_rejects_negative_slot(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            _normalize_rows([["s1", "mon", -1, 22, "hard"]])

    def test_rejects_start_geq_end(self) -> None:
        with pytest.raises(ValueError, match="start_slot >= end_slot"):
            _normalize_rows([["s1", "mon", 22, 22, "hard"]])

    def test_normalizes_long_day_name(self) -> None:
        # ``_normalize_day`` truncates to first 3 characters lowercased,
        # so "Monday" round-trips to "mon".
        rows = _normalize_rows([["s1", "Monday", 18, 22, "hard"]])
        assert rows == [("s1", "mon", 18, 22, "hard")]


# ---------------------------------------------------------------------------
# GET /api/share/<token>
# ---------------------------------------------------------------------------


class TestApiShare:
    def test_optimize_then_share_round_trip(self, client) -> None:
        post_response = _post_optimize(client, _legacy_payload())
        assert post_response.status_code == 200
        body = post_response.get_json()
        token = body["share_token"]
        assert token  # non-empty

        share_response = client.get(f"/api/share/{token}")
        assert share_response.status_code == 200
        share_body = share_response.get_json()
        assert "result" in share_body

        # The shared result is byte-identical to the freshly-optimized one.
        assert share_body["result"] == body["result"]

    def test_share_returns_json_not_html(self, client) -> None:
        post_response = _post_optimize(client, _legacy_payload())
        token = post_response.get_json()["share_token"]
        share_response = client.get(f"/api/share/{token}")
        assert share_response.mimetype == "application/json"

    def test_share_v2_round_trip_preserves_all_v2_keys(self, client) -> None:
        # Use a v2-shape payload so the result has the extended schema.
        body = {
            "settings": {
                "slot_minutes": 30,
                "num_teachers": 2,
                "slot_length_slots": 2,
                "num_blocks": 1,
            },
            "students": {
                "rows_v2": [
                    ["s1", "mon", 18, 22, "hard"],
                    ["s2", "mon", 18, 22, "soft"],
                ]
            },
            "teachers": {
                "rows_v2": [
                    ["prof1", "mon", 18, 24, "hard"],
                    ["prof2", "tue", 18, 24, "hard"],
                ]
            },
        }
        post_response = _post_optimize(client, body)
        token = post_response.get_json()["share_token"]
        share_response = client.get(f"/api/share/{token}")
        result = share_response.get_json()["result"]
        for key in (
            "weighted_coverage",
            "weighted_coverage_ratio",
            "slots_per_day",
            "teacher_ids",
            "student_availability",
            "teacher_availability",
            "uncovered_student_ids",
        ):
            assert key in result, f"missing v2 key: {key}"

    def test_invalid_share_token_returns_404_json(self, client) -> None:
        response = client.get("/api/share/not-a-real-token!!!")
        assert response.status_code == 404
        body = response.get_json()
        assert body and "error" in body

    def test_garbage_share_token_returns_404(self, client) -> None:
        response = client.get("/api/share/" + "A" * 200)
        assert response.status_code == 404

    def test_share_token_round_trips_for_legacy_shape(self, client) -> None:
        # Verifies that the legacy-shape result (which lacks v2 keys) still
        # encodes/decodes cleanly through the share-token path.
        post_response = _post_optimize(client, _legacy_payload())
        token = post_response.get_json()["share_token"]
        result = client.get(f"/api/share/{token}").get_json()["result"]
        assert "blocks" in result
        assert "students_covered" in result
        # And legacy shape really lacks v2 keys.
        assert "weighted_coverage" not in result


# ---------------------------------------------------------------------------
# Smoke test: encoded module-level constants
# ---------------------------------------------------------------------------


class TestModuleSurface:
    def test_supported_slot_minutes_unchanged(self) -> None:
        # The frontend SettingsCard hard-codes these three values too. If you
        # add a new granularity here, also add it in the SPA's slot-minutes
        # dropdown.
        assert app_module.SUPPORTED_SLOT_MINUTES == (15, 30, 60)

    def test_default_slot_minutes_is_30(self) -> None:
        assert app_module.DEFAULT_SLOT_MINUTES == 30

    def test_frontend_dist_is_a_path(self) -> None:
        assert isinstance(app_module.FRONTEND_DIST, Path)
        # It points at frontend/dist relative to the repo root, regardless of
        # whether the directory currently exists.
        assert app_module.FRONTEND_DIST.name == "dist"
        assert app_module.FRONTEND_DIST.parent.name == "frontend"

    def test_max_content_length_is_5mb(self) -> None:
        assert flask_app.config["MAX_CONTENT_LENGTH"] == 5 * 1024 * 1024
