from __future__ import annotations

import csv
import datetime
import json
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Generator, Literal, TextIO, Union

CsvSource = Union[str, Path, TextIO]


Day = Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DAYS: tuple[Day, ...] = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


@dataclass(frozen=True)
class Block:
    """One office-hours block on one day.

    Slots are 30-min indices: slot 0 is 00:00, slot 1 is 00:30, ...
    """

    day: Day
    enabled: bool
    start_slot: int
    length_slots: int

    @property
    def end_slot(self) -> int:
        return self.start_slot + self.length_slots


def _slots_per_day(slot_minutes: int) -> int:
    if slot_minutes <= 0 or (24 * 60) % slot_minutes != 0:
        raise ValueError("slot_minutes must evenly divide 1440")
    return (24 * 60) // slot_minutes


def _intervals_contain(day_intervals: list[tuple[int, int]], start: int, end: int) -> bool:
    """Return True if [start,end) is fully contained in union of intervals."""
    for a, b in day_intervals:
        if a <= start and end <= b:
            return True
    return False


def _overlap_len(a0: int, a1: int, b0: int, b1: int) -> int:
    return max(0, min(a1, b1) - max(a0, b0))


def _student_overlap_slots(
    student_intervals: dict[Day, list[tuple[int, int]]],
    blocks: list[Block],
) -> int:
    total = 0
    for bl in blocks:
        if not bl.enabled:
            continue
        for a, b in student_intervals.get(bl.day, []):
            total += _overlap_len(a, b, bl.start_slot, bl.end_slot)
    return total


@contextmanager
def _open_csv_text(path_or_buf: CsvSource) -> Generator[TextIO, None, None]:
    if isinstance(path_or_buf, (str, Path)):
        f = open(path_or_buf, newline="", encoding="utf-8-sig")
        try:
            yield f
        finally:
            f.close()
    else:
        yield path_or_buf


def _norm_csv_row(row: dict[str, str | None]) -> dict[str, str]:
    return {(k or "").strip().lower(): (v or "").strip() for k, v in row.items() if (k or "").strip()}


def _get_field(row: dict[str, str], *names: str) -> str | None:
    for n in names:
        v = row.get(n.lower())
        if v:
            return v
    return None


def _normalize_day(raw: str) -> Day:
    s = raw.strip().lower()
    if len(s) < 3:
        raise ValueError(
            f"Unrecognized day {raw!r}; use a weekday (e.g. mon, tuesday)."
        )
    key = s[:3]
    if key in ("mon", "tue", "wed", "thu", "fri", "sat", "sun"):
        return key  # type: ignore[return-value]
    raise ValueError(
        f"Unrecognized day {raw!r}; use mon–sun or a full weekday name (e.g. Monday)."
    )


def _time_to_slot_boundary(time_str: str, slot_minutes: int) -> int:
    t = datetime.datetime.strptime(time_str.strip(), "%H:%M").time()
    minutes = t.hour * 60 + t.minute
    if minutes % slot_minutes != 0:
        raise ValueError(
            f"Time {time_str!r} is not aligned to {slot_minutes}-minute slots; "
            f"use times on the grid (e.g. 09:00, 09:30)."
        )
    return minutes // slot_minutes


def _interval_from_csv_row(
    row: dict[str, str], *, slot_minutes: int, label: str, line: int
) -> tuple[Day, int, int]:
    d_raw = _get_field(row, "day", "d")
    if not d_raw:
        raise ValueError(f"{label} line {line}: missing 'day'")
    day = _normalize_day(d_raw)
    ss = _get_field(row, "start_slot", "start")
    es = _get_field(row, "end_slot", "end", "stop")
    st = _get_field(row, "start_time", "from")
    en = _get_field(row, "end_time", "to", "until")
    if ss and es:
        a, b = int(ss), int(es)
    elif st and en:
        a, b = _time_to_slot_boundary(st, slot_minutes), _time_to_slot_boundary(en, slot_minutes)
    else:
        raise ValueError(
            f"{label} line {line}: need (start_slot, end_slot) or (start_time, end_time) for day {d_raw!r}."
        )
    if a >= b:
        raise ValueError(
            f"{label} line {line}: start must be strictly before end; got {a=} {b=}"
        )
    return day, a, b


