import datetime
import csv
import os


def load_availability_from_csv(filepath):
    """
    Loads student availability from a shared CSV file.
    
    Expected columns:
      student, Monday_start, Monday_end, Tuesday_start, Tuesday_end, ..., Friday_start, Friday_end

    Each student has one row. Blank start/end means unavailable that day.
    Returns (availability dict, num_students).
    """
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    availability = {day: [] for day in days}
    num_students = 0

    if not os.path.exists(filepath):
        print(f"  Error: File '{filepath}' not found.")
        return availability, num_students

    with open(filepath, newline='') as f:
        reader = csv.DictReader(f)

        # Validate that all expected columns are present
        expected_cols = ['student'] + [f"{day}_{suffix}" for day in days for suffix in ('start', 'end')]
        missing = [col for col in expected_cols if col not in reader.fieldnames]
        if missing:
            print(f"  Error: CSV is missing columns: {', '.join(missing)}")
            return availability, num_students

        for row in reader:
            student_name = row['student'].strip()
            if not student_name:
                continue  # Skip blank rows

            num_students += 1
            student_slots = {day: [] for day in days}

            for day in days:
                start_raw = row[f"{day}_start"].strip()
                end_raw   = row[f"{day}_end"].strip()

                if not start_raw and not end_raw:
                    continue  # Student unavailable this day

                try:
                    s = datetime.datetime.strptime(start_raw, "%H:%M").time()
                    e = datetime.datetime.strptime(end_raw,   "%H:%M").time()
                    if s >= e:
                        print(f"  Warning: {student_name}'s {day} range {start_raw}-{end_raw} is invalid (start >= end). Skipping.")
                        continue
                    student_slots[day].append((s, e))
                except ValueError:
                    print(f"  Warning: {student_name}'s {day} has an unrecognized time format ('{start_raw}', '{end_raw}'). Skipping.")

            for day in days:
                availability[day].append(student_slots[day])

            print(f"  ✓ Loaded {student_name}")

    return availability, num_students


