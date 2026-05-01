"""Behavioral tests for the pymoo-backed optimizers and the result writer.

The pymoo GA is seeded so these tests are deterministic. Problem sizes are
kept small (a handful of students, narrow teacher windows) so the suite stays
fast even though it exercises the real GA path.
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import pytest

from optimize import (
    optimize_from_records,
    optimize_office_hour_blocks,
    optimize_office_hour_slot,
    write_result_csv,
)


# ---------------------------------------------------------------------------
# optimize_office_hour_slot (single block)
# ---------------------------------------------------------------------------


class TestOptimizeOfficeHourSlot:
    def test_finds_obvious_best_slot(self) -> None:
        # 3 students, 6-slot timeline. Best 2-slot window is [1, 2] (covers all 3).
        student_matrix = np.array(
            [
                [0, 1, 1, 0, 0, 0],
                [0, 1, 1, 1, 0, 0],
                [0, 1, 1, 0, 0, 0],
            ],
            dtype=bool,
        )
        teacher = np.ones(6, dtype=bool)
        result = optimize_office_hour_slot(
            student_matrix, teacher, slot_length_slots=2, pop_size=20, generations=20
        )
        assert result["slot_start_index"] == 1
        assert result["students_covered"] == 3
        assert result["total_students"] == 3
        assert result["coverage_ratio"] == pytest.approx(1.0)

    def test_rejects_mismatched_shapes(self) -> None:
        student_matrix = np.zeros((2, 6), dtype=bool)
        teacher = np.zeros(8, dtype=bool)
        with pytest.raises(ValueError, match="same time axis"):
            optimize_office_hour_slot(student_matrix, teacher, slot_length_slots=2)

    def test_rejects_bad_student_dimensions(self) -> None:
        with pytest.raises(ValueError, match="2D array"):
            optimize_office_hour_slot(np.zeros(6, dtype=bool), np.ones(6, dtype=bool), 2)

    def test_rejects_bad_teacher_dimensions(self) -> None:
        with pytest.raises(ValueError, match="1D array"):
            optimize_office_hour_slot(np.zeros((2, 6), dtype=bool), np.ones((2, 6), dtype=bool), 2)

    def test_rejects_zero_slot_length(self) -> None:
        student_matrix = np.zeros((2, 6), dtype=bool)
        teacher = np.ones(6, dtype=bool)
        with pytest.raises(ValueError, match=">= 1"):
            optimize_office_hour_slot(student_matrix, teacher, slot_length_slots=0)

    def test_rejects_no_feasible_window(self) -> None:
        # Teacher never has 2 contiguous available slots.
        teacher = np.array([1, 0, 1, 0, 1, 0], dtype=bool)
        student_matrix = np.ones((2, 6), dtype=bool)
        with pytest.raises(ValueError, match="No feasible slot"):
            optimize_office_hour_slot(student_matrix, teacher, slot_length_slots=2)


# ---------------------------------------------------------------------------
# optimize_office_hour_blocks (multi block)
# ---------------------------------------------------------------------------


class TestOptimizeOfficeHourBlocks:
    def test_single_block_path_matches_single_optimizer(self) -> None:
        student_matrix = np.array(
            [
                [0, 1, 1, 0, 0, 0],
                [0, 1, 1, 1, 0, 0],
                [0, 1, 1, 0, 0, 0],
            ],
            dtype=bool,
        )
        teacher = np.ones(6, dtype=bool)
        result = optimize_office_hour_blocks(
            student_matrix, teacher, slot_length_slots=2, num_blocks=1
        )
        assert result["num_blocks_requested"] == 1
        assert result["num_blocks_selected"] == 1
        assert result["students_covered"] == 3
        assert len(result["blocks"]) == 1
        assert result["blocks"][0]["students_covered_in_block"] == 3

    def test_two_blocks_increases_coverage_when_disjoint_groups_exist(self) -> None:
        # Two disjoint student groups, each only available in their own window.
        # 4 students, 12 slot timeline.  Group A is available in slots 0..1,
        # group B in slots 8..9.  Single-block coverage maxes out at 2; two
        # blocks should cover all 4.
        student_matrix = np.zeros((4, 12), dtype=bool)
        student_matrix[0, 0:2] = True
        student_matrix[1, 0:2] = True
        student_matrix[2, 8:10] = True
        student_matrix[3, 8:10] = True
        teacher = np.ones(12, dtype=bool)

        single = optimize_office_hour_blocks(
            student_matrix, teacher, slot_length_slots=2, num_blocks=1
        )
        multi = optimize_office_hour_blocks(
            student_matrix, teacher, slot_length_slots=2, num_blocks=2
        )

        assert single["students_covered"] == 2
        assert multi["students_covered"] == 4
        assert multi["num_blocks_selected"] == 2

        # Picked blocks must not overlap.
        picks = sorted(b["slot_start_index"] for b in multi["blocks"])
        assert picks[1] >= picks[0] + 2

    def test_block_decoder_drops_overlaps_when_optimizer_returns_overlapping_picks(self) -> None:
        # Only one decent window exists; with num_blocks=3 the decoder must
        # still return at most one usable block (the rest would overlap).
        student_matrix = np.array(
            [[0, 1, 1, 0, 0, 0]] * 2,
            dtype=bool,
        )
        teacher = np.ones(6, dtype=bool)
        result = optimize_office_hour_blocks(
            student_matrix, teacher, slot_length_slots=2, num_blocks=3
        )
        # No two kept blocks may overlap.
        starts = sorted(b["slot_start_index"] for b in result["blocks"])
        for prev, nxt in zip(starts, starts[1:]):
            assert nxt >= prev + 2
        assert result["num_blocks_requested"] == 3
        assert 1 <= result["num_blocks_selected"] <= 3

    def test_rejects_invalid_num_blocks(self) -> None:
        student_matrix = np.ones((2, 6), dtype=bool)
        teacher = np.ones(6, dtype=bool)
        with pytest.raises(ValueError, match="num_blocks"):
            optimize_office_hour_blocks(
                student_matrix, teacher, slot_length_slots=2, num_blocks=0
            )


# ---------------------------------------------------------------------------
# optimize_from_records (end-to-end)
# ---------------------------------------------------------------------------


class TestOptimizeFromRecords:
    def test_returns_full_schema_for_single_block(self) -> None:
        # Only one 1-hour window covers all three students: slots 19..20
        # (09:30..10:30).  s2 is unavailable at slot 21 so a window starting
        # at 20 would only cover s1 and s3.
        student_rows = [
            ("s1", "mon", 18, 22),
            ("s2", "mon", 19, 21),
            ("s3", "mon", 18, 23),
        ]
        teacher_rows = [("mon", 18, 24)]
        result = optimize_from_records(
            student_rows, teacher_rows, slot_length_slots=2, num_blocks=1
        )

        assert "blocks" in result
        assert isinstance(result["blocks"], list) and len(result["blocks"]) == 1
        block = result["blocks"][0]
        assert block["slot_day"] == "mon"
        assert block["start_slot_in_day"] == 19
        assert block["end_slot_in_day"] == 21  # 19 + slot_length(2)
        assert block["students_covered_in_block"] == 3
        assert sorted(block["available_student_ids"]) == ["s1", "s2", "s3"]

        # Aggregates.
        assert result["students_covered"] == 3
        assert result["total_students"] == 3
        assert result["coverage_ratio"] == pytest.approx(1.0)
        assert result["num_blocks_requested"] == 1
        assert result["num_blocks_selected"] == 1
        assert sorted(result["covered_student_ids"]) == ["s1", "s2", "s3"]

        # Legacy keys (mirror of first block) still populated.
        assert result["slot_day"] == block["slot_day"]
        assert result["start_slot_in_day"] == block["start_slot_in_day"]
        assert result["end_slot_in_day"] == block["end_slot_in_day"]
        assert result["slot_start_index"] == block["slot_start_index"]

    def test_two_blocks_cover_two_disjoint_groups(self) -> None:
        # Group A only available mon 09:00..10:00, Group B only mon 14:00..15:00.
        student_rows = [
            ("a1", "mon", 18, 20),
            ("a2", "mon", 18, 20),
            ("b1", "mon", 28, 30),
            ("b2", "mon", 28, 30),
        ]
        teacher_rows = [("mon", 18, 32)]

        result = optimize_from_records(
            student_rows, teacher_rows, slot_length_slots=2, num_blocks=2
        )
        assert result["num_blocks_selected"] == 2
        assert result["students_covered"] == 4
        # Each block covers 2 students; combined block coverage = 4.
        block_coverage = sum(b["students_covered_in_block"] for b in result["blocks"])
        assert block_coverage == 4

        # Sanity: covered ids are a subset of student ids.
        assert set(result["covered_student_ids"]).issubset(set(result["student_ids"]))

    def test_rejects_invalid_inputs(self) -> None:
        with pytest.raises(ValueError):
            optimize_from_records([], [("mon", 18, 24)])


# ---------------------------------------------------------------------------
# write_result_csv
# ---------------------------------------------------------------------------


class TestWriteResultCsv:
    def _sample_result(self) -> dict:
        return {
            "blocks": [
                {
                    "slot_start_index": 19,
                    "slot_day": "mon",
                    "start_slot_in_day": 19,
                    "end_slot_in_day": 21,
                    "students_covered_in_block": 3,
                    "available_student_ids": ["s1", "s2", "s3"],
                },
                {
                    "slot_start_index": 28,
                    "slot_day": "mon",
                    "start_slot_in_day": 28,
                    "end_slot_in_day": 30,
                    "students_covered_in_block": 1,
                    "available_student_ids": ["s4"],
                },
            ],
            "students_covered": 4,
            "total_students": 4,
            "coverage_ratio": 1.0,
        }

    def test_writes_expected_rows(self, tmp_path: Path) -> None:
        out_path = tmp_path / "schedules" / "result.csv"
        returned = write_result_csv(self._sample_result(), out_path)
        assert returned == out_path
        assert out_path.exists()

        with out_path.open(newline="", encoding="utf-8") as fh:
            rows = list(csv.reader(fh))

        assert rows[0] == [
            "block_index",
            "day",
            "start_slot",
            "end_slot",
            "students_covered_in_block",
            "students_covered_total",
            "total_students",
            "coverage_ratio",
        ]
        assert len(rows) == 1 + 2  # header + 2 blocks
        assert rows[1][0] == "1"
        assert rows[1][1] == "mon"
        assert rows[1][4] == "3"
        assert rows[1][5] == "4"
        assert rows[1][6] == "4"
        assert rows[1][7] == "1.0000"
        assert rows[2][0] == "2"
        assert rows[2][4] == "1"

    def test_falls_back_to_legacy_keys_when_blocks_missing(self, tmp_path: Path) -> None:
        legacy_result = {
            "slot_day": "tue",
            "start_slot_in_day": 20,
            "end_slot_in_day": 22,
            "students_covered": 2,
            "total_students": 4,
            "coverage_ratio": 0.5,
        }
        out_path = tmp_path / "legacy.csv"
        write_result_csv(legacy_result, out_path)

        with out_path.open(newline="", encoding="utf-8") as fh:
            rows = list(csv.reader(fh))
        assert len(rows) == 2  # header + one synthesized row
        assert rows[1][1] == "tue"
        assert rows[1][2] == "20"
        assert rows[1][3] == "22"
        assert rows[1][4] == "2"
        assert rows[1][7] == "0.5000"
