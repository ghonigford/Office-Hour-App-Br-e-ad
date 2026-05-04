import { useEditor } from "../state/editor";
import type { SlotMinutes } from "../types";

const SLOT_OPTIONS: SlotMinutes[] = [15, 30, 60];

export function SettingsCard() {
  const { state, dispatch } = useEditor();
  const { settings } = state;

  return (
    <article className="card">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="card-title">Schedule settings</h2>
          <p className="muted">
            Configure granularity and the day window — the calendars below adapt to these.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500 dark:text-slate-400">
          <span>
            <span className="legend-swatch hard mr-1" /> Hard = counts 1.0
          </span>
          <span>
            <span className="legend-swatch soft mr-1" /> Soft = counts 0.5
          </span>
        </div>
      </div>

      <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="flex flex-col gap-1">
          <label className="input-label" htmlFor="slot-minutes">
            Slot granularity
          </label>
          <select
            id="slot-minutes"
            className="select"
            value={settings.slotMinutes}
            onChange={(e) =>
              dispatch({
                type: "set_settings",
                patch: { slotMinutes: Number(e.target.value) as SlotMinutes },
              })
            }
          >
            {SLOT_OPTIONS.map((m) => (
              <option key={m} value={m}>
                {m} minutes
              </option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-1">
          <label className="input-label" htmlFor="day-start">
            Day window start (hour)
          </label>
          <input
            id="day-start"
            className="input"
            type="number"
            min={0}
            max={23}
            value={settings.dayStartHour}
            onChange={(e) =>
              dispatch({
                type: "set_settings",
                patch: { dayStartHour: clampInt(e.target.value, 0, 23, 8) },
              })
            }
          />
        </div>

        <div className="flex flex-col gap-1">
          <label className="input-label" htmlFor="day-end">
            Day window end (hour)
          </label>
          <input
            id="day-end"
            className="input"
            type="number"
            min={1}
            max={24}
            value={settings.dayEndHour}
            onChange={(e) => {
              const next = clampInt(e.target.value, 1, 24, 20);
              const dayEndHour =
                next <= settings.dayStartHour
                  ? Math.min(24, settings.dayStartHour + 1)
                  : next;
              dispatch({ type: "set_settings", patch: { dayEndHour } });
            }}
          />
        </div>

        <div className="flex flex-col gap-1">
          <label className="input-label" htmlFor="num-teachers">
            Number of teachers
          </label>
          <input
            id="num-teachers"
            className="input"
            type="number"
            min={1}
            max={10}
            value={settings.numTeachers}
            onChange={(e) =>
              dispatch({
                type: "set_settings",
                patch: { numTeachers: clampInt(e.target.value, 1, 10, 1) },
              })
            }
          />
        </div>
      </div>
    </article>
  );
}

function clampInt(raw: string, min: number, max: number, fallback: number): number {
  const parsed = parseInt(raw, 10);
  if (Number.isNaN(parsed)) return fallback;
  return Math.max(min, Math.min(max, parsed));
}
