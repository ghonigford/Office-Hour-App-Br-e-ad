import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useReducer,
  type Dispatch,
  type ReactNode,
} from "react";
import type {
  Day,
  EntityKind,
  EntityState,
  Mode,
  Settings,
  SlotMinutes,
  Strength,
} from "../types";
import { cellKey, migrateCellsToGranularity } from "../lib/slots";

export interface EditorState {
  settings: Settings;
  students: EntityState[];
  teachers: EntityState[];
  selectedStudent: string;
  selectedTeacher: string;
  paintStrength: Record<EntityKind, Strength>;
  studentInputMode: "manual" | "csv";
  teacherInputMode: "manual" | "csv";
  studentCsvText: string;
  teacherCsvText: string;
  studentCsvName: string;
  teacherCsvName: string;
}

export type Action =
  | { type: "set_settings"; patch: Partial<Settings> }
  | { type: "add_student"; id: string }
  | { type: "remove_student"; id: string }
  | { type: "select_student"; id: string }
  | { type: "set_student_mode"; id: string; mode: Mode }
  | { type: "clear_student"; id: string }
  | { type: "rename_student"; oldId: string; newId: string }
  | { type: "ensure_teachers"; count: number }
  | { type: "select_teacher"; id: string }
  | { type: "set_teacher_mode"; id: string; mode: Mode }
  | { type: "clear_teacher"; id: string }
  | { type: "remove_teacher"; id: string }
  | { type: "rename_teacher"; oldId: string; newId: string }
  | {
      type: "paint_cells";
      kind: EntityKind;
      id: string;
      changes: Array<{ day: Day; slot: number; strength: Strength | null }>;
    }
  | { type: "set_paint_strength"; kind: EntityKind; strength: Strength }
  | { type: "set_input_mode"; kind: EntityKind; mode: "manual" | "csv" }
  | { type: "set_csv"; kind: EntityKind; text: string; name: string }
  | { type: "load_state"; state: EditorState }
  | { type: "reset" };

const DEFAULT_SETTINGS: Settings = {
  slotMinutes: 30,
  dayStartHour: 8,
  dayEndHour: 20,
  numTeachers: 1,
  slotLengthSlots: 2,
  numBlocks: 1,
};

const makeEntity = (id: string): EntityState => ({
  id,
  cells: {},
  mode: "available",
});

export const INITIAL_STATE: EditorState = {
  settings: { ...DEFAULT_SETTINGS },
  students: [makeEntity("s1")],
  teachers: [makeEntity("prof1")],
  selectedStudent: "s1",
  selectedTeacher: "prof1",
  paintStrength: { student: "hard", teacher: "hard" },
  studentInputMode: "manual",
  teacherInputMode: "manual",
  studentCsvText: "",
  teacherCsvText: "",
  studentCsvName: "",
  teacherCsvName: "",
};

function withUpdatedEntity(
  list: EntityState[],
  id: string,
  patch: Partial<EntityState> | ((e: EntityState) => Partial<EntityState>),
): EntityState[] {
  return list.map((e) => {
    if (e.id !== id) return e;
    const p = typeof patch === "function" ? patch(e) : patch;
    return { ...e, ...p };
  });
}

function ensureTeacherList(teachers: EntityState[], count: number): EntityState[] {
  const target = Math.max(1, Math.min(10, count));
  if (teachers.length >= target) return teachers;
  const out = [...teachers];
  for (let i = teachers.length; i < target; i += 1) {
    const id = `prof${i + 1}`;
    if (!out.find((e) => e.id === id)) out.push(makeEntity(id));
  }
  return out;
}

