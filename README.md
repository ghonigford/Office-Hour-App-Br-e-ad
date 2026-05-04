# Office Hours Scheduler

A Flask + React web app that helps a faculty member pick the office-hour
window(s) the most students can actually attend, given their weekly
availability. Built as the AI-class final project by Ashton Beresford,
Truman Godsey, and Brad Hanley.

## Public URL
https://office-hours-optimizer.onrender.com/

## What it does

- Takes student availability and teacher availability for Mon–Fri.
- Lets the teacher pick the slot **granularity** (15 / 30 / 60 min), the
  **day window** (e.g. 8 AM – 8 PM), how long each office-hour block should
  be, how many non-overlapping blocks to schedule (1–20), and how many
  teachers to schedule for.
- Supports **hard vs soft** availability for both students and teachers:
  hard slots count fully (1.0), soft slots count half (0.5). Both sides can
  flip into "mark unavailability" mode and tag busy slots instead.
- For multiple teachers, the optimizer assigns each block to a specific host
  and a student is covered if they can attend any block hosted by their
  matching teacher.
- Runs a `pymoo` genetic algorithm that picks the set of `(start, host)`
  pairs maximizing total weighted unique student coverage.
- Renders a result panel with picked blocks and hosts, who is available in
  each, the overall weighted/coverage ratios, and a panel listing
  **uncovered students** with their availability so you can see why.
- Generates a stateless **read-only share link** (`/r/<token>`) that
  recreates the result page from a gzip+base64 of the result itself — no
  server storage required.
- Modern UI with **dark mode** (system preference + persisted toggle),
  toast notifications, and a `⌘/Ctrl + Enter` keyboard shortcut to run.

## Architecture

- **Frontend**: React 18 + TypeScript + Vite + Tailwind CSS, in `frontend/`.
- **Backend**: Flask exposing a JSON API (`/api/optimize`,
  `/api/share/<token>`) and serving the built SPA at `/` and `/r/<token>`.
- **Optimizer**: pymoo, in `optimize.py` — completely unchanged by the UI
  rewrite. Both legacy and v2 stacks remain available.
- **Deployment**: Multi-stage Dockerfile (Node 20 builds the frontend,
  Python 3.11 runs gunicorn with the built dist/ baked in).

## Project layout

```
.
├── app.py                      # Flask: JSON API + SPA shell + share routes
├── optimize.py                 # Parsing, matrix building, pymoo optimizer
│                               #   (legacy boolean stack + v2 weighted/multi-teacher)
├── Dockerfile                  # Multi-stage: Node build → Python runtime
├── render.yaml                 # Render.com config (Docker runtime)
├── requirements.txt            # Runtime deps (flask, gunicorn, pymoo)
├── requirements-dev.txt        # Adds pytest for the test suite
├── pytest.ini                  # Pytest configuration
├── conftest.py                 # Anchors pytest's rootdir
├── AGENTS.md                   # Guidance for AI coding agents
├── frontend/                   # React + TS + Vite + Tailwind SPA
│   ├── package.json
│   ├── vite.config.ts          # Dev server proxies /api → Flask :5000
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   ├── public/favicon.svg
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── index.css           # Tailwind base + component classes
│       ├── types.ts            # Shared types matching the v2 result schema
│       ├── components/         # Header, Settings, Editors, Heatmap,
│       │                       #   ResultPanel, ResultCalendar, ShareView,
│       │                       #   Modal, Toast, etc.
│       ├── lib/                # api.ts, slots.ts, classnames.ts
│       └── state/              # editor.tsx (reducer + context),
│                               #   theme.ts, toast.tsx
├── examples/                   # Sample CSVs
├── docs/                       # Historical planning notes
├── legacy/                     # Standalone prototypes kept for reference
└── tests/                      # Pytest suite (parsers, helpers, optimizers,
                                #   app routes — being updated for the new API)
```

## Running locally (development)

You'll want two terminals: one for Flask (the API), one for Vite (the SPA).

```bash
# Terminal 1: API
pip install -r requirements.txt
python app.py
# → Flask on http://localhost:5000

# Terminal 2: SPA
cd frontend
npm install
npm run dev
# → Vite on http://localhost:5173 (proxies /api → :5000)
```

Then open <http://localhost:5173>. The Vite dev server hot-reloads on
every save and proxies API calls to Flask automatically.

### Production-like single-server mode

If you'd rather run everything from Flask:

```bash
cd frontend
npm install
npm run build         # produces frontend/dist/
cd ..
python app.py
# → http://localhost:5000 serves both the SPA and the API
```

If you skip the `npm run build` step, opening <http://localhost:5000>
shows a friendly placeholder page with the dev instructions.

### Docker (matches production)

```bash
docker build -t office-hours .
docker run -p 8000:8000 office-hours
# → http://localhost:8000
```

