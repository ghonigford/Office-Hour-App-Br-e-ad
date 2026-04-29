from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

import numpy as np
from pymoo.algorithms.soo.nonconvex.ga import GA
from pymoo.core.problem import ElementwiseProblem
from pymoo.optimize import minimize

DAY_ORDER = ("mon", "tue", "wed", "thu", "fri")
DAY_TO_IDX = {day: idx for idx, day in enumerate(DAY_ORDER)}


def _normalize_day(raw_day: str) -> str:
    normalized = raw_day.strip().lower()[:3]
    if normalized not in DAY_TO_IDX:
        raise ValueError(f"Unsupported day value: '{raw_day}'")
    return normalized


def _parse_slot(raw_slot: str) -> int:
    try:
        slot = int(raw_slot)
    except ValueError as exc:
        raise ValueError(f"Invalid slot value: '{raw_slot}'") from exc
    if slot < 0:
        raise ValueError("Slot values must be non-negative integers.")
    return slot


def _parse_time_to_slot(raw_time: str, slot_minutes: int = 30) -> int:
    parts = raw_time.strip().split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid HH:MM time: '{raw_time}'")
    hour, minute = int(parts[0]), int(parts[1])
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise ValueError(f"Invalid HH:MM time: '{raw_time}'")
    total_minutes = hour * 60 + minute
    if total_minutes % slot_minutes != 0:
        raise ValueError(f"Time '{raw_time}' does not align with {slot_minutes}-minute slots.")
    return total_minutes // slot_minutes


def _parse_student_slot_rows(rows: list[dict[str, str]]) -> list[tuple[str, str, int, int]]:
    parsed: list[tuple[str, str, int, int]] = []
    for row in rows:
        student_id = row.get("id", "").strip()
        if not student_id:
            raise ValueError("Student row is missing 'id'.")
        day = _normalize_day(row.get("day", ""))
        start = _parse_slot(row.get("start_slot", ""))
        end = _parse_slot(row.get("end_slot", ""))
        if start >= end:
            raise ValueError(f"Student row has start >= end for '{student_id}'.")
        parsed.append((student_id, day, start, end))
    return parsed


def _parse_teacher_slot_rows(rows: list[dict[str, str]]) -> list[tuple[str, int, int]]:
    parsed: list[tuple[str, int, int]] = []
    for row in rows:
        day = _normalize_day(row.get("day", ""))
        start = _parse_slot(row.get("start_slot", ""))
        end = _parse_slot(row.get("end_slot", ""))
        if start >= end:
            raise ValueError("Teacher row has start_slot >= end_slot.")
        parsed.append((day, start, end))
    return parsed


def _read_csv_dicts_from_text(csv_text: str) -> list[dict[str, str]]:
    text = csv_text.strip()
    if not text:
        return []
    return list(csv.DictReader(io.StringIO(text)))


def parse_student_csv_text(csv_text: str) -> list[tuple[str, str, int, int]]:
    rows = _read_csv_dicts_from_text(csv_text)
    if not rows:
        return []

    headers = {h.strip() for h in rows[0].keys()}
    slot_headers = {"id", "day", "start_slot", "end_slot"}
    wide_headers = {"student", "Monday_start", "Monday_end", "Tuesday_start", "Tuesday_end", "Wednesday_start", "Wednesday_end", "Thursday_start", "Thursday_end", "Friday_start", "Friday_end"}

    if slot_headers.issubset(headers):
        return _parse_student_slot_rows(rows)
    if wide_headers.issubset(headers):
        parsed: list[tuple[str, str, int, int]] = []
        for row in rows:
            student_id = row.get("student", "").strip()
            if not student_id:
                continue
            for day_key, day_short in (("Monday", "mon"), ("Tuesday", "tue"), ("Wednesday", "wed"), ("Thursday", "thu"), ("Friday", "fri")):
                start_raw = row.get(f"{day_key}_start", "").strip()
                end_raw = row.get(f"{day_key}_end", "").strip()
                if not start_raw and not end_raw:
                    continue
                if not start_raw or not end_raw:
                    raise ValueError(f"Incomplete time range for '{student_id}' on {day_key}.")
                start = _parse_time_to_slot(start_raw)
                end = _parse_time_to_slot(end_raw)
                if start >= end:
                    raise ValueError(f"Invalid time range for '{student_id}' on {day_key}.")
                parsed.append((student_id, day_short, start, end))
        return parsed

    raise ValueError(
        "Student CSV must use either 'id,day,start_slot,end_slot' or the wide template with Monday-Friday start/end columns."
    )


