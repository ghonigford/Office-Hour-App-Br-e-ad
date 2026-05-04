## Do

- Use Python 3.11, Flask (`app.py`, `gunicorn` in production via the
  multi-stage `Dockerfile`).
- Use `pymoo` for schedule search ([`requirements.txt`](requirements.txt)).
- Keep `optimize.py` as the canonical parsing + optimization pipeline.
- Prefer adding small pure functions in `optimize.py` over spreading CSV
  parsing logic in routes.
- Use the React + TypeScript SPA in `frontend/` for all UI work. Build with
  `npm run build` (Vite). Local dev: `npm run dev` proxies `/api` to Flask.
- Add types to `frontend/src/types.ts` when extending the result schema, and
  match the field names returned by `optimize_from_records[_v2]`.
- Keep both the **legacy** and **v2** parsing/optimization stacks working.
  The v2 stack (weighted hard/soft availability + multiple teachers) is a
  strict superset.

## Don't

- Delete the entire code base.
- Bake test-only dependencies (e.g. `pytest`) into `requirements.txt` —
  those belong in `requirements-dev.txt` so the production image stays small.
- Change route names without also updating `frontend/src/lib/api.ts` and the
  affected tests.
- Re-introduce a Jinja `templates/index.html` for the main UI — the SPA in
  `frontend/dist/index.html` is now the only HTML the browser loads. Do
  embed inline scripts in the SPA's static `frontend/index.html` only for
  the pre-paint theme guard (no Jinja anywhere — Vite serves this verbatim).

## Project structure

- `app.py` --> Flask. Exposes `POST /api/optimize`, `GET /api/share/<token>`,
  serves the SPA shell at `/` and `/r/<token>`, and serves built assets
  from `frontend/dist/`.
- `optimize.py` --> parsing, availability matrices, pymoo optimization.
  Contains the legacy boolean stack and a parallel v2 stack with float
  weights and multi-teacher support. **Untouched** by the SPA rewrite.
- `Dockerfile` --> multi-stage: Node 20 builds the React SPA, Python 3.11
  runs gunicorn with the built `dist/` baked in.
- `render.yaml` --> Render config; uses `runtime: docker`.
- `frontend/` --> React 18 + TypeScript + Vite + Tailwind CSS SPA.
  - `frontend/package.json`, `vite.config.ts`, `tsconfig*.json`,
    `tailwind.config.ts`, `postcss.config.js` --> build config.
  - `frontend/index.html` --> static shell. Contains a pre-paint inline
    script that applies the persisted/system dark-mode class before React
    hydrates, to avoid the light-mode flash.
  - `frontend/public/favicon.svg` --> favicon (copied to `dist/` by Vite).
  - `frontend/src/main.tsx` --> mounts `<App />`.
  - `frontend/src/App.tsx` --> top-level shell. Detects `/r/<token>` paths
    client-side (no router lib; a regex on `window.location.pathname`
    decides editor-vs-share-view).
  - `frontend/src/types.ts` --> shared types (`OptimizeResult`,
    `OptimizeRequest`, `EntityState`, `Settings`, etc.). Mirrors the
    server's v2 result schema.
  - `frontend/src/state/editor.tsx` --> reducer + React Context for the
    main editor (settings, students, teachers, paint mode/strength, CSV
    inputs). Centralised dispatch keeps grid painting batched.
  - `frontend/src/state/theme.ts` --> persisted dark/light hook
    (`localStorage` key `oh.theme`).
  - `frontend/src/state/toast.tsx` --> tiny toast queue (`useToast`).
  - `frontend/src/lib/api.ts` --> `runOptimize` / `fetchSharedResult`.
  - `frontend/src/lib/slots.ts` --> slot-index helpers, weight lookup, and
    the contiguous-run compressor that turns the editor grid into v2 rows.
  - `frontend/src/components/` --> UI pieces:
    - `Header.tsx`, `SettingsCard.tsx`, `RunCard.tsx`, `Heatmap.tsx`,
    - `StudentEditor.tsx`, `TeacherEditor.tsx`,
    - `CalendarGrid.tsx` (the click-and-drag primitive),
    - `PaintControls.tsx`, `EntitySelector.tsx`, `CsvUploader.tsx`,
    - `ResultPanel.tsx`, `ResultCalendar.tsx`, `UncoveredStudents.tsx`,
    - `ShareBanner.tsx`, `ShareView.tsx`,
    - `Modal.tsx`, `Tabs.tsx`, `ToastViewport.tsx`.