## API

### `POST /api/optimize`

Request body (all `settings` keys have sensible defaults):

```jsonc
{
  "settings": {
    "slot_minutes": 30,
    "day_start_hour": 8,
    "day_end_hour": 20,
    "num_teachers": 1,
    "slot_length_slots": 2,
    "num_blocks": 1
  },
  "students": {
    "rows_v2": [["s1", "mon", 18, 22, "hard"], ["s2", "tue", 20, 24, "soft"]]
    // OR: "csv_text": "id,day,start_slot,end_slot,strength\n…"
  },
  "teachers": {
    "rows_v2": [["prof1", "mon", 18, 24, "hard"]]
    // OR: "csv_text": "teacher_id,day,start_slot,end_slot,strength\n…"
  }
}
```

Response on success: `{ "result": <result_dict>, "share_token": "…" }`.
Response on error: `{ "error": "…" }` with HTTP 400.

### `GET /api/share/<token>`

Returns `{ "result": <result_dict> }` for a previously-issued token, or
HTTP 404 if the token is malformed.

### `GET /` and `GET /r/<token>`

Serve the SPA shell. The React app inspects the URL client-side to decide
between the editor and the read-only share view.

## Input formats (CSV uploads)

The same CSV formats the legacy app accepted are still accepted — they're
parsed server-side by `optimize.parse_*_csv_text_v2`.

### Student CSV

```
id,day,start_slot,end_slot
s1,mon,18,22
```

Optional `strength` column (`hard` / `soft`):

```
id,day,start_slot,end_slot,strength
s1,mon,18,22,hard
s1,mon,22,24,soft
```

The wide template is also accepted:

```
student,Monday_start,Monday_end,Tuesday_start,Tuesday_end,...,Friday_start,Friday_end
Brad,09:00,11:00,,,10:00,12:00,,,,
```

### Teacher CSV

Single teacher (legacy):

```
day,start_slot,end_slot
mon,18,24
```

Multi-teacher with optional strength:

```
teacher_id,day,start_slot,end_slot,strength
prof1,mon,18,24,hard
prof2,tue,20,30,soft
```

## Hard vs soft semantics

Each per-slot weight is `1.0` (hard), `0.5` (soft), or `0.0` (unavailable).

For a block hosted by a particular teacher, each student's per-block score
is the elementwise minimum across the block's slots of
`min(student_weight, host_weight)`. So:

- hard student attending a fully-hard host block → score 1.0,
- any soft slot anywhere in the pair → score 0.5,
- any unavailable slot → score 0.0.

A student's contribution to a schedule is the **max** of their per-block
scores across all kept blocks. The optimizer maximises the sum of those
contributions across all students.

## Sharing results

Every successful optimization returns a `share_token`. The SPA renders an
absolute `/r/<token>` URL with a Copy button. The token embeds a
gzip-compressed, URL-safe base64 of the result JSON, so it's stateless —
no server storage, no expiry. Tokens are typically a few hundred bytes;
large-class runs may push 1–2 KB.

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

Expected: **226 tests passing** in ~45 seconds. Coverage:

- `tests/test_parsers.py` — CSV + manual parsers (legacy + v2).
- `tests/test_helpers.py` — matrix builders, slot encoding, coverage helpers.
- `tests/test_optimizers.py` — pymoo end-to-end runs for legacy single-block,
  legacy multi-block, v2 weighted multi-teacher, plus `write_result_csv`.
- `tests/test_app.py` — Flask JSON API: `POST /api/optimize` happy paths
  (legacy + v2 + multi-teacher + 15/60-min granularities + CSV-text input),
  all validation error paths, source precedence rules, `_normalize_rows`
  unit tests, share-token round-trip via `GET /api/share/<token>`, the SPA
  shell routes (`GET /`, `GET /r/<token>`), and the static-asset routes
  (`/favicon.svg`, `/assets/<path>`). The static-asset tests use
  `monkeypatch` so they're deterministic whether or not you've run
  `npm run build`.

To run a single suite:

```bash
pytest tests/test_parsers.py
pytest tests/test_helpers.py
pytest tests/test_optimizers.py
pytest tests/test_app.py
```

Or just the new fast Flask tests (no pymoo):

```bash
pytest tests/test_app.py -k 'not Optimize or ValidationErrors or RequestErrors or NormalizeRows or Spa or Static or Module'
```

## Deployment

Render is configured to use the multi-stage `Dockerfile`. Pushing to the
main branch triggers a rebuild that:

1. Installs Node 20 and `npm ci` in `frontend/`.
2. Runs `vite build` to produce `frontend/dist/`.
3. Switches to the Python 3.11 base image, installs `requirements.txt`,
   and copies the built `dist/` in.
4. Starts gunicorn on port 8000.
