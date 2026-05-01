# Office Hours Scheduler

A small Flask web app that helps a faculty member pick the office-hour
window(s) that the most students can actually attend, given their weekly
availability. Built as the AI-class final project by Ashton Beresford,
Truman Godsey, and Brad Hanley (the "Make an app to help a faculty create
the best office hours given the students' schedules" prompt).

## What it does

- Takes student availability and teacher availability for Mon–Fri.
- Lets the teacher choose how long each office hour block should be
  (30 min or 1 hr) and how many non-overlapping blocks to schedule
  (1–20).
- Runs a `pymoo` genetic algorithm (`OfficeHoursMultiBlockProblem`) that
  picks the set of blocks maximizing the number of *unique* students who
  can fully attend at least one of the chosen blocks (set-cover style —
  each student counts at most once).
- Renders a result panel showing the picked blocks, who is available in
  each, and the overall coverage ratio.

## Project layout

```
.
├── app.py                  # Flask route + form/file plumbing
├── optimize.py             # Parsing, matrix building, and the pymoo optimizer
├── render.yaml             # Render.com web service config
├── requirements.txt        # Runtime deps (flask, gunicorn, pymoo)
├── requirements-dev.txt    # Adds pytest for the test suite
├── pytest.ini              # Pytest configuration
├── conftest.py             # Anchors pytest's rootdir
├── AGENTS.md               # Guidance for AI coding agents working on this repo
├── templates/
│   └── index.html          # Single-page UI (form + result panel)
├── examples/               # Sample CSVs (template + ready-to-run inputs)
│   ├── availability_template.csv
│   ├── students_availability.csv
│   └── teacher_availability.csv
├── docs/                   # Historical planning notes
│   └── implement_optimize_plan.md
├── legacy/                 # Standalone prototypes kept for reference
│   └── ai_final.py
└── tests/                  # Unit + integration tests (see below)
    ├── test_parsers.py
    ├── test_helpers.py
    ├── test_optimizers.py
    └── test_app.py
```

## Running locally

```bash
pip install -r requirements.txt
python app.py
```

Then open http://localhost:5000.

## Input formats

The app accepts both file uploads and pasted manual rows for students and
teachers. When the manual textarea is non-empty, it takes precedence over
the uploaded file.

**Student "slot" CSV (and the manual textarea format):**

```
id,day,start_slot,end_slot
s1,mon,18,22
s2,tue,20,24
```

`day` is one of `mon`, `tue`, `wed`, `thu`, `fri` (case insensitive).
`start_slot` / `end_slot` are 30-minute slot indices from midnight, so
`18 = 09:00`, `24 = 12:00`, `48 = 24:00`. `end_slot` is exclusive.

**Student "wide" CSV** (matches [`examples/availability_template.csv`](examples/availability_template.csv)):

```
student,Monday_start,Monday_end,Tuesday_start,Tuesday_end, ... ,Friday_start,Friday_end
Brad,09:00,11:00,,,10:00,12:00,,,,
```

Times must be `HH:MM` and currently align to 30-minute boundaries.

**Teacher CSV / manual rows:**

```
day,start_slot,end_slot
mon,18,24
fri,20,30
```

## Testing

This project ships with a `pytest` test suite under `tests/`. It covers
parsing, matrix building, the pymoo optimizer (single + multi-block) and
the Flask route end-to-end via `app.test_client()`.

```bash
pip install -r requirements-dev.txt
pytest
```

Expected output: ~119 tests passing in well under a minute. The pymoo GA
is seeded so test runs are deterministic.

To run a single suite:

```bash
pytest tests/test_parsers.py
pytest tests/test_helpers.py
pytest tests/test_optimizers.py
pytest tests/test_app.py
```

## Deployment

`render.yaml` deploys the app on [Render](https://render.com) using
`gunicorn app:app`. Any change merged to the main branch redeploys.