- `examples/` --> sample input CSVs.
- `legacy/` --> code kept for reference, not part of the live app.
- `docs/` --> historical / non-code documentation.
- `tests/` --> pytest suite (parsers, helpers, optimizers, Flask JSON API).
- `pytest.ini`, `conftest.py` --> pytest config + rootdir anchor.
- `requirements.txt` / `requirements-dev.txt` --> runtime deps and the
  test-only add-on (`pytest`).

## Input formats currently supported

### Legacy (boolean availability, single teacher)

- Student slot CSV: `id,day,start_slot,end_slot`
  - Example row: `s1,mon,20,22`
- Teacher slot CSV: `day,start_slot,end_slot`
  - Example row: `mon,18,24`
- Student wide template CSV is also supported for parsing:
  - `student,Monday_start,Monday_end,Tuesday_start,Tuesday_end,Wednesday_start,Wednesday_end,Thursday_start,Thursday_end,Friday_start,Friday_end`
  - Times must be `HH:MM` and map to slots from midnight. With the default
    30-minute granularity, `09:00 -> slot 18`.
- Manual textarea input mirrors the slot CSV row format (one row per line, no header).

### v2 (weighted hard/soft availability, multi-teacher)

- Student slot CSV: `id,day,start_slot,end_slot[,strength]`
  - Example row: `s1,mon,20,22,hard` or `s1,mon,22,24,soft`
  - `strength` is `hard` or `soft` (case-insensitive). Missing/blank defaults to `hard`.
- Teacher slot CSV: `[teacher_id,]day,start_slot,end_slot[,strength]`
  - Example rows:
    - `mon,18,24` (legacy 3-column form, treated as a single anonymous
      teacher with `hard` strength)
    - `prof1,mon,18,24` (multi-teacher with `hard` default)
    - `prof2,tue,20,30,soft` (full v2 form)
- Manual textareas accept all of these column counts (3, 4, or 5 fields per
  line); fewer-column rows are zero-padded with the legacy defaults.
- The wide student template does **not** support per-cell strength — it always
  parses as `hard`.

### Hard vs soft semantics

- Per slot, every entity (student or teacher) has one of three weights:
  `1.0` (hard), `0.5` (soft), or `0.0` (unavailable).
- For a given block (a contiguous run of `slot_length_slots` slots) and a
  `(student, host)` pair, the **block score** is the elementwise minimum
  across the block's slots of `min(student_weight, host_weight)`.
- Each student's contribution to a schedule is the **max** of their per-block
  scores across all kept blocks. The optimizer maximises the sum of those
  contributions.
- Concretely: hard student in a hard host block = 1.0; either side soft = 0.5;
  any zero = 0.0.

## Flask behavior notes

