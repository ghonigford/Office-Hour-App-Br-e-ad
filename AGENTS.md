## Do

- use Python, Flask (`app.py`, `gunicorn` in production if configured in `render.yaml`)
- `pymoo` for schedule search ([`requirements.txt`](requirements.txt))
- keep `optimize.py` as the canonical parsing + optimization pipeline used by Flask
- prefer adding small pure functions in `optimize.py` over spreading CSV parsing logic in routes

## Don't

- delete the entire code base 

## Project structure

- app.py and render.yaml --> set up website
- optimize.py --> pymoo and optimize
- ai_final.py --> obtains student schedules (input)

## Input formats currently supported

- Student slot CSV: `id,day,start_slot,end_slot`
  - Example row: `s1,mon,20,22`
- Teacher slot CSV: `day,start_slot,end_slot`
  - Example row: `mon,18,24`
- Student wide template CSV is also supported for parsing:
  - `student,Monday_start,Monday_end,Tuesday_start,Tuesday_end,Wednesday_start,Wednesday_end,Thursday_start,Thursday_end,Friday_start,Friday_end`
  - Times must be `HH:MM` and currently map to 30-minute slots from midnight (e.g. `09:00 -> slot 18`)

## Flask behavior notes

- `app.py` route `/` supports both `GET` and `POST`.
- POST source precedence:
  - students: use `students_manual` textarea if non-empty; else use `students_csv` upload
  - teachers: use `teachers_manual` textarea if non-empty; else use `teachers_csv` upload
- The route passes `result` or `error` into `templates/index.html`.

## Optimizer model notes

- Days are normalized to 3-letter lowercase keys: `mon`, `tue`, `wed`, `thu`, `fri`.
- Internal timeline is flattened week slots: `absolute_slot = day_index * slots_per_day + slot_in_day`.
- Default `slots_per_day=48` (30-minute buckets across 24h).
- `slot_length_slots` is the per-block contiguous slot count and is user-configurable from the UI (currently 1 = 30 min, 2 = 1 hour).
- `num_blocks` controls how many non-overlapping office-hour windows are selected.
- Objective is to maximize the number of unique students who can fully attend at least one of the selected blocks (set-cover style). Each student is counted at most once even if they're available for multiple blocks.
- Multi-block search uses `OfficeHoursMultiBlockProblem` (pymoo GA over N candidate-start indices); the decoder sorts the picks and drops any that overlap a previously kept block, so feasibility is enforced at decode time rather than via constraints.
- `optimize_office_hour_slot` (single-block) is preserved for backward compatibility and is used when `num_blocks == 1`.

## Result schema (returned by `optimize_from_records`)

- `blocks`: list of dicts, each with `slot_day`, `start_slot_in_day`, `end_slot_in_day`, `slot_start_index`, `students_covered_in_block`, `available_student_ids`.
- `slot_length_slots`, `num_blocks_requested`, `num_blocks_selected`.
- `students_covered` / `total_students` / `coverage_ratio` are aggregates over the union of all blocks.
- Legacy keys `slot_day`, `start_slot_in_day`, `end_slot_in_day`, `slot_start_index` mirror the first block so older consumers / templates still work.

## Important implementation constraints for future LLM edits

- Keep all parsing error messages `ValueError`-based so Flask can show user-facing errors cleanly.
- If you add new accepted CSV schemas, update both:
  - parser functions in `optimize.py`
  - help text in `templates/index.html` info panel
- Avoid changing route names or field names without updating template names:
  - `students_csv`, `teachers_csv`, `students_manual`, `teachers_manual`, `slot_length_slots`, `num_blocks`