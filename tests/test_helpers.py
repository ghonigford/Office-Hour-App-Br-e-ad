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
    _aggregate_weighted_coverage,
    _block_per_student_score,
    _count_students_covered,
    _decode_absolute_slot,
    _decode_block_indices,
    _decode_multi_teacher_picks,
    _summarize_availability,
    _to_absolute_slot,
    _unique_coverage_mask,
    _valid_slot_starts,
    _valid_slot_starts_weighted,
    build_availability_matrices,
    build_availability_matrices_v2,
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


# ---------------------------------------------------------------------------
# v2 helpers (weighted matrices, multi-teacher decoder, scoring)
# ---------------------------------------------------------------------------


class TestBuildAvailabilityMatricesV2:
    def test_shape_values_and_strengths(self) -> None:
        student_rows = [
            ("s1", "mon", 18, 22, "hard"),
            ("s1", "mon", 22, 24, "soft"),
            ("s2", "tue", 20, 24, "hard"),
        ]
        teacher_rows = [
            ("prof1", "mon", 18, 24, "hard"),
            ("prof2", "tue", 20, 30, "soft"),
        ]
        student_matrix, teacher_matrices, sids, tids = build_availability_matrices_v2(
            student_rows, teacher_rows, slots_per_day=48
        )

        assert student_matrix.shape == (2, 5 * 48)
        assert sids == ["s1", "s2"]
        assert tids == ["prof1", "prof2"]

        s1 = sids.index("s1")
        # Hard 18..21 -> 1.0, soft 22..23 -> 0.5.
        assert (student_matrix[s1, 18:22] == 1.0).all()
        assert (student_matrix[s1, 22:24] == 0.5).all()
        assert student_matrix[s1, 17] == 0.0
        assert student_matrix[s1, 24] == 0.0

        # Teachers are float with the right strengths.
        assert (teacher_matrices["prof1"][18:24] == 1.0).all()
        assert teacher_matrices["prof1"][17] == 0.0
        assert (teacher_matrices["prof2"][48 + 20 : 48 + 30] == 0.5).all()

    def test_overlapping_rows_take_max(self) -> None:
        # Same student, same slot, marked both soft and hard -> hard wins.
        student_rows = [
            ("s1", "mon", 18, 22, "soft"),
            ("s1", "mon", 18, 22, "hard"),
        ]
        teacher_rows = [("teacher", "mon", 18, 22, "hard")]
        student_matrix, _, _, _ = build_availability_matrices_v2(
            student_rows, teacher_rows, slots_per_day=48
        )
        assert (student_matrix[0, 18:22] == 1.0).all()

    def test_empty_students_raises(self) -> None:
        with pytest.raises(ValueError, match="No student"):
            build_availability_matrices_v2([], [("teacher", "mon", 18, 24, "hard")])

    def test_empty_teachers_raises(self) -> None:
        with pytest.raises(ValueError, match="No teacher"):
            build_availability_matrices_v2([("s1", "mon", 18, 22, "hard")], [])

    def test_student_end_exceeds_day_raises(self) -> None:
        with pytest.raises(ValueError, match="exceeds slots_per_day"):
            build_availability_matrices_v2(
                [("s1", "mon", 18, 50, "hard")],
                [("teacher", "mon", 18, 24, "hard")],
                slots_per_day=48,
            )


class TestValidSlotStartsWeighted:
    def test_treats_soft_as_feasible(self) -> None:
        # 0.5 is at-least-soft so it counts as a valid host slot.
        teacher = np.array([0.0, 1.0, 0.5, 1.0, 0.0, 0.5, 0.5, 0.0])
        starts = _valid_slot_starts_weighted(teacher, slot_length_slots=2)
        # Valid windows (length 2 with min > 0): [1,2], [2,3], [5,6].
        assert starts.tolist() == [1, 2, 5]

    def test_zero_breaks_window(self) -> None:
        teacher = np.array([1.0, 0.0, 1.0, 0.0])
        starts = _valid_slot_starts_weighted(teacher, slot_length_slots=2)
        assert starts.size == 0


