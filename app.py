from __future__ import annotations

from flask import Flask, render_template, request

from optimize import (
    optimize_from_records,
    parse_manual_students,
    parse_manual_teachers,
    parse_student_csv_text,
    parse_teacher_csv_text,
)

app = Flask(__name__)


def _read_uploaded_csv(name: str) -> str:
    uploaded_file = request.files.get(name)
    if not uploaded_file or not uploaded_file.filename:
        return ""
    return uploaded_file.read().decode("utf-8-sig")


@app.route("/", methods=["GET", "POST"])
def index():
    result = None
    error = None

    if request.method == "POST":
        try:
            students_manual = request.form.get("students_manual", "").strip()
            teachers_manual = request.form.get("teachers_manual", "").strip()
            slot_length_slots = int(request.form.get("slot_length_slots", "2"))

            if students_manual:
                student_rows = parse_manual_students(students_manual)
            else:
                student_csv = _read_uploaded_csv("students_csv")
                student_rows = parse_student_csv_text(student_csv)

            if teachers_manual:
                teacher_rows = parse_manual_teachers(teachers_manual)
            else:
                teacher_csv = _read_uploaded_csv("teachers_csv")
                teacher_rows = parse_teacher_csv_text(teacher_csv)

            result = optimize_from_records(
                student_rows=student_rows,
                teacher_rows=teacher_rows,
                slot_length_slots=slot_length_slots,
            )
        except (ValueError, UnicodeDecodeError) as exc:
            error = str(exc)
        except Exception:
            error = "Unexpected error while running optimization."

    return render_template("index.html", result=result, error=error)


if __name__ == "__main__":
    app.run(debug=True)
