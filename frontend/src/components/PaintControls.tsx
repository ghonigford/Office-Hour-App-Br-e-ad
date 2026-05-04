import type { EntityKind, Mode, Strength } from "../types";

interface PaintControlsProps {
  kind: EntityKind;
  mode: Mode;
  strength: Strength;
  onModeChange: (mode: Mode) => void;
  onStrengthChange: (strength: Strength) => void;
  onClear: () => void;
}

export function PaintControls({
  kind,
  mode,
  strength,
  onModeChange,
  onStrengthChange,
  onClear,
}: PaintControlsProps) {
  const entityLabel = kind === "student" ? "student" : "teacher";
  const hint =
    mode === "available"
      ? `Click and drag to mark when this ${entityLabel} IS free. Hard = definitely free, soft = could attend but would prefer not to.`
      : `Click and drag to mark when this ${entityLabel} is NOT free. Hard = definitely busy, soft = busy but movable; everything else inside the day window is treated as free.`;

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 p-2 dark:border-slate-800 dark:bg-slate-900/40">
        <span className="muted px-1">Input mode:</span>
        <div className="pill-group" role="tablist">
          <button
            type="button"
            className="pill"
            data-active={mode === "available"}
            onClick={() => onModeChange("available")}
          >
            Mark availability
          </button>
          <button
            type="button"
            className="pill"
            data-active={mode === "unavailable"}
            onClick={() => onModeChange("unavailable")}
          >
            Mark unavailability
          </button>
        </div>
        <span className="muted px-1">Strength:</span>
        <div className="pill-group">
          <button
            type="button"
            className="pill"
            data-active={strength === "hard"}
            data-strength="hard"
            onClick={() => onStrengthChange("hard")}
          >
            Hard
          </button>
          <button
            type="button"
            className="pill"
            data-active={strength === "soft"}
            data-strength="soft"
            onClick={() => onStrengthChange("soft")}
          >
            Soft
          </button>
        </div>
        <div className="ml-auto">
          <button type="button" className="btn-danger" onClick={onClear}>
            Clear grid
          </button>
        </div>
      </div>
      <p className="muted">{hint}</p>
    </div>
  );
}
