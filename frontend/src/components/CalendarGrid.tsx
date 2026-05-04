import { memo, useEffect, useMemo, useRef } from "react";
import type { Day, EntityKind, EntityState, Settings, Strength } from "../types";
import { DAYS, DAY_LABELS } from "../types";
import {
  cellKey,
  endSlotForSettings,
  slotToLabel,
  startSlotForSettings,
} from "../lib/slots";

export interface PaintChange {
  day: Day;
  slot: number;
  strength: Strength | null;
}

export interface CalendarGridProps {
  settings: Settings;
  entity: EntityState;
  paintStrength: Strength;
  kind: EntityKind;
  onPaint: (changes: PaintChange[]) => void;
}

interface DragState {
  active: boolean;
  action: "paint" | "erase";
  paint: Strength;
  visited: Set<string>;
  pending: Array<{ day: Day; slot: number; strength: Strength | null }>;
  flushScheduled: boolean;
}

function CalendarGridImpl({
  settings,
  entity,
  paintStrength,
  kind,
  onPaint,
}: CalendarGridProps) {
  const startS = startSlotForSettings(settings);
  const endS = endSlotForSettings(settings);
  const slotMinutes = settings.slotMinutes;
  const cells = entity.cells;
  const mode = entity.mode;

  const dragRef = useRef<DragState>({
    active: false,
    action: "paint",
    paint: "hard",
    visited: new Set<string>(),
    pending: [],
    flushScheduled: false,
  });
  const onPaintRef = useRef(onPaint);
  useEffect(() => {
    onPaintRef.current = onPaint;
  }, [onPaint]);

  const flushPending = () => {
    const drag = dragRef.current;
    if (drag.pending.length === 0) {
      drag.flushScheduled = false;
      return;
    }
    const batch = drag.pending;
    drag.pending = [];
    drag.flushScheduled = false;
    onPaintRef.current(batch);
  };

  const queueChange = (
    day: Day,
    slot: number,
    strength: Strength | null,
  ) => {
    const drag = dragRef.current;
    drag.pending.push({ day, slot, strength });
    if (!drag.flushScheduled) {
      drag.flushScheduled = true;
      requestAnimationFrame(flushPending);
    }
  };

  const handleCellPress = (day: Day, slot: number, current: Strength | null) => {
    const drag = dragRef.current;
    drag.visited.clear();
    drag.paint = paintStrength;
    drag.action = current === paintStrength ? "erase" : "paint";
    drag.active = true;
    drag.visited.add(cellKey(day, slot));
    queueChange(day, slot, drag.action === "erase" ? null : paintStrength);
  };

  const handleCellEnter = (day: Day, slot: number) => {
    const drag = dragRef.current;
    if (!drag.active) return;
    const key = cellKey(day, slot);
    if (drag.visited.has(key)) return;
    drag.visited.add(key);
    queueChange(day, slot, drag.action === "erase" ? null : drag.paint);
  };

  useEffect(() => {
    const stop = () => {
      dragRef.current.active = false;
      dragRef.current.visited.clear();
      flushPending();
    };
    window.addEventListener("mouseup", stop);
    window.addEventListener("blur", stop);
    return () => {
      window.removeEventListener("mouseup", stop);
      window.removeEventListener("blur", stop);
    };
  }, []);

  const slotIndices = useMemo(() => {
    const out: number[] = [];
    for (let s = startS; s < endS; s += 1) out.push(s);
    return out;
  }, [startS, endS]);

  return (
    <div className="scroll-area">
      <div
        className="grid min-w-[640px]"
        style={{ gridTemplateColumns: "96px repeat(5, minmax(80px, 1fr))" }}
        onContextMenu={(e) => e.preventDefault()}
      >
        <div className="grid-head">Time</div>
        {DAYS.map((day) => (
          <div key={`head-${day}`} className="grid-head">
            {DAY_LABELS[day]}
          </div>
        ))}
        {slotIndices.map((slot) => (
          <CalendarRow
            key={`row-${slot}`}
            slot={slot}
            slotMinutes={slotMinutes}
            cells={cells}
            mode={mode}
            kind={kind}
            onCellPress={handleCellPress}
            onCellEnter={handleCellEnter}
          />
        ))}
      </div>
    </div>
  );
}

interface CalendarRowProps {
  slot: number;
  slotMinutes: number;
  cells: Record<string, Strength>;
  mode: EntityState["mode"];
  kind: EntityKind;
  onCellPress: (day: Day, slot: number, current: Strength | null) => void;
  onCellEnter: (day: Day, slot: number) => void;
}

const CalendarRow = memo(function CalendarRow({
  slot,
  slotMinutes,
  cells,
  mode,
  onCellPress,
  onCellEnter,
}: CalendarRowProps) {
  return (
    <>
      <div className="grid-time">{slotToLabel(slot, slotMinutes)}</div>
      {DAYS.map((day) => {
        const state = cells[cellKey(day, slot)] ?? null;
        return (
          <div
            key={`${day}-${slot}`}
            className="grid-slot min-h-[26px] py-1"
            data-state={state ?? ""}
            data-mode={mode}
            onMouseDown={(e) => {
              if (e.button !== 0) return;
              e.preventDefault();
              onCellPress(day, slot, state);
            }}
            onMouseEnter={() => onCellEnter(day, slot)}
          />
        );
      })}
    </>
  );
});

export const CalendarGrid = memo(CalendarGridImpl);
