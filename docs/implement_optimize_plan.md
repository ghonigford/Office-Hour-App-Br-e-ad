---
name: set up optimize.py
overview: Implement 'optimize.py' in very small, safe slices, that only implements a few lines of code at a time, before it will ask the user for confirmation and if the code makes sense. The purpose of optimize.py as a whole is to take in students and a teacher's schedule that will then be used as inputs for a pymoo function which will determine the best time for the teacher to have office hours.
todos:
    - allow for CSV file to be imported with student and teacher schedules.
    - conversion of schedules of csv file values into input for pymoo
    - set up pymoo optimization to determine the best time for the professor to have office hours
    - make it so output from pymoo is converted into a csv format that resembles the format of the csv file that was inputted
---

> **Status:** historical. This is the original tiny-step plan that was used to
> bring `optimize.py` up. All three steps below have shipped — the live code
> in `optimize.py`, the Flask integration in `app.py`, and the test suite in
> `tests/` are the current source of truth. Kept here as a paper trail.

# Tiny-step plan
Between each step ask the user to see if they accept the code and understand it.

## First step: set up pymoo optimization function

### Goal of first step
Build the pymoo optimization part of this code. Don't need specific CSV files to input into it yet, but it should be set up in a format to receive them later on.

### Scope of first step
- Add pymoo code in [`optimize.py`](../optimize.py).

### Out of scope (for first step)
- No working with actual CSV files.
- No Flask integration.

## Step 2: set up format to convert CSV files into input for pymoo function

### Goal of second step
Take the information from a CSV file and set it up to be the input for the pymoo function.

### Scope of second step
- Set up functions that convert CSV files into usable input for pymoo in [`optimize.py`](../optimize.py).
- Example teacher CSV file: [`examples/teacher_availability.csv`](../examples/teacher_availability.csv).
- Example student CSV file: [`examples/students_availability.csv`](../examples/students_availability.csv).

### Out of scope (for now)
- No Flask integration.
- No output CSV file from this.

## Step 3: Set up output from optimize file

### Goal of third step
Set up `optimize.py` to output a CSV file containing the found optimal office hour schedule for the teacher.

### Scope of third step
- Set up functions that convert output into a CSV file in [`optimize.py`](../optimize.py).
- Example teacher input CSV file: [`examples/teacher_availability.csv`](../examples/teacher_availability.csv).
- Example student input CSV file: [`examples/students_availability.csv`](../examples/students_availability.csv).
- Output is now produced via `optimize.write_result_csv(result, output_path)`; the caller decides where to write it.

### Next steps after Step 3
1. Call `optimize.py` from `ai_final.py` so that custom CSV files can be inputted there and used as input. *(Superseded — `ai_final.py` is now a standalone CLI prototype kept under `legacy/`; the live entrypoint is the Flask app in `app.py`.)*
2. Set up integration with Flask so that input from the website can be used as CSV input for `optimize.py`. *(Done — see `app.py`.)*