def load_teacher_availability_from_csv(
    path_or_buf: CsvSource, *, slot_minutes: int = 30
) -> dict[Day, list[tuple[int, int]]]:
    """Load teacher open intervals from a CSV (no pre-parsed dict needed).

    Each row: ``day, start_slot, end_slot`` (half-open slot indices), or
    ``day, start_time, end_time`` (``HH:MM`` in 24h, aligned to ``slot_minutes``).
    Multiple rows for the same day are allowed; intervals are not merged.
    """
    out: dict[Day, list[tuple[int, int]]] = {d: [] for d in DAYS}
    with _open_csv_text(path_or_buf) as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("teacher CSV: missing header row")
        for i, row in enumerate(reader, start=2):
            n = _norm_csv_row(row)
            if not any(n.values()):
                continue
            day, a, b = _interval_from_csv_row(
                n, slot_minutes=slot_minutes, label="teacher CSV", line=i
            )
            out[day].append((a, b))
    return out


def load_students_from_csv(path_or_buf: CsvSource, *, slot_minutes: int = 30) -> list[dict[str, Any]]:
    """Load student free-time intervals from a CSV and build ``optimize_office_hours`` input.

    One row per free interval. Columns: ``id`` (or ``student_id``), ``day``,
    and either ``(start_slot, end_slot)`` or ``(start_time, end_time)`` (same
    rules as the teacher file). Rows for the same id are merged.
    """
    by_id: dict[str, dict[Day, list[tuple[int, int]]]] = {}
    with _open_csv_text(path_or_buf) as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("students CSV: missing header row")
        for i, row in enumerate(reader, start=2):
            n = _norm_csv_row(row)
            if not any(n.values()):
                continue
            sid = _get_field(n, "id", "student_id", "student")
            if not sid:
                raise ValueError(f"students CSV line {i}: missing id (use id, student_id, or student).")
            day, a, b = _interval_from_csv_row(
                n, slot_minutes=slot_minutes, label="students CSV", line=i
            )
            stu = by_id.setdefault(
                sid, {d: [] for d in DAYS}
            )
            stu[day].append((a, b))
    return [{"id": sid, "availability": av} for sid, av in by_id.items()]


def optimize_office_hours_from_csv(
    teacher_csv: CsvSource,
    students_csv: CsvSource,
    *,
    slot_minutes: int = 30,
    **kwargs: Any,
) -> dict[str, Any]:
    """Run :func:`optimize_office_hours` after loading the two input CSVs."""
    teacher_availability = load_teacher_availability_from_csv(
        teacher_csv, slot_minutes=slot_minutes
    )
    students = load_students_from_csv(students_csv, slot_minutes=slot_minutes)
    return optimize_office_hours(
        teacher_availability=teacher_availability,
        students=students,
        slot_minutes=slot_minutes,
        **kwargs,
    )