function reducer(state: EditorState, action: Action): EditorState {
  switch (action.type) {
    case "set_settings": {
      const merged = { ...state.settings, ...action.patch };
      let nextStudents = state.students;
      let nextTeachers = state.teachers;
      if (
        action.patch.slotMinutes !== undefined &&
        action.patch.slotMinutes !== state.settings.slotMinutes
      ) {
        const newSlot = action.patch.slotMinutes as SlotMinutes;
        nextStudents = state.students.map((e) => ({
          ...e,
          cells: migrateCellsToGranularity(e.cells, newSlot),
        }));
        nextTeachers = state.teachers.map((e) => ({
          ...e,
          cells: migrateCellsToGranularity(e.cells, newSlot),
        }));
      }
      if (
        action.patch.numTeachers !== undefined &&
        action.patch.numTeachers > state.teachers.length
      ) {
        nextTeachers = ensureTeacherList(nextTeachers, action.patch.numTeachers);
      }
      let selectedTeacher = state.selectedTeacher;
      const visibleTeachers = nextTeachers.slice(0, merged.numTeachers);
      if (!visibleTeachers.find((t) => t.id === selectedTeacher)) {
        selectedTeacher = visibleTeachers[0]?.id ?? "";
      }
      return {
        ...state,
        settings: merged,
        students: nextStudents,
        teachers: nextTeachers,
        selectedTeacher,
      };
    }

    case "add_student": {
      const id = action.id.trim();
      if (!id) return state;
      if (state.students.find((e) => e.id === id)) {
        return { ...state, selectedStudent: id };
      }
      return {
        ...state,
        students: [...state.students, makeEntity(id)],
        selectedStudent: id,
      };
    }

    case "remove_student": {
      if (state.students.length <= 1) return state;
      const remaining = state.students.filter((e) => e.id !== action.id);
      const selectedStudent =
        state.selectedStudent === action.id
          ? remaining[0]?.id ?? ""
          : state.selectedStudent;
      return { ...state, students: remaining, selectedStudent };
    }

    case "select_student":
      return { ...state, selectedStudent: action.id };

    case "set_student_mode":
      return {
        ...state,
        students: withUpdatedEntity(state.students, action.id, { mode: action.mode }),
      };

    case "clear_student":
      return {
        ...state,
        students: withUpdatedEntity(state.students, action.id, { cells: {} }),
      };

    case "rename_student": {
      const oldId = action.oldId;
      const newId = action.newId.trim();
      if (!newId || oldId === newId) return state;
      if (state.students.find((e) => e.id === newId)) return state;
      const students = state.students.map((e) =>
        e.id === oldId ? { ...e, id: newId } : e,
      );
      return {
        ...state,
        students,
        selectedStudent:
          state.selectedStudent === oldId ? newId : state.selectedStudent,
      };
    }

    case "ensure_teachers": {
      const teachers = ensureTeacherList(state.teachers, action.count);
      return { ...state, teachers };
    }

    case "select_teacher":
      return { ...state, selectedTeacher: action.id };

    case "set_teacher_mode":
      return {
        ...state,
        teachers: withUpdatedEntity(state.teachers, action.id, { mode: action.mode }),
      };

    case "clear_teacher":
      return {
        ...state,
        teachers: withUpdatedEntity(state.teachers, action.id, { cells: {} }),
      };

    case "remove_teacher": {
      const visibleCount = state.settings.numTeachers;
      if (state.teachers.length <= 1) return state;
      const idx = state.teachers.findIndex((e) => e.id === action.id);
      if (idx === -1) return state;
      const remaining = state.teachers.filter((e) => e.id !== action.id);
      const selectedTeacher =
        state.selectedTeacher === action.id
          ? remaining[Math.min(idx, remaining.length - 1)].id
          : state.selectedTeacher;
      const newNumTeachers = Math.min(visibleCount, remaining.length);
      return {
        ...state,
        teachers: remaining,
        selectedTeacher,
        settings: { ...state.settings, numTeachers: newNumTeachers || 1 },
      };
    }

    case "rename_teacher": {
      const oldId = action.oldId;
      const newId = action.newId.trim();
      if (!newId || oldId === newId) return state;
      if (state.teachers.find((e) => e.id === newId)) return state;
      const teachers = state.teachers.map((e) =>
        e.id === oldId ? { ...e, id: newId } : e,
      );
      return {
        ...state,
        teachers,
        selectedTeacher:
          state.selectedTeacher === oldId ? newId : state.selectedTeacher,
      };
    }

    case "paint_cells": {
      const list = action.kind === "student" ? state.students : state.teachers;
      const updater = (e: EntityState) => {
        const cells = { ...e.cells };
        for (const change of action.changes) {
          const k = cellKey(change.day, change.slot);
          if (change.strength == null) delete cells[k];
          else cells[k] = change.strength;
        }
        return { cells };
      };
      const next = withUpdatedEntity(list, action.id, updater);
      return action.kind === "student"
        ? { ...state, students: next }
        : { ...state, teachers: next };
    }

    case "set_paint_strength":
      return {
        ...state,
        paintStrength: { ...state.paintStrength, [action.kind]: action.strength },
      };

    case "set_input_mode":
      return action.kind === "student"
        ? { ...state, studentInputMode: action.mode }
        : { ...state, teacherInputMode: action.mode };

    case "set_csv":
      return action.kind === "student"
        ? { ...state, studentCsvText: action.text, studentCsvName: action.name }
        : { ...state, teacherCsvText: action.text, teacherCsvName: action.name };

    case "load_state":
      return action.state;

    case "reset":
      return INITIAL_STATE;

    default:
      return state;
  }
}

interface EditorContextValue {
  state: EditorState;
  dispatch: Dispatch<Action>;
  visibleTeachers: EntityState[];
  selectedStudentEntity: EntityState | undefined;
  selectedTeacherEntity: EntityState | undefined;
}

const EditorContext = createContext<EditorContextValue | null>(null);

export function EditorProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, INITIAL_STATE);

  const visibleTeachers = useMemo(
    () => state.teachers.slice(0, state.settings.numTeachers),
    [state.teachers, state.settings.numTeachers],
  );

  const selectedStudentEntity = useMemo(
    () => state.students.find((e) => e.id === state.selectedStudent),
    [state.students, state.selectedStudent],
  );

  const selectedTeacherEntity = useMemo(
    () => visibleTeachers.find((e) => e.id === state.selectedTeacher),
    [visibleTeachers, state.selectedTeacher],
  );

  const value = useMemo(
    () => ({
      state,
      dispatch,
      visibleTeachers,
      selectedStudentEntity,
      selectedTeacherEntity,
    }),
    [state, visibleTeachers, selectedStudentEntity, selectedTeacherEntity],
  );

  return <EditorContext.Provider value={value}>{children}</EditorContext.Provider>;
}

export function useEditor(): EditorContextValue {
  const ctx = useContext(EditorContext);
  if (!ctx) throw new Error("useEditor must be used inside <EditorProvider>");
  return ctx;
}

export const useEditorActions = () => {
  const { dispatch } = useEditor();
  return useCallback(
    (action: Action) => {
      dispatch(action);
    },
    [dispatch],
  );
};