- `app.py` exposes:
  - `GET /` and `GET /r/<token>` --> serve `frontend/dist/index.html` (or a
    "frontend not built" placeholder if `dist/` doesn't exist yet).
  - `GET /favicon.svg`, `GET /assets/<path>` --> serve from
    `frontend/dist/`.
  - `POST /api/optimize` --> takes JSON, returns `{result, share_token}` on
    success or `{error}` with HTTP 400 on validation failure.
  - `GET /api/share/<token>` --> returns `{result}` for a previously-issued
    share token, or HTTP 404.
- Server-side request size cap: `MAX_CONTENT_LENGTH = 5 MB`.
- `POST /api/optimize` JSON body shape:

  ```jsonc
  {
    "settings": {
      "slot_minutes": 30,        // 15 | 30 | 60
      "day_start_hour": 8,
      "day_end_hour": 20,
      "num_teachers": 1,         // 1..10
      "slot_length_slots": 2,
      "num_blocks": 1            // 1..20
    },
    "students": {
      "rows_v2": [["s1", "mon", 18, 22, "hard"], ...],
      // OR (mutually exclusive):
      "csv_text": "id,day,start_slot,end_slot,strength\n..."
    },
    "teachers": { /* same shape */ }
  }
  ```

- Pipeline routing in `_run_optimize_from_json`: when the request looks
  legacy-shaped (default 30-min slots, 1 teacher, all-hard rows for both
  sides) it calls `optimize_from_records` so legacy result keys are
  produced. Otherwise it calls `optimize_from_records_v2`. The SPA does
  not care which one ran — both produce a superset of the same schema.
- Share-token format is **unchanged** (gzip + URL-safe base64 of the
  JSON-serialized result), so existing `/r/<token>` URLs out in the wild
  keep working. The decode happens in `GET /api/share/<token>` and the SPA
  renders the read-only view from that JSON.
- The SPA detects the read-only mode itself by matching
  `^/r/([^/]+)/?$` against `window.location.pathname` in `App.tsx`.

## Optimizer model notes

### Shared (legacy + v2)

- Days are normalized to 3-letter lowercase keys: `mon`, `tue`, `wed`, `thu`, `fri`.
  `_normalize_day` simply truncates to the first three characters of the lowercased
  input, so `"monday"` and `"mon"` both resolve to `mon`.
- Internal timeline is flattened week slots: `absolute_slot = day_index * slots_per_day + slot_in_day`.
- Default `slots_per_day=48` (30-minute buckets across 24 h). The v2 pipeline
  also accepts `slots_per_day=96` (15-min) and `slots_per_day=24` (60-min);
  the legacy pipeline always uses 48.
- `slot_length_slots` is the per-block contiguous slot count.
- `num_blocks` controls how many non-overlapping office-hour windows are selected.
- The GA is seeded (`seed=1` by default), so optimizer outputs are deterministic across runs — relied on by the test suite.

### Legacy single-teacher boolean stack

- Objective is to maximize the number of unique students who can fully attend at least one of the selected blocks (set-cover style). Each student is counted at most once even if they're available for multiple blocks.
- Multi-block search uses `OfficeHoursMultiBlockProblem` (pymoo GA over N candidate-start indices); the decoder sorts the picks and drops any that overlap a previously kept block, so feasibility is enforced at decode time rather than via constraints.
- `optimize_office_hour_slot` (single-block) is preserved for backward compatibility and is used when `num_blocks == 1`.

### v2 multi-teacher weighted stack

- `OfficeHoursWeightedMultiTeacherProblem` is the pymoo problem; decision
  vector is interleaved `[start_idx_0, host_idx_0, start_idx_1, host_idx_1, ...]`
  of length `2 * num_blocks`.
- `_decode_multi_teacher_picks` drops infeasible picks (host unavailable at
  the chosen start), de-duplicates, and prunes overlap **globally regardless
  of host** (a student can only be in one place at a time).
- Objective is the negative of `sum(_aggregate_weighted_coverage(...))` — i.e.
  the optimizer maximises the sum across students of their best per-block
  weighted score.
- `optimize_weighted_multi_teacher` is the lower-level entry point; it expects
  a float student matrix and a `{teacher_id: float vector}` dict.
- `optimize_from_records_v2` is the end-to-end entry point used by the Flask
  route. It accepts v2-format rows
  `[(student_id, day, start, end, strength), ...]` and
  `[(teacher_id, day, start, end, strength), ...]`.

## Result schema

### `optimize_from_records` (legacy)

- `blocks`: list of dicts, each with `slot_day`, `start_slot_in_day`, `end_slot_in_day`, `slot_start_index`, `students_covered_in_block`, `available_student_ids`.
- `slot_length_slots`, `num_blocks_requested`, `num_blocks_selected`.
- `students_covered` / `total_students` / `coverage_ratio` are aggregates over the union of all blocks.
- `student_ids`: full sorted list of student IDs seen in input.
- `covered_student_ids`: subset of `student_ids` that are covered by at least one selected block.
- Legacy keys `slot_day`, `start_slot_in_day`, `end_slot_in_day`, `slot_start_index` mirror the first block so older consumers / templates still work.

### `optimize_from_records_v2` (extends the legacy schema)

Everything the legacy schema returns, **plus**:

- Per-block additions:
  - `host`: teacher id assigned to host this block.
  - `students_covered_hard` / `students_covered_soft`: counts split by the
    block's per-student score (hard = 1.0, soft = 0.5).
  - `weighted_coverage`: sum of per-student scores for this block.
  - `hard_student_ids` / `soft_student_ids`: the ids behind the counts above.
- Top-level additions:
  - `slots_per_day`: granularity used for this run (24, 48, or 96).
  - `weighted_coverage`: sum of per-student best scores across the schedule.
  - `weighted_coverage_ratio`: `weighted_coverage / total_students`.
  - `students_covered_hard` / `students_covered_any`: hard-coverage and
    any-coverage counts (the latter equals `students_covered`).
  - `hard_coverage_ratio`.
  - `hard_student_ids`: students with at least one hard block in their best
    schedule.
  - `uncovered_student_ids`: complement of `covered_student_ids` against
    `student_ids`. Powers the uncovered-students panel.
  - `teacher_ids`: sorted list of teacher ids seen in input.
  - `student_availability` / `teacher_availability`: mapping of
    `entity_id -> [{day, start_slot, end_slot, strength}, ...]`, sorted by
    `(day_index, start_slot)`. Used by the read-only share view to render
    each student's / teacher's availability without re-shipping the matrix.
  - `per_student_best_score`: list of floats indexed by `student_ids`.

## CSV export

- `optimize.write_result_csv(result, output_path)` writes one row per block with the
  columns `block_index, day, start_slot, end_slot, students_covered_in_block,
  students_covered_total, total_students, coverage_ratio`. It also has a
  legacy fallback for results that only contain the older flat keys. The
  writer accepts both legacy and v2 result dicts because v2 keeps the
  legacy block keys populated.

## Share links

- `app._encode_share_token(result)` returns a URL-safe base64-encoded gzipped
  JSON of the result dict. `_decode_share_token(token)` is the inverse and
  raises `ValueError` on any decode failure.
- Tokens are stateless — there is no server-side store, which means they are
  immune to Render's ephemeral disk on free tier.
- Tokens scale roughly with result size: typical 10-student / 2-block runs
  produce a 200 B–2 KB token.

## UI / SPA notes

- The SPA layout (top to bottom): `Header` (with theme toggle + Help modal),
  any in-flight error, the `ResultPanel` (only after a successful run), the
  `UncoveredStudents` panel, `SettingsCard`, the side-by-side
  `StudentEditor` + `TeacherEditor`, the `RunCard`, the live `Heatmap`,
  and a small footer.
- `CalendarGrid` is the click-and-drag primitive shared by both editors.
  - Cells are 3-state (empty / `hard` / `soft`); active paint strength is
    chosen via a pill toggle in `PaintControls`.
  - Drag is implemented with `mousedown` on the entry cell + `mouseenter`
    on subsequent cells; a single drag flushes a batch of `paint_cells`
    actions per `requestAnimationFrame` frame for perf. A drag that starts
    on a cell already matching the paint strength erases instead.
- Each entity has an "Input mode" pill toggle (`available` /
  `unavailable`). In `unavailable` mode, the calendar's painted cells
  represent busy time; everything else inside the day window is treated as
  `hard` available. The conversion happens in
  `frontend/src/lib/slots.ts::compressEntityRows` which is what builds the
  `rows_v2` array sent to `POST /api/optimize`.
- `SettingsCard` exposes `slot_minutes` (15 / 30 / 60), day-window
  start/end hours, and `num_teachers` (1–10). The reducer clears cells
  whose slot index no longer fits the new resolution when granularity
  changes (`migrateCellsToGranularity`).
- `Heatmap` re-renders on every grid edit. It shows the count of students
  free in each slot, masked by the union of teacher availability.
- `ResultPanel` shows summary stats, a per-block list with hosts, a
  "View result calendar" button that opens `ResultCalendar` in a `Modal`,
  and the `ShareBanner` with the absolute `/r/<token>` URL + Copy button.
- `UncoveredStudents` renders when `result.uncovered_student_ids` is
  non-empty.
- Read-only share view: when the URL matches `^/r/<token>/?$` the SPA
  bypasses the editor entirely and renders only `ResultPanel` +
  `UncoveredStudents` populated from `GET /api/share/<token>`.
- Theme: the `useTheme` hook stores the user's choice under `oh.theme` in
  localStorage. The static `frontend/index.html` has an inline pre-paint
  script that applies `class="dark"` to `<html>` before React hydrates so
  there's no light-mode flash for dark-mode users.

## Testing

- Test framework: `pytest` (in `requirements-dev.txt`, not `requirements.txt`).
- Run the full suite from the repo root with `pytest`. With Anaconda Python:
  `& "C:\Users\<user>\anaconda3\python.exe" -m pytest`.
- Test layout:
  - `tests/test_parsers.py` — `_normalize_day`, `_parse_slot`,
    `_parse_time_to_slot`, `_parse_strength`, the legacy
    `parse_*_csv_text` / `parse_manual_*` functions, and the v2 variants
    (`parse_*_csv_text_v2`, `parse_manual_*_v2`).
  - `tests/test_helpers.py` — matrix builders, slot encode/decode,
    coverage helpers.
  - `tests/test_optimizers.py` — pymoo-driven end-to-end optimization
    tests for `optimize_office_hour_slot`, `optimize_office_hour_blocks`,
    `optimize_weighted_multi_teacher`, `optimize_from_records`,
    `optimize_from_records_v2`, and `write_result_csv`.
  - `tests/test_app.py` — Flask JSON API tests:
    `POST /api/optimize` happy paths (legacy + v2 + multi-teacher +
    15/60-min granularities + CSV-text input), source precedence
    (`rows_v2` over `csv_text`), all validation error paths (returns
    HTTP 400 with `{"error": "..."}`), `_normalize_rows` unit tests,
    share-token round-trip via `GET /api/share/<token>`, SPA shell
    routes (`GET /`, `GET /r/<token>`), and static-asset routes
    (`/favicon.svg`, `/assets/<path>`) using `monkeypatch` against
    `app.FRONTEND_DIST` so the tests pass whether or not the frontend
    has been built locally.
- The full suite is **226 tests** and runs in ~45 seconds.
- Test problem sizes are intentionally tiny (a handful of students, narrow
  teacher windows) so the GA is fast.
- Optimizer assertions check coverage *counts* and non-overlap invariants
  rather than exact `slot_start_index` values when multiple solutions tie,
  to stay robust against pymoo internals changing.

## Frontend dev workflow

- Two terminals for fast iteration:
  - `python app.py` (Flask on `:5000`).
  - `cd frontend && npm run dev` (Vite on `:5173`, proxies `/api` to Flask).
  - Open <http://localhost:5173>.
- Full single-server check: `cd frontend && npm run build && cd .. && python app.py`,
  then open <http://localhost:5000>.
- Type-check only: `cd frontend && npm run lint` (`tsc --noEmit`).
- Production build: `cd frontend && npm run build`. Output goes to
  `frontend/dist/` which is what Flask serves and what the Dockerfile
  copies into the runtime image.

## Important implementation constraints for future LLM edits

- Keep all parsing error messages `ValueError`-based so Flask can surface
  them via the `{"error": "..."}` JSON shape.
- If you add new accepted CSV schemas, update four things:
  - parser functions in `optimize.py` (and their v2 counterparts when
    relevant),
  - the help modal copy in `frontend/src/components/Header.tsx`,
  - parser tests in `tests/test_parsers.py`,
  - sample files in `examples/` if a new schema needs an example.
- Don't rename API endpoints without also updating
  `frontend/src/lib/api.ts`. Current surface:
  - `POST /api/optimize`
  - `GET /api/share/<token>`
  - `GET /` and `GET /r/<token>` (SPA shell)
  - `GET /assets/<path>`, `GET /favicon.svg`
- The SPA's editor reducer state shape is in
  `frontend/src/state/editor.tsx`. If you add a new setting, plumb it
  through `Settings`, `INITIAL_STATE`, the `set_settings` action, the
  `SettingsCard` form, and the API request body in `App.tsx::runScheduler`.
- The result schema is consumed by both the SPA (`frontend/src/types.ts`)
  and the optimizer tests; if you add or rename keys in `optimize.py`,
  update both.
- The share-link round trip relies on the v2 result being JSON-serializable.
  Don't put `numpy` arrays or other non-JSON types into the v2 result dict;
  cast to `int`, `float`, or `list` at the boundary in `optimize.py`.
- Tailwind v3.4: don't combine `dark:hover:` with arbitrary opacity
  modifiers (e.g. `dark:hover:bg-foo/40`) inside `@apply` directives —
  Tailwind's `@apply` parser rejects that. Use a regular `.dark .x:hover`
  selector instead, as is done in `frontend/src/index.css` for the grid
  cell hover states.