def parse_teacher_csv_text(csv_text: str) -> list[tuple[str, int, int]]:
    rows = _read_csv_dicts_from_text(csv_text)
    if not rows:
        return []
    headers = {h.strip() for h in rows[0].keys()}
    required = {"day", "start_slot", "end_slot"}
    if not required.issubset(headers):
        raise ValueError("Teacher CSV must use headers: day,start_slot,end_slot")
    return _parse_teacher_slot_rows(rows)


def parse_manual_students(text: str) -> list[tuple[str, str, int, int]]:
    rows: list[dict[str, str]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = [part.strip() for part in line.split(",")]
        if len(parts) != 4:
            raise ValueError("Each student manual row must be: id,day,start_slot,end_slot")
        rows.append({"id": parts[0], "day": parts[1], "start_slot": parts[2], "end_slot": parts[3]})
    return _parse_student_slot_rows(rows)


def parse_manual_teachers(text: str) -> list[tuple[str, int, int]]:
    rows: list[dict[str, str]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = [part.strip() for part in line.split(",")]
        if len(parts) != 3:
            raise ValueError("Each teacher manual row must be: day,start_slot,end_slot")
        rows.append({"day": parts[0], "start_slot": parts[1], "end_slot": parts[2]})
    return _parse_teacher_slot_rows(rows)


def _to_absolute_slot(day: str, slot: int, slots_per_day: int) -> int:
    return DAY_TO_IDX[day] * slots_per_day + slot


def _decode_absolute_slot(absolute_slot: int, slots_per_day: int) -> tuple[str, int]:
    day_idx = absolute_slot // slots_per_day
    day = DAY_ORDER[day_idx]
    slot = absolute_slot % slots_per_day
    return day, slot


def build_availability_matrices(
    student_rows: list[tuple[str, str, int, int]],
    teacher_rows: list[tuple[str, int, int]],
    slots_per_day: int = 48,
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    if not student_rows:
        raise ValueError("No student availability rows were provided.")
    if not teacher_rows:
        raise ValueError("No teacher availability rows were provided.")

    student_ids = sorted({student_id for student_id, _, _, _ in student_rows})
    student_index = {student_id: idx for idx, student_id in enumerate(student_ids)}
    total_slots = len(DAY_ORDER) * slots_per_day
    student_matrix = np.zeros((len(student_ids), total_slots), dtype=bool)
    teacher_vector = np.zeros(total_slots, dtype=bool)

    for student_id, day, start, end in student_rows:
        if end > slots_per_day:
            raise ValueError(f"Student row for '{student_id}' exceeds slots_per_day={slots_per_day}.")
        absolute_start = _to_absolute_slot(day, start, slots_per_day)
        absolute_end = _to_absolute_slot(day, end, slots_per_day)
        student_matrix[student_index[student_id], absolute_start:absolute_end] = True

    for day, start, end in teacher_rows:
        if end > slots_per_day:
            raise ValueError(f"Teacher row '{day},{start},{end}' exceeds slots_per_day={slots_per_day}.")
        absolute_start = _to_absolute_slot(day, start, slots_per_day)
        absolute_end = _to_absolute_slot(day, end, slots_per_day)
        teacher_vector[absolute_start:absolute_end] = True

    return student_matrix, teacher_vector, student_ids


def _count_students_covered(
    student_availability: np.ndarray, slot_start: int, slot_length_slots: int
) -> int:
    """Count students available for the full slot duration."""
    slot_window = student_availability[:, slot_start : slot_start + slot_length_slots]
    return int(np.all(slot_window, axis=1).sum())

# constrains optimization to only feasible slots for the teacher
def _valid_slot_starts(
    teacher_availability: np.ndarray, slot_length_slots: int
) -> np.ndarray:
    """Return start indices where the teacher can host the full slot."""
    max_start = teacher_availability.shape[0] - slot_length_slots + 1
    starts: list[int] = []
    for start in range(max_start):
        window = teacher_availability[start : start + slot_length_slots]
        if bool(np.all(window)):
            starts.append(start)
    return np.array(starts, dtype=int)


class OfficeHourProblem(ElementwiseProblem):
    """
    Single-objective optimization:
    - Decision variable: index into feasible slot starts
    - Objective: maximize student coverage (modeled as minimizing negative coverage)
    """

    def __init__(
        self,
        student_availability: np.ndarray,
        candidate_starts: np.ndarray,
        slot_length_slots: int,
    ) -> None:
        self.student_availability = student_availability
        self.candidate_starts = candidate_starts
        self.slot_length_slots = slot_length_slots

        super().__init__(n_var=1, n_obj=1, xl=0, xu=len(candidate_starts) - 1)

    def _evaluate(self, x: np.ndarray, out: dict[str, Any], *args: Any, **kwargs: Any) -> None:
        candidate_idx = int(np.clip(np.rint(x[0]), 0, len(self.candidate_starts) - 1))
        slot_start = int(self.candidate_starts[candidate_idx])
        covered = _count_students_covered(
            self.student_availability, slot_start, self.slot_length_slots
        )
        out["F"] = [-covered]


def optimize_office_hour_slot(
    student_availability: np.ndarray,
    teacher_availability: np.ndarray,
    slot_length_slots: int = 2,
    pop_size: int = 40,
    generations: int = 50,
    seed: int = 1,
) -> dict[str, Any]:
    """
    Find the best slot index for office hours using pymoo.

    Inputs (prepared by upstream code, e.g. later CSV parsing):
    - student_availability: shape (num_students, num_time_slots), bool-like
    - teacher_availability: shape (num_time_slots,), bool-like
    - slot_length_slots: consecutive slot count for office hours
    """
    student_matrix = np.asarray(student_availability, dtype=bool)
    teacher_vector = np.asarray(teacher_availability, dtype=bool)

    if student_matrix.ndim != 2:
        raise ValueError("student_availability must be a 2D array.")
    if teacher_vector.ndim != 1:
        raise ValueError("teacher_availability must be a 1D array.")
    if student_matrix.shape[1] != teacher_vector.shape[0]:
        raise ValueError("Student and teacher availability must share the same time axis length.")
    if slot_length_slots < 1:
        raise ValueError("slot_length_slots must be >= 1.")

    candidate_starts = _valid_slot_starts(teacher_vector, slot_length_slots)
    if candidate_starts.size == 0:
        raise ValueError("No feasible slot start found for teacher availability and slot length.")

    problem = OfficeHourProblem(student_matrix, candidate_starts, slot_length_slots)
    algorithm = GA(pop_size=pop_size)
    result = minimize(
        problem,
        algorithm,
        termination=("n_gen", generations),
        seed=seed,
        verbose=False,
    )

    best_idx = int(np.clip(np.rint(result.X[0]), 0, len(candidate_starts) - 1))
    best_start = int(candidate_starts[best_idx])
    covered = _count_students_covered(student_matrix, best_start, slot_length_slots)
    total_students = int(student_matrix.shape[0])

    return {
        "slot_start_index": best_start,
        "slot_length_slots": slot_length_slots,
        "students_covered": covered,
        "total_students": total_students,
        "coverage_ratio": covered / total_students if total_students else 0.0,
    }


def optimize_from_records(
    student_rows: list[tuple[str, str, int, int]],
    teacher_rows: list[tuple[str, int, int]],
    slot_length_slots: int = 2,
    slots_per_day: int = 48,
) -> dict[str, Any]:
    student_matrix, teacher_vector, student_ids = build_availability_matrices(
        student_rows, teacher_rows, slots_per_day=slots_per_day
    )
    result = optimize_office_hour_slot(
        student_availability=student_matrix,
        teacher_availability=teacher_vector,
        slot_length_slots=slot_length_slots,
    )
    best_day, best_start_slot = _decode_absolute_slot(result["slot_start_index"], slots_per_day)
    _, best_end_slot = _decode_absolute_slot(
        result["slot_start_index"] + slot_length_slots, slots_per_day
    )
    result["slot_day"] = best_day
    result["start_slot_in_day"] = best_start_slot
    result["end_slot_in_day"] = best_end_slot
    result["student_ids"] = student_ids
    return result


def write_result_csv(result: dict[str, Any], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["day", "start_slot", "end_slot", "students_covered", "total_students", "coverage_ratio"])
        writer.writerow([
            result["slot_day"],
            result["start_slot_in_day"],
            result["end_slot_in_day"],
            result["students_covered"],
            result["total_students"],
            f"{result['coverage_ratio']:.4f}",
        ])
    return path
