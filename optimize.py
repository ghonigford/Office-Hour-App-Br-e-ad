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
