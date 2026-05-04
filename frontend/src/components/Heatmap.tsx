import { useMemo } from "react";
import { useEditor } from "../state/editor";
import {
  endSlotForSettings,
  slotToLabel,
  startSlotForSettings,
  weightForCell,
} from "../lib/slots";
import { DAYS, DAY_LABELS } from "../types";

export function Heatmap() {
  const { state, visibleTeachers } = useEditor();
  const { settings, students } = state;
  const startS = startSlotForSettings(settings);
  const endS = endSlotForSettings(settings);

  const slotIndices = useMemo(() => {
    const out: number[] = [];
    for (let s = startS; s < endS; s += 1) out.push(s);
    return out;
  }, [startS, endS]);

  const totalStudents = students.length;

  return (
    <article className="card">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="card-title">Live availability heatmap</h2>
          <p className="muted">
            How many students are free per slot, masked by the union of teacher availability.
          </p>
        </div>
        <span className="muted text-xs">{totalStudents} students · {visibleTeachers.length} teachers</span>
      </div>

      <div className="mt-3 scroll-area">
        <div
          className="grid min-w-[640px]"
          style={{ gridTemplateColumns: "96px repeat(5, minmax(80px, 1fr))" }}
        >
          <div className="grid-head">Time</div>
          {DAYS.map((d) => (
            <div key={`head-${d}`} className="grid-head">
              {DAY_LABELS[d]}
            </div>
          ))}
          {slotIndices.map((slot) => (
            <HeatmapRow
              key={slot}
              slot={slot}
              totalStudents={totalStudents}
              slotMinutes={settings.slotMinutes}
              students={students}
              teachers={visibleTeachers}
            />
          ))}
        </div>
      </div>
    </article>
  );
}

interface HeatmapRowProps {
  slot: number;
  slotMinutes: number;
  totalStudents: number;
  students: ReturnType<typeof useEditor>["state"]["students"];
  teachers: ReturnType<typeof useEditor>["visibleTeachers"];
}

function HeatmapRow({ slot, slotMinutes, totalStudents, students, teachers }: HeatmapRowProps) {
  return (
    <>
      <div className="grid-time">{slotToLabel(slot, slotMinutes)}</div>
      {DAYS.map((day) => {
        let teacherWeight = 0;
        for (const t of teachers) {
          teacherWeight = Math.max(teacherWeight, weightForCell(t, day, slot));
        }

        if (teacherWeight === 0) {
          return (
            <div
              key={`${day}-${slot}`}
              className="grid-cell bg-slate-100 text-center text-xs text-slate-300 dark:bg-slate-900 dark:text-slate-700"
            />
          );
        }

        let count = 0;
        let weighted = 0;
        for (const sEnt of students) {
          const w = weightForCell(sEnt, day, slot);
          if (w > 0) count += 1;
          weighted += Math.min(w, teacherWeight);
        }

        const intensity = totalStudents > 0 ? count / totalStudents : 0;
        const r = Math.round(255 - intensity * 200);
        const g = Math.round(255 - intensity * 80);
        const b = 255;
        const bg = `rgb(${r}, ${g}, ${b})`;

        return (
          <div
            key={`${day}-${slot}`}
            className="grid-cell text-center text-xs font-semibold text-slate-800"
            style={{ backgroundColor: bg }}
            title={`${count}/${totalStudents} students free; weighted ${weighted.toFixed(1)}`}
          >
            {count > 0 ? count : ""}
          </div>
        );
      })}
    </>
  );
}
