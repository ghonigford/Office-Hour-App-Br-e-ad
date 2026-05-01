## Do

- Use Python 3.11, Flask (`app.py`, `gunicorn` in production via `render.yaml`).
- Use `pymoo` for schedule search ([`requirements.txt`](requirements.txt)).
- Keep `optimize.py` as the canonical parsing + optimization pipeline used by Flask.
- Prefer adding small pure functions in `optimize.py` over spreading CSV parsing logic in routes.
- Run the test suite (`pytest`) after any change to `optimize.py` or `app.py`.
- When adding behaviour, add a corresponding test under `tests/` rather than only
  manually verifying in the browser.

## Don't

- Delete the entire code base.
- Bake test-only dependencies (e.g. `pytest`) into `requirements.txt` — those
  belong in `requirements-dev.txt` so the production image stays small.
- Change route names or form field names without also updating
  `templates/index.html` and `tests/test_app.py`.

## Project structure

- `app.py` and `render.yaml` --> set up the website (Flask + Render web service).
- `optimize.py` --> parsing, availability matrices, pymoo optimization.
- `templates/index.html` --> single-page UI (form + result panel + small JS calendar viz).
- `examples/` --> sample input CSVs.
  - `availability_template.csv` --> wide-format student template.
  - `students_availability.csv` / `teacher_availability.csv` --> small ready-to-run inputs.
- `legacy/` --> code kept for reference, not part of the live app.
  - `legacy/ai_final.py` --> standalone CLI prototype (predecessor to the Flask app).
- `docs/` --> historical / non-code documentation.
  - `docs/implement_optimize_plan.md` --> the original tiny-step plan that brought up `optimize.py`.
- `tests/` --> pytest test suite (parsers, helpers, optimizers, Flask app).
- `pytest.ini` --> pytest config (`testpaths = tests`).
- `conftest.py` --> empty file at repo root that anchors pytest's rootdir so
  tests can `from optimize import ...` / `from app import ...`.
- `requirements.txt` / `requirements-dev.txt` --> runtime deps and the test-only
  add-on (`pytest`).

## Input formats currently supported

- Student slot CSV: `id,day,start_slot,end_slot`
  - Example row: `s1,mon,20,22`
- Teacher slot CSV: `day,start_slot,end_slot`
  - Example row: `mon,18,24`
- Student wide template CSV is also supported for parsing:
  - `student,Monday_start,Monday_end,Tuesday_start,Tuesday_end,Wednesday_start,Wednesday_end,Thursday_start,Thursday_end,Friday_start,Friday_end`
  - Times must be `HH:MM` and currently map to 30-minute slots from midnight (e.g. `09:00 -> slot 18`).
- Manual textarea input mirrors the slot CSV row format (one row per line, no header).

## Flask behavior notes

- `app.py` route `/` supports both `GET` and `POST`.
- POST source precedence:
  - students: use `students_manual` textarea if non-empty; else use `students_csv` upload.
  - teachers: use `teachers_manual` textarea if non-empty; else use `teachers_csv` upload.
- The route passes `result` or `error` into `templates/index.html`.
- The error banner is rendered as `<section class="status status-error">{{ error }}</section>`
  and the success banner as `<section class="status status-ok">…</section>`. Tests rely on
  these exact tags — keep them stable.

## Optimizer model notes

- Days are normalized to 3-letter lowercase keys: `mon`, `tue`, `wed`, `thu`, `fri`.
  `_normalize_day` simply truncates to the first three characters of the lowercased
  input, so `"monday"` and `"mon"` both resolve to `mon`.
