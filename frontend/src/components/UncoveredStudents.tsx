import type { OptimizeResult } from "../types";
import { DAY_LABELS } from "../types";
import { slotToLabel } from "../lib/slots";

interface UncoveredStudentsProps {
  result: OptimizeResult;
  slotMinutes: number;
}

export function UncoveredStudents({ result, slotMinutes }: UncoveredStudentsProps) {
  const ids = result.uncovered_student_ids ?? [];
  if (ids.length === 0) return null;

  return (
    <article className="card">
      <div>
        <h2 className="card-title">Uncovered students ({ids.length})</h2>
        <p className="muted">
          These students cannot fully attend any of the selected blocks. Their availability is
          shown so you can spot why.
        </p>
      </div>

      <ul className="mt-3 flex flex-col gap-2">
        {ids.map((sid) => {
          const entries = result.student_availability?.[sid];
          return (
            <li
              key={sid}
              className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-2.5 text-sm text-amber-900 dark:border-amber-900/40 dark:bg-amber-950/30 dark:text-amber-100"
            >
              <span className="font-bold">{sid}</span>
              {entries && entries.length > 0 ? (
                <span className="ml-2 text-amber-800 dark:text-amber-200">
                  —{" "}
                  {entries.map((e, i) => (
                    <span key={i}>
                      {DAY_LABELS[e.day]} {slotToLabel(e.start_slot, slotMinutes)}–
                      {slotToLabel(e.end_slot, slotMinutes)}
                      {e.strength === "soft" && (
                        <em className="ml-1 text-xs italic">(soft)</em>
                      )}
                      {i < entries.length - 1 ? "; " : ""}
                    </span>
                  ))}
                </span>
              ) : (
                <span className="ml-2 italic text-amber-700 dark:text-amber-300">
                  — no availability recorded.
                </span>
              )}
            </li>
          );
        })}
      </ul>
    </article>
  );
}
