import { useMemo } from "react";
import { DAYS, DAY_LABELS } from "../types";
import type { Block, Day } from "../types";
import { slotsPerDay, slotToLabel } from "../lib/slots";

interface ResultCalendarProps {
  blocks: Block[];
  slotMinutes: number;
}

export function ResultCalendar({ blocks, slotMinutes }: ResultCalendarProps) {
  const { startSlot, endSlot, lookup } = useMemo(() => {
    if (blocks.length === 0) {
      return { startSlot: 0, endSlot: 0, lookup: new Map<string, Block>() };
    }
    const minStart = Math.min(...blocks.map((b) => b.start_slot_in_day));
    const maxEnd = Math.max(...blocks.map((b) => b.end_slot_in_day));
    const padding = Math.max(2, Math.ceil(60 / slotMinutes));
    const total = slotsPerDay(slotMinutes as 15 | 30 | 60);
    const start = Math.max(0, minStart - padding);
    const end = Math.min(total, maxEnd + padding);
    const lookup = new Map<string, Block>();
    blocks.forEach((b) => {
      for (let s = b.start_slot_in_day; s < b.end_slot_in_day; s += 1) {
        lookup.set(`${b.slot_day}:${s}`, b);
      }
    });
    return { startSlot: start, endSlot: end, lookup };
  }, [blocks, slotMinutes]);

  const slotIndices: number[] = [];
  for (let s = startSlot; s < endSlot; s += 1) slotIndices.push(s);

  return (
    <div className="scroll-area max-h-[60vh]">
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
          <Row
            key={slot}
            slot={slot}
            slotMinutes={slotMinutes}
            lookup={lookup}
          />
        ))}
      </div>
    </div>
  );
}

interface RowProps {
  slot: number;
  slotMinutes: number;
  lookup: Map<string, Block>;
}

function Row({ slot, slotMinutes, lookup }: RowProps) {
  return (
    <>
      <div className="grid-time">{slotToLabel(slot, slotMinutes)}</div>
      {DAYS.map((day: Day) => {
        const block = lookup.get(`${day}:${slot}`);
        return (
          <div
            key={`${day}-${slot}`}
            className="grid-slot min-h-[26px] py-1"
            data-state=""
            data-result={block ? "hard" : ""}
            title={
              block
                ? `Host: ${block.host || "—"} · ${block.students_covered_in_block} students`
                : ""
            }
          >
            {block?.host ?? ""}
          </div>
        );
      })}
    </>
  );
}