def optimize_office_hours(
    *,
    teacher_availability: dict[Day, list[tuple[int, int]]],
    students: list[dict[str, Any]],
    slot_minutes: int = 30,
    min_block_minutes: int = 30,
    max_block_minutes: int = 180,
    max_blocks_per_week: int = 7,
    weights: dict[str, float] | None = None,
    seed: int = 1,
    n_generations: int = 200,
    pop_size: int = 200,
) -> dict[str, Any]:
    """Optimize office-hours blocks using pymoo.

    Inputs
    - teacher_availability: {day: [(start_slot, end_slot), ...]} (slots are 30-min indices)
    - students: list of dicts with at least:
        - "id": str
        - "availability": {day: [(start_slot, end_slot), ...]} (same slot units)

    Decision variables (per day)
    - enabled (0/1)
    - start_slot (int)
    - length_slots (int) in [min,max]

    Hard constraint
    - If enabled, each block must be fully within teacher availability for that day.

    Objective (weighted, maximized)
    - coverage: number of students with >=1 slot overlap
    - overlap: total overlap slots across all students
    - fairness: minimum overlap slots across students (raise the floor)

    We maximize the weighted sum; pymoo minimizes, so we return negative.
    """

    try:
        from pymoo.core.problem import ElementwiseProblem
        from pymoo.optimize import minimize
        from pymoo.core.variable import Integer, Binary
        from pymoo.algorithms.soo.nonconvex.ga import GA
        from pymoo.operators.sampling.rnd import MixedVariableSampling
        from pymoo.operators.crossover.sbx import SBX
        from pymoo.operators.mutation.pm import PM
        from pymoo.operators.repair.rounding import RoundingRepair
        from pymoo.termination import get_termination
        from pymoo.core.mixed import MixedVariableMating
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "pymoo is required. Install dependencies (pip install -r requirements.txt)."
        ) from e

    w = {
        "coverage": 1.0,
        "overlap": 0.25,
        "fairness": 1.0,
        "blocks_penalty": 0.5,
    }
    if weights:
        w.update(weights)

    slots_day = _slots_per_day(slot_minutes)
    min_len = max(1, min_block_minutes // slot_minutes)
    max_len = max(1, max_block_minutes // slot_minutes)
    if min_len > max_len:
        raise ValueError("min_block_minutes cannot exceed max_block_minutes")

    for day in DAYS:
        teacher_availability.setdefault(day, [])

    if any("availability" not in s for s in students):
        raise ValueError('Each student must include an "availability" field')

    # Variable schema: for each day: enabled, start, length
    var_names: list[str] = []
    vars_dict: dict[str, Any] = {}
    for day in DAYS:
        v_en = f"{day}_en"
        v_st = f"{day}_start"
        v_ln = f"{day}_len"
        var_names.extend([v_en, v_st, v_ln])
        vars_dict[v_en] = Binary()
        vars_dict[v_st] = Integer(bounds=(0, slots_day - 1))
        vars_dict[v_ln] = Integer(bounds=(min_len, max_len))

    def decode(x: dict[str, int]) -> list[Block]:
        blocks: list[Block] = []
        for day in DAYS:
            en = bool(int(x[f"{day}_en"]))
            st = int(x[f"{day}_start"])
            ln = int(x[f"{day}_len"])
            # Clip end-of-day overflow (still must satisfy teacher constraint)
            if st + ln > slots_day:
                ln = max(1, slots_day - st)
            blocks.append(Block(day=day, enabled=en, start_slot=st, length_slots=ln))
        return blocks

    class OfficeHoursProblem(ElementwiseProblem):
        def __init__(self) -> None:
            super().__init__(
                vars=vars_dict,
                n_obj=1,
                n_ieq_constr=1,
            )

        def _evaluate(self, x: dict[str, int], out: dict[str, Any], *args: Any, **kwargs: Any) -> None:
            blocks = decode(x)

            # Hard constraint: all enabled blocks must be within teacher availability
            violations = 0
            enabled_blocks = 0
            for bl in blocks:
                if not bl.enabled:
                    continue
                enabled_blocks += 1
                if not _intervals_contain(teacher_availability.get(bl.day, []), bl.start_slot, bl.end_slot):
                    violations += 1

            # Soft preference: avoid too many blocks in a week (since you said "can be different each day")
            blocks_over = max(0, enabled_blocks - max_blocks_per_week)

            overlaps: list[int] = []
            covered = 0
            total_overlap = 0
            for s in students:
                ov = _student_overlap_slots(s["availability"], blocks)
                overlaps.append(ov)
                total_overlap += ov
                if ov > 0:
                    covered += 1

            min_overlap = min(overlaps) if overlaps else 0

            score = (
                w["coverage"] * covered
                + w["overlap"] * total_overlap
                + w["fairness"] * min_overlap
                - w["blocks_penalty"] * blocks_over
            )

            out["F"] = [-float(score)]
            out["G"] = [float(violations)]

    problem = OfficeHoursProblem()

    algorithm = GA(
        pop_size=pop_size,
        sampling=MixedVariableSampling(),
        mating=MixedVariableMating(
            elimination_duplicates=True,
            crossover=SBX(eta=15, prob=0.9, repair=RoundingRepair()),
            mutation=PM(eta=20, prob=None, repair=RoundingRepair()),
        ),
        eliminate_duplicates=True,
    )

    res = minimize(
        problem,
        algorithm,
        termination=get_termination("n_gen", n_generations),
        seed=seed,
        verbose=False,
    )

    if res.X is None:
        raise RuntimeError("Optimization failed to produce a solution.")

    best_blocks = decode(res.X)
    best_blocks = [b for b in best_blocks if b.enabled]

    per_student = []
    for s in students:
        ov_slots = _student_overlap_slots(s["availability"], best_blocks)
        per_student.append(
            {
                "id": s.get("id"),
                "overlap_slots": ov_slots,
                "overlap_minutes": ov_slots * slot_minutes,
                "covered": ov_slots > 0,
            }
        )

    output = {
        "slot_minutes": slot_minutes,
        "blocks": [
            {
                "day": b.day,
                "start_slot": b.start_slot,
                "end_slot": b.end_slot,
                "length_slots": b.length_slots,
                "start_minutes": b.start_slot * slot_minutes,
                "end_minutes": b.end_slot * slot_minutes,
                "length_minutes": b.length_slots * slot_minutes,
            }
            for b in best_blocks
        ],
        "objective": {
            "weighted_score": -float(res.F[0]),
            "weights": w,
        },
        "per_student": per_student,
    }
    return output


def export_blocks_csv(result: dict[str, Any], path: str) -> None:
    """Export chosen blocks to a simple CSV for debugging."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "day",
                "start_minutes",
                "end_minutes",
                "length_minutes",
                "start_slot",
                "end_slot",
                "length_slots",
            ],
        )
        w.writeheader()
        for row in result.get("blocks", []):
            w.writerow({k: row.get(k) for k in w.fieldnames})


def export_result_json(result: dict[str, Any], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)


if __name__ == "__main__":  # minimal local smoke-runner (CSV or inline)
    import sys

    _here = Path(__file__).resolve().parent
    _default_teacher = _here / "schedules" / "teacher_availability.csv"
    _default_students = _here / "schedules" / "students_availability.csv"

    if len(sys.argv) >= 3:
        res = optimize_office_hours_from_csv(
            sys.argv[1],
            sys.argv[2],
            weights={"coverage": 1.0, "overlap": 0.2, "fairness": 0.8},
            n_generations=150,
            pop_size=150,
            seed=2,
        )
    elif _default_teacher.is_file() and _default_students.is_file():
        res = optimize_office_hours_from_csv(
            _default_teacher,
            _default_students,
            weights={"coverage": 1.0, "overlap": 0.2, "fairness": 0.8},
            n_generations=150,
            pop_size=150,
            seed=2,
        )
    else:
        teacher = {
            "mon": [(18, 24)],
            "tue": [(26, 32)],
            "wed": [(18, 24)],
            "thu": [(26, 32)],
            "fri": [(18, 24)],
            "sat": [],
            "sun": [],
        }
        students_in = [
            {"id": "s1", "availability": {"mon": [(20, 22)], "wed": [(18, 20)]}},
            {"id": "s2", "availability": {"tue": [(26, 30)]}},
            {"id": "s3", "availability": {"thu": [(28, 32)], "fri": [(18, 19)]}},
        ]
        res = optimize_office_hours(
            teacher_availability=teacher,
            students=students_in,
            weights={"coverage": 1.0, "overlap": 0.2, "fairness": 0.8},
            n_generations=150,
            pop_size=150,
            seed=2,
        )
    print(json.dumps(res, indent=2))
