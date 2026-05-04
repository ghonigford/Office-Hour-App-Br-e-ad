export type Strength = "hard" | "soft";
export type Mode = "available" | "unavailable";
export type EntityKind = "student" | "teacher";
export type SlotMinutes = 15 | 30 | 60;
export type Day = "mon" | "tue" | "wed" | "thu" | "fri";

export const DAYS: Day[] = ["mon", "tue", "wed", "thu", "fri"];
export const DAY_LABELS: Record<Day, string> = {
  mon: "Mon",
  tue: "Tue",
  wed: "Wed",
  thu: "Thu",
  fri: "Fri",
};
export const DAY_LABELS_LONG: Record<Day, string> = {
  mon: "Monday",
  tue: "Tuesday",
  wed: "Wednesday",
  thu: "Thursday",
  fri: "Friday",
};

export interface EntityState {
  id: string;
  cells: Record<string, Strength>;
  mode: Mode;
}

export interface Settings {
  slotMinutes: SlotMinutes;
  dayStartHour: number;
  dayEndHour: number;
  numTeachers: number;
  slotLengthSlots: number;
  numBlocks: number;
}

export type V2Row = [string, Day, number, number, Strength];

export interface AvailabilityEntry {
  day: Day;
  start_slot: number;
  end_slot: number;
  strength?: Strength;
}

export interface Block {
  slot_day: Day;
  start_slot_in_day: number;
  end_slot_in_day: number;
  slot_start_index: number;
  students_covered_in_block: number;
  available_student_ids: string[];
  host?: string;
  students_covered_hard?: number;
  students_covered_soft?: number;
  weighted_coverage?: number;
  hard_student_ids?: string[];
  soft_student_ids?: string[];
}

export interface OptimizeResult {
  blocks: Block[];
  slot_length_slots: number;
  num_blocks_requested: number;
  num_blocks_selected: number;
  students_covered: number;
  total_students: number;
  coverage_ratio: number;
  student_ids: string[];
  covered_student_ids: string[];

  slots_per_day?: number;
  weighted_coverage?: number;
  weighted_coverage_ratio?: number;
  students_covered_hard?: number;
  students_covered_any?: number;
  hard_coverage_ratio?: number;
  hard_student_ids?: string[];
  uncovered_student_ids?: string[];
  teacher_ids?: string[];
  student_availability?: Record<string, AvailabilityEntry[]>;
  teacher_availability?: Record<string, AvailabilityEntry[]>;
  per_student_best_score?: number[];

  slot_day?: Day;
  start_slot_in_day?: number;
  end_slot_in_day?: number;
  slot_start_index?: number;
}

export interface OptimizeRequest {
  settings: {
    slot_minutes: SlotMinutes;
    day_start_hour: number;
    day_end_hour: number;
    num_teachers: number;
    slot_length_slots: number;
    num_blocks: number;
  };
  students: {
    rows_v2?: V2Row[];
    csv_text?: string;
  };
  teachers: {
    rows_v2?: V2Row[];
    csv_text?: string;
  };
}

export interface OptimizeResponse {
  result: OptimizeResult;
  share_token: string;
}

export interface OptimizeErrorResponse {
  error: string;
}
