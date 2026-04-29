---
name: set up optimize.py
overview: Implement 'optimize.py' in very small, safe slices, that only implements a few lines of code at a time, before it will ask the user for confirmation and if the code makes sense. The purpose of optimize.py as a whole is to take in students and a teacher's schedule that will then be used as inputs for a pymoo function which will determine the best time for the teacher to have office hours.
todos: 
    - allow for CSV file to be imported with student and teacher schedules.
    - conversion of schedules of csv file values into input for pymoo
    - set up pymoo optimization to determine the best time for the professor to have office hours
    - make it so output from pymoo is converted into a csv format that resembles the format of the csv file that was inputted
---

# Tiny-step plan: 
between each step ask the user to see if they accept the code and understand it

## First step: set up pymoo optimization function

### Goal of first step
build the pymoo optimization part of this code, don't need specific csv files to input into it yet, but should be set up in a format to receive them when set up later on.

### Scope of first step
- Add pymoo code in [C:/Code_general/school/ai_stuff_that_surely_final/Office-Hour-App-Br-e-ad-Fork/optimize.py](C:/Code_general/school/ai_stuff_that_surely_final/Office-Hour-App-Br-e-ad-Fork/optimize.py)

### out of scope (for first step)
- No working with actual CSV files
- No flask integration

## Step 2: set up format to convert CSV files into input for pymoo function

### Goal of second step
To take the information from a csv file and set it up to be the input for the pymoo function. 

### Scope of second step
- Set up functions that converts csv files into usable input for pymoo [C:/Code_general/school/ai_stuff_that_surely_final/Office-Hour-App-Br-e-ad-Fork/optimize.py](C:/Code_general/school/ai_stuff_that_surely_final/Office-Hour-App-Br-e-ad-Fork/optimize.py)
- example teacher CSV file - [C:/Code_general/school/ai_stuff_that_surely_final/Office-Hour-App-Br-e-ad-Fork/schedules/teacher_availability.csv](C:/Code_general/school/ai_stuff_that_surely_final/Office-Hour-App-Br-e-ad-Fork/schedules/teacher_availability.csv)
- example student csv file - [C:/Code_general/school/ai_stuff_that_surely_final/Office-Hour-App-Br-e-ad-Fork/schedules/students_availability.csv](C:/Code_general/school/ai_stuff_that_surely_final/Office-Hour-App-Br-e-ad-Fork/schedules/students_availability.csv)

### Out of scope (for now)
- no flask integration 
- no output csv file from this

## Step 3: Set up output from optimize file

### Goal of third step
The goal of the third step is to set up the optimize.py file to output a csv file containing the found optimal office hour schedule for the teacher. 
- (optional) make another output that states wether 

### Scope of third step
- Set up functions that convert output into a csv file [C:/Code_general/school/ai_stuff_that_surely_final/Office-Hour-App-Br-e-ad-Fork/optimize.py](C:/Code_general/school/ai_stuff_that_surely_final/Office-Hour-App-Br-e-ad-Fork/optimize.py)
- example teacher input CSV file - [C:/Code_general/school/ai_stuff_that_surely_final/Office-Hour-App-Br-e-ad-Fork/schedules/teacher_availability.csv](C:/Code_general/school/ai_stuff_that_surely_final/Office-Hour-App-Br-e-ad-Fork/schedules/teacher_availability.csv)
- example student input csv file - [C:/Code_general/school/ai_stuff_that_surely_final/Office-Hour-App-Br-e-ad-Fork/schedules/students_availability.csv](C:/Code_general/school/ai_stuff_that_surely_final/Office-Hour-App-Br-e-ad-Fork/schedules/students_availability.csv)
- output file location for csv file - [C:/Code_general/school/ai_stuff_that_surely_final/Office-Hour-App-Br-e-ad-Fork/schedules/](C:/Code_general/school/ai_stuff_that_surely_final/Office-Hour-App-Br-e-ad-Fork/schedules)

### Next steps after Step 3
1. call optimize.py from ai_final.py so that custom csv files can be inputted into there and used as input
2. set up integration with flask so that input from the website can be used as csv input for optimize.py