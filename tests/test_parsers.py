"""Unit tests for the parsing helpers in ``optimize.py``.

These tests cover both the small private helpers (``_normalize_day``,
``_parse_slot``, ``_parse_time_to_slot``) and the public CSV / manual-text
parsers used by the Flask route.
"""

from __future__ import annotations

import pytest

from optimize import (
    _normalize_day,
    _parse_slot,
    _parse_time_to_slot,
    parse_manual_students,
    parse_manual_teachers,
    parse_student_csv_text,
    parse_teacher_csv_text,
)


class TestNormalizeDay:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("mon", "mon"),
            ("Mon", "mon"),
            ("MONDAY", "mon"),
            ("  tuesday ", "tue"),
            ("wednesday", "wed"),
            ("Thu", "thu"),
            ("fri", "fri"),
        ],
    )
    def test_accepts_valid_days(self, raw: str, expected: str) -> None:
        assert _normalize_day(raw) == expected

    @pytest.mark.parametrize("raw", ["sat", "sun", "", "xyz", "abc"])
    def test_rejects_invalid_days(self, raw: str) -> None:
        with pytest.raises(ValueError):
            _normalize_day(raw)

    def test_truncates_to_three_letter_prefix(self) -> None:
        # The current implementation just takes the first three letters of the
        # lowercased input.  This test pins that contract so future changes
        # have to update both the helper and the docs in AGENTS.md.
        assert _normalize_day("monday") == "mon"
        assert _normalize_day("Wednesday") == "wed"


class TestParseSlot:
    def test_accepts_valid_int(self) -> None:
        assert _parse_slot("18") == 18

    def test_accepts_zero(self) -> None:
        assert _parse_slot("0") == 0

    @pytest.mark.parametrize("raw", ["abc", "", "1.5", "9:00"])
    def test_rejects_non_integer(self, raw: str) -> None:
        with pytest.raises(ValueError):
            _parse_slot(raw)

    def test_rejects_negative(self) -> None:
        with pytest.raises(ValueError):
            _parse_slot("-3")


class TestParseTimeToSlot:
    @pytest.mark.parametrize(
        "raw, expected_slot",
        [
            ("00:00", 0),
            ("00:30", 1),
            ("09:00", 18),
            ("12:00", 24),
            ("23:30", 47),
        ],
    )
    def test_aligned_times(self, raw: str, expected_slot: int) -> None:
        assert _parse_time_to_slot(raw) == expected_slot

    def test_rejects_misaligned_minutes(self) -> None:
        with pytest.raises(ValueError):
            _parse_time_to_slot("09:15")

    @pytest.mark.parametrize("raw", ["9", "9:00:00", "noon", ""])
    def test_rejects_malformed(self, raw: str) -> None:
        with pytest.raises(ValueError):
            _parse_time_to_slot(raw)

    @pytest.mark.parametrize("raw", ["24:00", "12:60", "-1:00"])
    def test_rejects_out_of_range(self, raw: str) -> None:
        with pytest.raises(ValueError):
            _parse_time_to_slot(raw)


