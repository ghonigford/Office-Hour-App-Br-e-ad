"""Tests for the matrix builders and small numeric helpers in ``optimize.py``.

These cover the pieces that translate parsed records into the boolean matrices
consumed by the GA, plus the standalone helpers used inside the problem
classes.
"""

from __future__ import annotations

import numpy as np
import pytest

from optimize import (
    DAY_ORDER,
    _count_students_covered,
    _decode_absolute_slot,
    _decode_block_indices,
    _to_absolute_slot,
    _unique_coverage_mask,
    _valid_slot_starts,
    build_availability_matrices,
)


class TestAbsoluteSlotRoundTrip:
    @pytest.mark.parametrize("day", DAY_ORDER)
    @pytest.mark.parametrize("slot", [0, 1, 17, 24, 47])
    def test_round_trip(self, day: str, slot: int) -> None:
        slots_per_day = 48
        absolute = _to_absolute_slot(day, slot, slots_per_day)
        decoded_day, decoded_slot = _decode_absolute_slot(absolute, slots_per_day)
        assert decoded_day == day
        assert decoded_slot == slot

    def test_day_offsets(self) -> None:
        assert _to_absolute_slot("mon", 0, 48) == 0
        assert _to_absolute_slot("tue", 0, 48) == 48
        assert _to_absolute_slot("fri", 47, 48) == 4 * 48 + 47


class TestBuildAvailabilityMatrices:
    def test_shape_and_values(self) -> None:
        student_rows = [
            ("s1", "mon", 18, 22),
            ("s2", "tue", 20, 24),
            ("s1", "wed", 18, 20),  # second range for s1
        ]
        teacher_rows = [("mon", 18, 24), ("tue", 20, 26)]
        student_matrix, teacher_vector, ids = build_availability_matrices(
            student_rows, teacher_rows, slots_per_day=48
        )

        assert student_matrix.shape == (2, 5 * 48)
        assert teacher_vector.shape == (5 * 48,)
        assert ids == ["s1", "s2"]

        # s1 should be available on mon 18..21 inclusive (slice 18:22) and
        # wed 18..19 inclusive (slice 18:20).
        s1_idx = ids.index("s1")
        assert student_matrix[s1_idx, 18:22].all()
        assert not student_matrix[s1_idx, 17]
        assert not student_matrix[s1_idx, 22]
        wed_offset = 2 * 48
        assert student_matrix[s1_idx, wed_offset + 18 : wed_offset + 20].all()
        assert not student_matrix[s1_idx, wed_offset + 20]

        # Teacher should be available mon 18..23 and tue 20..25.
        assert teacher_vector[18:24].all()
        assert not teacher_vector[24]
        assert teacher_vector[48 + 20 : 48 + 26].all()

    def test_empty_students_raises(self) -> None:
        with pytest.raises(ValueError, match="No student"):
            build_availability_matrices([], [("mon", 18, 24)])

    def test_empty_teachers_raises(self) -> None:
        with pytest.raises(ValueError, match="No teacher"):
            build_availability_matrices([("s1", "mon", 18, 22)], [])

    def test_student_end_exceeds_day_raises(self) -> None:
        with pytest.raises(ValueError, match="exceeds slots_per_day"):
            build_availability_matrices(
                [("s1", "mon", 18, 50)],
                [("mon", 18, 24)],
                slots_per_day=48,
            )

    def test_teacher_end_exceeds_day_raises(self) -> None:
        with pytest.raises(ValueError, match="exceeds slots_per_day"):
            build_availability_matrices(
                [("s1", "mon", 18, 22)],
                [("mon", 18, 50)],
                slots_per_day=48,
            )


class TestCountStudentsCovered:
    def test_full_window_covered(self) -> None:
        # 3 students, 4 slots; only s0 and s2 are available across slots 1..2.
        student_matrix = np.array(
            [
                [False, True, True, False],
                [False, True, False, False],
                [True, True, True, True],
            ],
            dtype=bool,
        )
        assert _count_students_covered(student_matrix, slot_start=1, slot_length_slots=2) == 2

    def test_returns_zero_when_nobody_available(self) -> None:
        student_matrix = np.zeros((3, 4), dtype=bool)
        assert _count_students_covered(student_matrix, 0, 2) == 0


class TestValidSlotStarts:
    def test_only_contiguous_windows(self) -> None:
        # Teacher available at indices 1, 2, 3 and 5, 6.
        teacher = np.array([0, 1, 1, 1, 0, 1, 1, 0], dtype=bool)
        starts = _valid_slot_starts(teacher, slot_length_slots=2)
        # Valid 2-length windows: [1,2], [2,3], [5,6]. Starts: 1, 2, 5.
        assert starts.tolist() == [1, 2, 5]

    def test_empty_when_no_window_fits(self) -> None:
        teacher = np.array([1, 0, 1, 0], dtype=bool)
        starts = _valid_slot_starts(teacher, slot_length_slots=2)
        assert starts.size == 0


class TestDecodeBlockIndices:
    def test_prunes_overlapping_picks(self) -> None:
        # Candidate starts at every integer from 0..9, slot length = 3.
        candidates = np.arange(10)
        # Picks 0, 1, and 5: 0 kept, 1 overlaps with 0 (0..2), 5 starts after 0+3 -> kept.
        kept = _decode_block_indices(np.array([0.0, 1.0, 5.0]), candidates, slot_length_slots=3)
        assert kept == [0, 5]

    def test_deduplicates_repeated_indices(self) -> None:
        candidates = np.arange(5)
        kept = _decode_block_indices(np.array([2.0, 2.0, 2.0]), candidates, slot_length_slots=2)
        assert kept == [2]

    def test_clips_out_of_range_indices(self) -> None:
        candidates = np.array([10, 20, 30])
        kept = _decode_block_indices(np.array([-5.0, 99.0]), candidates, slot_length_slots=1)
        # -5 -> clipped to 0 -> 10; 99 -> clipped to 2 -> 30.
        assert kept == [10, 30]

    def test_empty_candidates(self) -> None:
        assert _decode_block_indices(np.array([0.0]), np.array([], dtype=int), slot_length_slots=2) == []


class TestUniqueCoverageMask:
    def test_unions_blocks(self) -> None:
        # 3 students, 6 slots.
        student_matrix = np.array(
            [
                [1, 1, 0, 0, 0, 0],  # available only in block 0..1
                [0, 0, 0, 0, 1, 1],  # available only in block 4..5
                [1, 1, 0, 0, 1, 1],  # available in both
            ],
            dtype=bool,
        )
        mask = _unique_coverage_mask(student_matrix, [0, 4], slot_length_slots=2)
        # All 3 students should be covered exactly once.
        assert mask.tolist() == [True, True, True]
        assert int(mask.sum()) == 3

    def test_empty_blocks_produces_empty_mask(self) -> None:
        student_matrix = np.ones((4, 6), dtype=bool)
        mask = _unique_coverage_mask(student_matrix, [], slot_length_slots=2)
        assert mask.tolist() == [False, False, False, False]
