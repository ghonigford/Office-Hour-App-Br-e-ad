import type { Day, EntityState, Settings, SlotMinutes, Strength, V2Row } from "../types";
import { DAYS } from "../types";

export const slotsPerDay = (slotMinutes: SlotMinutes) => (24 * 60) / slotMinutes;

export const startSlotForSettings = (s: Settings) =>
  Math.floor((s.dayStartHour * 60) / s.slotMinutes);

export const endSlotForSettings = (s: Settings) =>
  Math.ceil((s.dayEndHour * 60) / s.slotMinutes);

export function slotToLabel(slot: number, slotMinutes: number): string {
  const total = slot * slotMinutes;
  const h24 = Math.floor(total / 60) % 24;
  const minute = total % 60;
  const suffix = h24 >= 12 ? "PM" : "AM";
  let h12 = h24 % 12;
  if (h12 === 0) h12 = 12;
  const mm = minute === 0 ? "00" : minute < 10 ? "0" + minute : String(minute);
  return `${h12}:${mm} ${suffix}`;
}

export function cellKey(day: Day, slot: number): string {
  return `${day}:${slot}`;
}

export function weightForCell(entity: EntityState, day: Day, slot: number): number {
  const cellState = entity.cells[cellKey(day, slot)] ?? null;
  if (entity.mode === "available") {
    if (cellState === "hard") return 1.0;
    if (cellState === "soft") return 0.5;
    return 0.0;
  }
  if (cellState === "hard") return 0.0;
  if (cellState === "soft") return 0.5;
  return 1.0;
}

/**
 * Compress an entity's cells into V2 rows: contiguous runs per day with
 * matching strength become a single row. Mirrors the legacy template logic.
 */
export function compressEntityRows(
  entity: EntityState,
  settings: Settings,
): V2Row[] {
  const out: V2Row[] = [];
  const startS = startSlotForSettings(settings);
  const endS = endSlotForSettings(settings);
  for (const day of DAYS) {
    const points: Array<[number, Strength]> = [];
    for (let s = startS; s < endS; s += 1) {
      const cellState = entity.cells[cellKey(day, s)] ?? null;
      let strength: Strength | null = null;
      if (entity.mode === "available") {
        if (cellState === "hard" || cellState === "soft") strength = cellState;
      } else {
        if (cellState === "hard") strength = null;
        else if (cellState === "soft") strength = "soft";
        else strength = "hard";
      }
      if (strength) points.push([s, strength]);
    }
    if (points.length === 0) continue;
    let runStart = points[0][0];
    let runStrength = points[0][1];
    let prev = points[0][0];
    for (let i = 1; i < points.length; i += 1) {
      const [s, str] = points[i];
      if (s === prev + 1 && str === runStrength) {
        prev = s;
        continue;
      }
      out.push([entity.id, day, runStart, prev + 1, runStrength]);
      runStart = s;
      runStrength = str;
      prev = s;
    }
    out.push([entity.id, day, runStart, prev + 1, runStrength]);
  }
  return out;
}

export function compressMany(entities: EntityState[], settings: Settings): V2Row[] {
  return entities.flatMap((e) => compressEntityRows(e, settings));
}

/** Drop cells that no longer fit when the slot granularity changes. */
export function migrateCellsToGranularity(
  cells: Record<string, Strength>,
  newSlotMinutes: SlotMinutes,
): Record<string, Strength> {
  const limit = slotsPerDay(newSlotMinutes);
  const out: Record<string, Strength> = {};
  for (const [key, value] of Object.entries(cells)) {
    const [, slotStr] = key.split(":");
    const slot = parseInt(slotStr, 10);
    if (slot < limit) out[key] = value;
  }
  return out;
}