def generate_csv_template(filepath='availability_template.csv'):
    """
    Writes a blank CSV template that students can fill in and return to the faculty.
    """
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    headers = ['student'] + [f"{day}_{suffix}" for day in days for suffix in ('start', 'end')]

    with open(filepath, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        # Write two example rows so students know the format
        writer.writerow(['Alice', '09:00', '11:00', '13:00', '15:00', '', '', '10:00', '12:00', '', ''])
        writer.writerow(['Bob',   '',      '',      '10:00', '13:00', '09:00', '11:00', '', '', '', ''])

    print(f"  Template saved to '{filepath}'. Share this with students to fill in and return.")


def get_student_availability():
    """
    Interactively collects availability from multiple students.
    Returns (availability dict, num_students).

    availability format:
    {
        'Monday':    [ [(start, end), ...], [(start, end), ...] ],  # one sublist per student
        'Tuesday':   [ ... ],
        ...
    }
    """
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    availability = {day: [] for day in days}

    print("\n--- Student Availability Input ---")
    print("For each student, enter their free time ranges per day.")
    print("Time format: HH:MM  (24-hour), e.g. 09:00 or 14:30")
    print("Press Enter (blank) to skip a day or finish adding ranges.\n")

    num_students = 0

    while True:
        student_name = input("Enter student name (or 'done' to finish): ").strip()
        if student_name.lower() == 'done':
            break
        if not student_name:
            continue

        num_students += 1
        student_slots = {day: [] for day in days}

        for day in days:
            print(f"  {day} — enter available ranges (blank to skip):")
            while True:
                raw = input(f"    Start time (or blank to move on): ").strip()
                if not raw:
                    break
                end_raw = input(f"    End time: ").strip()
                if not end_raw:
                    print("    End time required. Skipping this range.")
                    break
                try:
                    s = datetime.datetime.strptime(raw, "%H:%M").time()
                    e = datetime.datetime.strptime(end_raw, "%H:%M").time()
                    if s >= e:
                        print("    Start must be before end. Try again.")
                        continue
                    student_slots[day].append((s, e))
                except ValueError:
                    print("    Invalid format. Use HH:MM (e.g. 09:00). Try again.")

        for day in days:
            availability[day].append(student_slots[day])

        print(f"  ✓ {student_name} added.\n")

    return availability, num_students


def find_best_slots(availability, num_students, min_students=1, slot_duration_minutes=30):
    """
    Find best office hour slots where the most students are available.
    Returns a list with (day, start_time, end_time, number_of_students_available)
    """
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    slot_delta = datetime.timedelta(minutes=slot_duration_minutes)
    slots = []

    for i, day in enumerate(days):
        current = datetime.datetime(2000, 1, 1, 8, 0)   # 8:00 AM
        end     = datetime.datetime(2000, 1, 1, 18, 0)  # 6:00 PM
        student_schedules = availability[day]

        while current + slot_delta <= end:
            start_time = current.time()
            end_time   = (current + slot_delta).time()
            count = 0

            for s_ranges in student_schedules:
                for s_start, s_end in s_ranges:
                    latest_start  = max(start_time, s_start)
                    earliest_end  = min(end_time, s_end)
                    slot_fits = (
                        latest_start < earliest_end and
                        (datetime.datetime.combine(current.date(), earliest_end) -
                         datetime.datetime.combine(current.date(), latest_start)).total_seconds()
                        >= slot_delta.total_seconds()
                    )
                    if slot_fits:
                        count += 1
                        break

            if count >= min_students:
                slots.append((day, start_time.strftime('%H:%M'), end_time.strftime('%H:%M'), count))

            current += datetime.timedelta(minutes=15)

    slots.sort(key=lambda x: (-x[3], x[0], x[1]))
    return slots


def filter_faculty_unavailability(slots, blocked):
    """
    Removes slots that overlap with the faculty's blocked times.
    blocked: list of (day, start_str, end_str) tuples the faculty can't make.
    """
    def overlaps(slot, block):
        return slot[0] == block[0] and not (slot[2] <= block[1] or slot[1] >= block[2])
    return [s for s in slots if not any(overlaps(s, b) for b in blocked)]


def get_faculty_blocked_times():
    """
    Interactively collects time ranges that the faculty is unavailable.
    Returns a list of (day, start_str, end_str) tuples.
    """
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    blocked = []

    print("\n--- Faculty Unavailability Input ---")
    print("Enter time ranges when you (the faculty) are NOT available.")
    print("Time format: HH:MM  (24-hour). Press Enter (blank) to skip a day.\n")

    for day in days:
        print(f"  {day} — enter blocked ranges (blank to skip):")
        while True:
            raw = input(f"    Block start time (or blank to move on): ").strip()
            if not raw:
                break
            end_raw = input(f"    Block end time: ").strip()
            if not end_raw:
                print("    End time required. Skipping this range.")
                break
            try:
                s = datetime.datetime.strptime(raw, "%H:%M")
                e = datetime.datetime.strptime(end_raw, "%H:%M")
                if s >= e:
                    print("    Start must be before end. Try again.")
                    continue
                blocked.append((day, raw, end_raw))
            except ValueError:
                print("    Invalid format. Use HH:MM (e.g. 09:00). Try again.")

    return blocked


def main():
    print("Faculty Office Hours Scheduler")
    print("\nHow would you like to enter student availability?")
    print("  1 - Manual input (type in each student's schedule)")
    print("  2 - Load from CSV file")
    print("  3 - Generate a blank CSV template for students to fill in")

    choice = input("\n  → ").strip()

    if choice == '1':
        availability, num_students = get_student_availability()

    elif choice == '2':
        filepath = input("  Enter path to CSV file (e.g. availability.csv): ").strip()
        print()
        availability, num_students = load_availability_from_csv(filepath)

    elif choice == '3':
        generate_csv_template()
        return  # Nothing more to do — faculty shares the template, then reruns with option 2

    else:
        print("  Invalid choice. Exiting.")
        return

    if num_students == 0:
        print("No students loaded. Exiting.")
        return

    slots = find_best_slots(availability, num_students, min_students=1)

    if not slots:
        print("No available slots found where any student is available.")
        return

    print("\nWould you like to enter times YOU are unavailable? (yes/no)")
    if input("  → ").strip().lower() in ('yes', 'y'):
        blocked = get_faculty_blocked_times()
        slots = filter_faculty_unavailability(slots, blocked)
        if not slots:
            print("No slots remain after applying your unavailability. Consider revising your blocked times.")
            return

    print("\nTop recommended office hour slots (most student availability first):")
    for slot in slots[:10]:
        pct = (slot[3] / num_students) * 100
        print(f"{slot[0]} {slot[1]}-{slot[2]}  →  {slot[3]}/{num_students} students ({pct:.0f}%)")


if __name__ == '__main__':
    main()