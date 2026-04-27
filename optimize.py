# currently on step 2 of implement_opimize_plan.md (only implemented step 1 so far)

# The function will take in the student and teacher schedules and output the best time for the teacher to have office hours.
# The function will use the pymoo library to find the best time for the teacher to have office hours.

from __future__ import annotations

from typing import Any

import numpy as np
from pymoo.algorithms.soo.nonconvex.ga import GA
from pymoo.core.problem import ElementwiseProblem
from pymoo.optimize import minimize


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

#this is the function that other code should call. It converts csv files into input for pymoo then builds and runs the pymoo problem.
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


def _demo_inputs(num_students: int = 6, num_slots: int = 40) -> tuple[np.ndarray, np.ndarray]:
    """Small deterministic demo data for local testing without CSV files."""
    rng = np.random.default_rng(42)
    student_availability = rng.random((num_students, num_slots)) > 0.45
    teacher_availability = rng.random(num_slots) > 0.35
    return student_availability, teacher_availability


if __name__ == "__main__":
    students, teacher = _demo_inputs()
    best = optimize_office_hour_slot(students, teacher, slot_length_slots=2)
    print("Best office-hour slot (Step 1 demo):")
    print(best)