class TestParseStudentCsvText:
    def test_empty_returns_empty_list(self) -> None:
        assert parse_student_csv_text("") == []
        assert parse_student_csv_text("   \n  ") == []

    def test_slot_format_basic(self) -> None:
        csv_text = "id,day,start_slot,end_slot\ns1,mon,18,22\ns2,Tue,20,24\n"
        rows = parse_student_csv_text(csv_text)
        assert rows == [
            ("s1", "mon", 18, 22),
            ("s2", "tue", 20, 24),
        ]

    def test_slot_format_rejects_missing_id(self) -> None:
        csv_text = "id,day,start_slot,end_slot\n,mon,18,22\n"
        with pytest.raises(ValueError, match="missing 'id'"):
            parse_student_csv_text(csv_text)

    def test_slot_format_rejects_inverted_range(self) -> None:
        csv_text = "id,day,start_slot,end_slot\ns1,mon,22,18\n"
        with pytest.raises(ValueError, match="start >= end"):
            parse_student_csv_text(csv_text)

    def test_wide_format_basic(self) -> None:
        csv_text = (
            "student,Monday_start,Monday_end,Tuesday_start,Tuesday_end,"
            "Wednesday_start,Wednesday_end,Thursday_start,Thursday_end,"
            "Friday_start,Friday_end\n"
            "Brad,09:00,11:00,,,10:00,12:00,,,,\n"
        )
        rows = parse_student_csv_text(csv_text)
        # 09:00 -> slot 18, 11:00 -> slot 22; 10:00 -> 20, 12:00 -> 24
        assert ("Brad", "mon", 18, 22) in rows
        assert ("Brad", "wed", 20, 24) in rows
        assert all(student == "Brad" for student, _, _, _ in rows)
        # Empty days should be skipped, not produce rows.
        assert len(rows) == 2

    def test_wide_format_skips_blank_student(self) -> None:
        csv_text = (
            "student,Monday_start,Monday_end,Tuesday_start,Tuesday_end,"
            "Wednesday_start,Wednesday_end,Thursday_start,Thursday_end,"
            "Friday_start,Friday_end\n"
            "Alice,09:00,11:00,,,,,,,,\n"
            ",,,,,,,,,,\n"
        )
        rows = parse_student_csv_text(csv_text)
        assert rows == [("Alice", "mon", 18, 22)]

    def test_wide_format_rejects_partial_range(self) -> None:
        csv_text = (
            "student,Monday_start,Monday_end,Tuesday_start,Tuesday_end,"
            "Wednesday_start,Wednesday_end,Thursday_start,Thursday_end,"
            "Friday_start,Friday_end\n"
            "Alice,09:00,,,,,,,,,\n"
        )
        with pytest.raises(ValueError, match="Incomplete time range"):
            parse_student_csv_text(csv_text)

    def test_wide_format_rejects_inverted_range(self) -> None:
        csv_text = (
            "student,Monday_start,Monday_end,Tuesday_start,Tuesday_end,"
            "Wednesday_start,Wednesday_end,Thursday_start,Thursday_end,"
            "Friday_start,Friday_end\n"
            "Alice,11:00,09:00,,,,,,,,\n"
        )
        with pytest.raises(ValueError, match="Invalid time range"):
            parse_student_csv_text(csv_text)

    def test_unknown_headers(self) -> None:
        csv_text = "name,when,from,to\nBrad,mon,18,22\n"
        with pytest.raises(ValueError, match="Student CSV must use"):
            parse_student_csv_text(csv_text)


class TestParseTeacherCsvText:
    def test_empty_returns_empty_list(self) -> None:
        assert parse_teacher_csv_text("") == []

    def test_basic(self) -> None:
        csv_text = "day,start_slot,end_slot\nmon,18,24\nfri,20,30\n"
        assert parse_teacher_csv_text(csv_text) == [
            ("mon", 18, 24),
            ("fri", 20, 30),
        ]

    def test_missing_headers(self) -> None:
        csv_text = "day,start,end\nmon,18,24\n"
        with pytest.raises(ValueError, match="day,start_slot,end_slot"):
            parse_teacher_csv_text(csv_text)

    def test_inverted_range(self) -> None:
        csv_text = "day,start_slot,end_slot\nmon,24,18\n"
        with pytest.raises(ValueError, match="start_slot >= end_slot"):
            parse_teacher_csv_text(csv_text)


class TestParseManualStudents:
    def test_basic(self) -> None:
        text = "s1,mon,18,22\ns2, tue ,20,24\n\n"
        assert parse_manual_students(text) == [
            ("s1", "mon", 18, 22),
            ("s2", "tue", 20, 24),
        ]

    def test_skips_blank_lines(self) -> None:
        text = "\n\ns1,mon,18,22\n   \n"
        assert parse_manual_students(text) == [("s1", "mon", 18, 22)]

    def test_wrong_column_count(self) -> None:
        with pytest.raises(ValueError, match="id,day,start_slot,end_slot"):
            parse_manual_students("s1,mon,18\n")

    def test_invalid_day(self) -> None:
        with pytest.raises(ValueError):
            parse_manual_students("s1,sat,18,22\n")


class TestParseManualTeachers:
    def test_basic(self) -> None:
        text = "mon,18,24\nfri,20,30\n"
        assert parse_manual_teachers(text) == [
            ("mon", 18, 24),
            ("fri", 20, 30),
        ]

    def test_wrong_column_count(self) -> None:
        with pytest.raises(ValueError, match="day,start_slot,end_slot"):
            parse_manual_teachers("mon,18\n")

    def test_skips_blank_lines(self) -> None:
        text = "\nmon,18,24\n\n"
        assert parse_manual_teachers(text) == [("mon", 18, 24)]
