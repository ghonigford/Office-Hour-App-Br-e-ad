"""Integration tests for the Flask app.

These tests use Flask's built-in test client. They exercise the actual route
handler in ``app.py``, including the precedence rules between the manual
textareas and the file uploads.
"""

from __future__ import annotations

from io import BytesIO

import pytest

from app import app as flask_app

# These strings only appear on the rendered ``<section>`` elements — the names
# also exist as CSS class definitions in ``<style>``, so we have to be specific.
ERROR_SECTION = '<section class="status status-error">'
OK_SECTION = '<section class="status status-ok">'


@pytest.fixture()
def client():
    flask_app.config.update(TESTING=True)
    with flask_app.test_client() as test_client:
        yield test_client


# ---------------------------------------------------------------------------
# GET
# ---------------------------------------------------------------------------


class TestIndexGet:
    def test_get_renders_form(self, client) -> None:
        response = client.get("/")
        assert response.status_code == 200
        body = response.get_data(as_text=True)
        # Hitting GET should render the form fields the route expects on POST.
        for field in (
            'name="students_csv"',
            'name="teachers_csv"',
            'name="students_manual"',
            'name="teachers_manual"',
            'name="slot_length_slots"',
            'name="num_blocks"',
        ):
            assert field in body


# ---------------------------------------------------------------------------
# Successful POST paths
# ---------------------------------------------------------------------------


class TestIndexPostManual:
    def test_manual_input_returns_result(self, client) -> None:
        # All three students free during 09:30..10:30.
        students_text = "s1,mon,18,22\ns2,mon,19,23\ns3,mon,18,23"
        teachers_text = "mon,18,24"
        response = client.post(
            "/",
            data={
                "students_manual": students_text,
                "teachers_manual": teachers_text,
                "slot_length_slots": "2",
                "num_blocks": "1",
            },
        )
        assert response.status_code == 200
        body = response.get_data(as_text=True)
        # The result block in the template surfaces these counts.
        assert "Selected" in body
        # 3/3 with 1 block should show up somewhere in the rendered result.
        assert "3</strong>/<strong>3" in body or "3/3" in body
        assert ERROR_SECTION not in body
        assert OK_SECTION in body

    def test_manual_input_two_blocks_disjoint_groups(self, client) -> None:
        students_text = (
            "a1,mon,18,20\n"
            "a2,mon,18,20\n"
            "b1,mon,28,30\n"
            "b2,mon,28,30"
        )
        teachers_text = "mon,18,32"
        response = client.post(
            "/",
            data={
                "students_manual": students_text,
                "teachers_manual": teachers_text,
                "slot_length_slots": "2",
                "num_blocks": "2",
            },
        )
        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert ERROR_SECTION not in body
        assert OK_SECTION in body
        # 4 / 4 should be covered using both blocks.
        assert "4</strong>/<strong>4" in body or "4/4" in body


class TestIndexPostCsvUpload:
    def test_csv_upload_returns_result(self, client) -> None:
        students_csv = (
            b"id,day,start_slot,end_slot\n"
            b"s1,mon,18,22\n"
            b"s2,mon,19,23\n"
            b"s3,mon,18,23\n"
        )
        teachers_csv = b"day,start_slot,end_slot\nmon,18,24\n"

        response = client.post(
            "/",
            data={
                "students_manual": "",
                "teachers_manual": "",
                "slot_length_slots": "2",
                "num_blocks": "1",
                "students_csv": (BytesIO(students_csv), "students.csv"),
                "teachers_csv": (BytesIO(teachers_csv), "teachers.csv"),
            },
            content_type="multipart/form-data",
        )
        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert ERROR_SECTION not in body
        assert "Selected" in body

    def test_manual_textarea_takes_precedence_over_csv(self, client) -> None:
        # The CSV file is intentionally broken; if we used it, we'd see an
        # error.  Because the manual textarea is non-empty, the route should
        # ignore the upload entirely and succeed.
        broken_students_csv = b"this,is,not,a,valid,header\noops,oops,oops,oops,oops,oops\n"
        students_manual = "s1,mon,18,22\ns2,mon,19,23"
        teachers_manual = "mon,18,24"

        response = client.post(
            "/",
            data={
                "students_manual": students_manual,
                "teachers_manual": teachers_manual,
                "slot_length_slots": "2",
                "num_blocks": "1",
                "students_csv": (BytesIO(broken_students_csv), "broken.csv"),
            },
            content_type="multipart/form-data",
        )
        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert ERROR_SECTION not in body


# ---------------------------------------------------------------------------
# Error handling on POST
# ---------------------------------------------------------------------------


class TestIndexPostErrors:
    def test_missing_students_renders_error(self, client) -> None:
        response = client.post(
            "/",
            data={
                "students_manual": "",
                "teachers_manual": "mon,18,24",
                "slot_length_slots": "2",
                "num_blocks": "1",
            },
        )
        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert ERROR_SECTION in body

    def test_invalid_manual_row_renders_error(self, client) -> None:
        response = client.post(
            "/",
            data={
                "students_manual": "s1,sat,18,22",  # saturday is unsupported
                "teachers_manual": "mon,18,24",
                "slot_length_slots": "2",
                "num_blocks": "1",
            },
        )
        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert ERROR_SECTION in body
        assert "Unsupported day" in body

    def test_zero_slot_length_renders_error(self, client) -> None:
        response = client.post(
            "/",
            data={
                "students_manual": "s1,mon,18,22",
                "teachers_manual": "mon,18,24",
                "slot_length_slots": "0",
                "num_blocks": "1",
            },
        )
        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert ERROR_SECTION in body
        assert "at least one 30-minute slot" in body

    def test_zero_num_blocks_renders_error(self, client) -> None:
        response = client.post(
            "/",
            data={
                "students_manual": "s1,mon,18,22",
                "teachers_manual": "mon,18,24",
                "slot_length_slots": "2",
                "num_blocks": "0",
            },
        )
        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert ERROR_SECTION in body
        assert "at least 1" in body

    def test_non_integer_num_blocks_renders_error(self, client) -> None:
        response = client.post(
            "/",
            data={
                "students_manual": "s1,mon,18,22",
                "teachers_manual": "mon,18,24",
                "slot_length_slots": "2",
                "num_blocks": "abc",
            },
        )
        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert ERROR_SECTION in body
