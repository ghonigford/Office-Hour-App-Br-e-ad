import datetime

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
        student_name = input(f"Enter student name (or 'done' to finish): ").strip()
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

        # Append this student's ranges to the shared availability dict
        for day in days:
            availability[day].append(student_slots[day])

        print(f"  ✓ {student_name} added.\n")

    return availability, num_students


# The function 'find_best_slots' computes the most optimal time slots for scheduling office hours
# based on student availability throughout the workweek.
def find_best_slots(availability, num_students, min_students=1, slot_duration_minutes=30):
    """
    Find best office hour slots where the most students are available.
    Returns a list with (day, start_time, end_time, number_of_students_available)
    """
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']  # Office hours only scheduled for weekdays
    slot_delta = datetime.timedelta(minutes=slot_duration_minutes)    # Duration of each considered time slot
    slots = []   # This will hold all possible time slots and how many students can attend

    for i, day in enumerate(days):
        # Consider possible office hours from 8am to 6pm for each day
        current = datetime.datetime(2000,1,1,8,0)  # arbitrary date, but time matters (8:00 AM)
        end = datetime.datetime(2000,1,1,18,0)     # end time for office hours (6:00 PM)
        student_schedules = availability[day]      # List of lists; each sublist is a student's available ranges

        while current + slot_delta <= end:
            # Determine window of current potential office hour slot
            start_time = current.time()
            end_time = (current + slot_delta).time()
            count = 0 # Number of students available in this slot

            for s_ranges in student_schedules:  # For each student's availability ranges on this day
                for s_start, s_end in s_ranges: # Each (start, end) tuple: a student's available window
                    # Check if slot is completely within student's available range
                    latest_start = max(start_time, s_start)
                    earliest_end = min(end_time, s_end)
                    # Ensure overlap is at least as long as the slot duration so the slot "fits"
                    slot_fits = (
                        latest_start < earliest_end and 
                        (datetime.datetime.combine(current.date(), earliest_end) - 
                        datetime.datetime.combine(current.date(), latest_start)).total_seconds() 
                        >= slot_delta.total_seconds()
                    )
                    if slot_fits:
                        count += 1
                        break  # Only count this student once for this slot

            if count >= min_students:
                # Store this slot if it fits the minimum students required
                # Format times as 'HH:MM' strings for printing
                slots.append( (day, start_time.strftime('%H:%M'), end_time.strftime('%H:%M'), count) )

            current += datetime.timedelta(minutes=15)  # Advance by 15 minutes for overlapping slots

    # Sort first by descending number of students available, then by day, then by start time for ranking
    slots.sort(key=lambda x: (-x[3], x[0], x[1]))
    return slots


def filter_faculty_unavailability(slots, blocked):
    """
    Removes slots that overlap with the faculty's blocked times.
    blocked: list of (day, start_str, end_str) tuples the faculty can't make
    e.g. [('Monday', '09:00', '10:00'), ('Friday', '14:00', '18:00')]
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

    availability, num_students = get_student_availability()  # Gather all student availabilities from input

    # Handle edge case where no students were entered
    if num_students == 0:
        print("No students entered. Exiting.")
        return

    slots = find_best_slots(availability, num_students, min_students=1)  # Find slots with at least one student

    if not slots:
        # If there are no possible slots, let user know
        print("No available slots found where any student is available.")
        return

    # Optionally filter out times the faculty is unavailable
    print("\nWould you like to enter times YOU are unavailable? (yes/no)")
    if input("  → ").strip().lower() in ('yes', 'y'):
        blocked = get_faculty_blocked_times()
        slots = filter_faculty_unavailability(slots, blocked)
        if not slots:
            print("No slots remain after applying your unavailability. Consider revising your blocked times.")
            return

    # Print out the top 10 slots where the most students can attend, with percentage coverage
    print("\nTop recommended office hour slots (most student availability first):")
    for slot in slots[:10]:
        pct = (slot[3] / num_students) * 100
        print(f"{slot[0]} {slot[1]}-{slot[2]}  →  {slot[3]}/{num_students} students ({pct:.0f}%)")


if __name__ == '__main__':
    main()