class TestBlockPerStudentScore:
    def test_min_of_min_pairing(self) -> None:
        # 3 students, 4 slots. Block = slots [1..2].
        student_matrix = np.array(
            [
                [0.0, 1.0, 1.0, 0.0],   # all hard in block -> 1.0
                [0.0, 1.0, 0.5, 0.0],   # one soft slot     -> 0.5
                [0.0, 0.0, 1.0, 0.0],   # one zero slot     -> 0.0
            ]
        )
        teacher = np.array([0.0, 1.0, 1.0, 0.0])
        scores = _block_per_student_score(student_matrix, teacher, start=1, length=2)
        assert scores.tolist() == [1.0, 0.5, 0.0]

    def test_teacher_soft_caps_block_score(self) -> None:
        # Even fully-hard students cap at 0.5 if the host is soft.
        student_matrix = np.array([[1.0, 1.0, 1.0]])
        teacher = np.array([0.5, 0.5, 0.5])
        scores = _block_per_student_score(student_matrix, teacher, start=0, length=3)
        assert scores.tolist() == [0.5]


class TestDecodeMultiTeacherPicks:
    def test_drops_infeasible_host_pick(self) -> None:
        # 2 candidate starts (10 and 20), 2 teachers (prof1, prof2).
        # prof1 is free at start=10, prof2 only at start=20.
        candidates = np.array([10, 20])
        teacher_matrices = {
            "prof1": np.zeros(30),
            "prof2": np.zeros(30),
        }
        teacher_matrices["prof1"][10:12] = 1.0
        teacher_matrices["prof2"][20:22] = 1.0
        # x = [start_idx_0, host_idx_0, start_idx_1, host_idx_1]
        # Pick (start=10, host=prof2) is infeasible -> dropped.
        # Pick (start=20, host=prof2) is feasible -> kept.
        x = np.array([0.0, 1.0, 1.0, 1.0])
        kept = _decode_multi_teacher_picks(
            x, candidates, ["prof1", "prof2"], teacher_matrices, slot_length_slots=2
        )
        assert kept == [(20, "prof2")]

    def test_prunes_overlap_globally_regardless_of_host(self) -> None:
        candidates = np.array([0, 1, 4])
        teacher_matrices = {
            "prof1": np.ones(10),
            "prof2": np.ones(10),
        }
        # Two picks: (0, prof1) and (1, prof2) -> overlap; second is dropped.
        # Third pick (4, prof1) survives.
        x = np.array([0.0, 0.0, 1.0, 1.0, 2.0, 0.0])
        kept = _decode_multi_teacher_picks(
            x, candidates, ["prof1", "prof2"], teacher_matrices, slot_length_slots=2
        )
        assert kept == [(0, "prof1"), (4, "prof1")]

    def test_dedupes_duplicate_picks(self) -> None:
        candidates = np.array([0, 4])
        teacher_matrices = {"prof1": np.ones(10)}
        x = np.array([0.0, 0.0, 0.0, 0.0])
        kept = _decode_multi_teacher_picks(
            x, candidates, ["prof1"], teacher_matrices, slot_length_slots=2
        )
        assert kept == [(0, "prof1")]


class TestAggregateWeightedCoverage:
    def test_takes_max_across_blocks(self) -> None:
        student_matrix = np.array(
            [
                [1.0, 1.0, 0.0, 0.5, 0.5],   # hard in block 0, soft in block 1
                [0.0, 0.0, 0.0, 1.0, 1.0],   # only block 1 reaches
            ]
        )
        teacher_matrices = {"prof": np.ones(5)}
        kept = [(0, "prof"), (3, "prof")]
        best = _aggregate_weighted_coverage(student_matrix, teacher_matrices, kept, slot_length_slots=2)
        # Student 0: max(1.0, 0.5) = 1.0
        # Student 1: max(0.0, 1.0) = 1.0
        assert best.tolist() == [1.0, 1.0]


class TestSummarizeAvailability:
    def test_groups_and_sorts_by_day_then_start(self) -> None:
        rows = [
            ("s1", "fri", 20, 22, "hard"),
            ("s1", "mon", 18, 22, "hard"),
            ("s1", "mon", 22, 24, "soft"),
        ]
        summary = _summarize_availability(rows)
        assert list(summary.keys()) == ["s1"]
        # Ordered: mon 18..22, mon 22..24, fri 20..22.
        days_in_order = [entry["day"] for entry in summary["s1"]]
        starts_in_order = [entry["start_slot"] for entry in summary["s1"]]
        assert days_in_order == ["mon", "mon", "fri"]
        assert starts_in_order == [18, 22, 20]
        assert summary["s1"][1]["strength"] == "soft"
