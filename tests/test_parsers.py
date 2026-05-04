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
    _parse_strength,
    _parse_time_to_slot,
    parse_manual_students,
    parse_manual_students_v2,
    parse_manual_teachers,
    parse_manual_teachers_v2,
    parse_student_csv_text,
    parse_student_csv_text_v2,
    parse_teacher_csv_text,
    parse_teacher_csv_text_v2,
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


# ---------------------------------------------------------------------------
# v2 parsers (weighted + multi-teacher)
# ---------------------------------------------------------------------------


class TestParseStrength:
    @pytest.mark.parametrize(
        "raw, expected",
        [("hard", "hard"), ("soft", "soft"), ("HARD", "hard"), (" Soft ", "soft"), ("", "hard"), (None, "hard")],
    )
    def test_normalizes(self, raw: str | None, expected: str) -> None:
        assert _parse_strength(raw) == expected

    def test_default_override(self) -> None:
        assert _parse_strength(None, default="soft") == "soft"
        assert _parse_strength("", default="soft") == "soft"

    def test_invalid_value_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid strength"):
            _parse_strength("medium")


class TestParseManualStudentsV2:
    def test_legacy_four_field_defaults_to_hard(self) -> None:
        rows = parse_manual_students_v2("s1,mon,18,22\ns2,tue,20,24\n")
        assert rows == [
            ("s1", "mon", 18, 22, "hard"),
            ("s2", "tue", 20, 24, "hard"),
        ]

    def test_full_five_field_with_strength(self) -> None:
        rows = parse_manual_students_v2("s1,mon,18,22,hard\ns1,mon,22,26,soft\n")
        assert rows == [
            ("s1", "mon", 18, 22, "hard"),
            ("s1", "mon", 22, 26, "soft"),
        ]

    def test_invalid_strength_value(self) -> None:
        with pytest.raises(ValueError, match="Invalid strength"):
            parse_manual_students_v2("s1,mon,18,22,maybe\n")

    def test_inverted_range_rejected(self) -> None:
        with pytest.raises(ValueError, match="start >= end"):
            parse_manual_students_v2("s1,mon,22,18,hard\n")

    def test_missing_id_rejected(self) -> None:
        with pytest.raises(ValueError, match="missing 'id'"):
            parse_manual_students_v2(",mon,18,22,hard\n")

    def test_wrong_column_count(self) -> None:
        with pytest.raises(ValueError, match="strength"):
            parse_manual_students_v2("s1,mon,18\n")

    def test_blank_lines_skipped(self) -> None:
        assert parse_manual_students_v2("\ns1,mon,18,22\n\n") == [("s1", "mon", 18, 22, "hard")]


class TestParseManualTeachersV2:
    def test_legacy_three_field_defaults_to_single_teacher_hard(self) -> None:
        rows = parse_manual_teachers_v2("mon,18,24\nfri,20,30\n")
        assert rows == [
            ("teacher", "mon", 18, 24, "hard"),
            ("teacher", "fri", 20, 30, "hard"),
        ]

    def test_four_field_with_teacher_id(self) -> None:
        rows = parse_manual_teachers_v2("prof1,mon,18,24\nprof2,tue,20,30\n")
        assert rows == [
            ("prof1", "mon", 18, 24, "hard"),
            ("prof2", "tue", 20, 30, "hard"),
        ]

    def test_full_five_field(self) -> None:
        rows = parse_manual_teachers_v2("prof1,mon,18,24,hard\nprof1,tue,20,24,soft\n")
        assert rows == [
            ("prof1", "mon", 18, 24, "hard"),
            ("prof1", "tue", 20, 24, "soft"),
        ]

    def test_unsupported_column_count(self) -> None:
        with pytest.raises(ValueError, match="teacher_id"):
            parse_manual_teachers_v2("prof1,mon\n")

    def test_inverted_range_rejected(self) -> None:
        with pytest.raises(ValueError, match="start >= end"):
            parse_manual_teachers_v2("prof1,mon,30,20,hard\n")


class TestParseStudentCsvTextV2:
    def test_legacy_slot_format_defaults_to_hard(self) -> None:
        rows = parse_student_csv_text_v2("id,day,start_slot,end_slot\ns1,mon,18,22\n")
        assert rows == [("s1", "mon", 18, 22, "hard")]

    def test_with_strength_column(self) -> None:
        rows = parse_student_csv_text_v2(
            "id,day,start_slot,end_slot,strength\ns1,mon,18,22,hard\ns1,mon,22,24,soft\n"
        )
        assert rows == [
            ("s1", "mon", 18, 22, "hard"),
            ("s1", "mon", 22, 24, "soft"),
        ]

    def test_wide_format_defaults_to_hard(self) -> None:
        csv_text = (
            "student,Monday_start,Monday_end,Tuesday_start,Tuesday_end,"
            "Wednesday_start,Wednesday_end,Thursday_start,Thursday_end,"
            "Friday_start,Friday_end\n"
            "Brad,09:00,11:00,,,,,,,,\n"
        )
        rows = parse_student_csv_text_v2(csv_text)
        assert rows == [("Brad", "mon", 18, 22, "hard")]

    def test_empty_text_returns_empty(self) -> None:
        assert parse_student_csv_text_v2("") == []

    def test_unknown_headers_raise(self) -> None:
        with pytest.raises(ValueError, match="Student CSV"):
            parse_student_csv_text_v2("name,when,from,to\nA,mon,1,2\n")


class TestParseTeacherCsvTextV2:
    def test_legacy_three_columns(self) -> None:
        rows = parse_teacher_csv_text_v2("day,start_slot,end_slot\nmon,18,24\n")
        assert rows == [("teacher", "mon", 18, 24, "hard")]

    def test_with_teacher_id(self) -> None:
        rows = parse_teacher_csv_text_v2("teacher_id,day,start_slot,end_slot\nprof1,mon,18,24\nprof2,tue,20,30\n")
        assert rows == [
            ("prof1", "mon", 18, 24, "hard"),
            ("prof2", "tue", 20, 30, "hard"),
        ]

    def test_with_strength_column(self) -> None:
        rows = parse_teacher_csv_text_v2(
            "teacher_id,day,start_slot,end_slot,strength\nprof1,mon,18,24,hard\nprof1,mon,24,28,soft\n"
        )
        assert rows == [
            ("prof1", "mon", 18, 24, "hard"),
            ("prof1", "mon", 24, 28, "soft"),
        ]

    def test_missing_required_columns(self) -> None:
        with pytest.raises(ValueError, match="day,start_slot,end_slot"):
            parse_teacher_csv_text_v2("teacher_id,start,end\nprof1,18,22\n")

    def test_empty_text_returns_empty(self) -> None:
        assert parse_teacher_csv_text_v2("") == []