- Internal timeline is flattened week slots: `absolute_slot = day_index * slots_per_day + slot_in_day`.
- Default `slots_per_day=48` (30-minute buckets across 24 h).
- `slot_length_slots` is the per-block contiguous slot count and is user-configurable from the UI (currently 1 = 30 min, 2 = 1 hour).
- `num_blocks` controls how many non-overlapping office-hour windows are selected.
- Objective is to maximize the number of unique students who can fully attend at least one of the selected blocks (set-cover style). Each student is counted at most once even if they're available for multiple blocks.
- Multi-block search uses `OfficeHoursMultiBlockProblem` (pymoo GA over N candidate-start indices); the decoder sorts the picks and drops any that overlap a previously kept block, so feasibility is enforced at decode time rather than via constraints.
- `optimize_office_hour_slot` (single-block) is preserved for backward compatibility and is used when `num_blocks == 1`.
- The GA is seeded (`seed=1` by default), so optimizer outputs are deterministic across runs — relied on by the test suite.

## Result schema (returned by `optimize_from_records`)

- `blocks`: list of dicts, each with `slot_day`, `start_slot_in_day`, `end_slot_in_day`, `slot_start_index`, `students_covered_in_block`, `available_student_ids`.
- `slot_length_slots`, `num_blocks_requested`, `num_blocks_selected`.
- `students_covered` / `total_students` / `coverage_ratio` are aggregates over the union of all blocks.
- `student_ids`: full sorted list of student IDs seen in input.
- `covered_student_ids`: subset of `student_ids` that are covered by at least one selected block.
- Legacy keys `slot_day`, `start_slot_in_day`, `end_slot_in_day`, `slot_start_index` mirror the first block so older consumers / templates still work.

## CSV export

- `optimize.write_result_csv(result, output_path)` writes one row per block with the
  columns `block_index, day, start_slot, end_slot, students_covered_in_block,
  students_covered_total, total_students, coverage_ratio`. It also has a
  legacy fallback for results that only contain the older flat keys.

## Testing

- Test framework: `pytest` (in `requirements-dev.txt`, not `requirements.txt`).
- Run the full suite from the repo root with `pytest`. With Anaconda Python:
  `& "C:\Users\<user>\anaconda3\python.exe" -m pytest`.
- Test layout:
  - `tests/test_parsers.py` — `_normalize_day`, `_parse_slot`,
    `_parse_time_to_slot`, and the public `parse_*_csv_text` /
    `parse_manual_*` functions.
  - `tests/test_helpers.py` — `build_availability_matrices`, the absolute-slot
    encode/decode helpers, `_count_students_covered`, `_valid_slot_starts`,
    `_decode_block_indices`, `_unique_coverage_mask`.
  - `tests/test_optimizers.py` — `optimize_office_hour_slot`,
    `optimize_office_hour_blocks` (single + multi-block, overlap pruning,
    error paths), end-to-end `optimize_from_records`, and `write_result_csv`.
  - `tests/test_app.py` — Flask `GET /` rendering, successful POST flows
    (manual + CSV upload), manual-textarea-takes-precedence-over-CSV
    behaviour, and all error-path branches in the route.
- Test problem sizes are intentionally tiny (a handful of students, narrow
  teacher windows) so the GA is fast. The full suite runs in ~15 seconds.
- Optimizer assertions check coverage *counts* and non-overlap invariants
  rather than exact `slot_start_index` values when multiple solutions tie,
  to stay robust against pymoo internals changing.

## Important implementation constraints for future LLM edits

- Keep all parsing error messages `ValueError`-based so Flask can show user-facing errors cleanly.
- If you add new accepted CSV schemas, update four things:
  - parser functions in `optimize.py`,
  - help text in `templates/index.html` info panel,
  - parser tests in `tests/test_parsers.py`,
  - sample files in `examples/` if a new schema needs an example.
- Avoid changing route names or field names without updating template names AND tests:
  - `students_csv`, `teachers_csv`, `students_manual`, `teachers_manual`, `slot_length_slots`, `num_blocks`.
- The result schema is consumed by both the Jinja template and the tests; if
  you add or rename keys, update `templates/index.html` and the schema
  assertions in `tests/test_optimizers.py::TestOptimizeFromRecords`.
