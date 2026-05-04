import { useState } from "react";
import type { OptimizeResult } from "../types";
import { DAY_LABELS } from "../types";
import { slotToLabel } from "../lib/slots";
import { Modal } from "./Modal";
import { ResultCalendar } from "./ResultCalendar";
import { ShareBanner } from "./ShareBanner";

interface ResultPanelProps {
  result: OptimizeResult;
  shareUrl: string | null;
}

export function ResultPanel({ result, shareUrl }: ResultPanelProps) {
  const [showCalendar, setShowCalendar] = useState(false);
  const slotMinutes = (24 * 60) / (result.slots_per_day || 48);
  const blockMinutes = slotMinutes * result.slot_length_slots;
  const coveragePct = (result.coverage_ratio * 100).toFixed(1);
  const weightedPct = ((result.weighted_coverage_ratio ?? 0) * 100).toFixed(1);
  const hardPct = ((result.hard_coverage_ratio ?? 0) * 100).toFixed(1);

  return (
    <article className="status-ok flex flex-col gap-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat
          label="Blocks selected"
          value={`${result.num_blocks_selected} / ${result.num_blocks_requested}`}
          sub={`${blockMinutes}-min ${result.num_blocks_selected === 1 ? "block" : "blocks"}`}
        />
        <Stat
          label="Students reached"
          value={`${result.students_covered} / ${result.total_students}`}
          sub={`${coveragePct}% coverage`}
        />
        {result.weighted_coverage !== undefined && (
          <Stat
            label="Weighted coverage"
            value={result.weighted_coverage.toFixed(1)}
            sub={`${weightedPct}% of total`}
          />
        )}
        {result.students_covered_hard !== undefined && (
          <Stat
            label="Hard-only coverage"
            value={`${result.students_covered_hard} / ${result.total_students}`}
            sub={`${hardPct}%`}
          />
        )}
      </div>

      <ul className="grid gap-2">
        {result.blocks.map((block, i) => (
          <li
            key={i}
            className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-emerald-200 bg-white px-4 py-3 text-sm text-emerald-900 dark:border-emerald-900/40 dark:bg-slate-950 dark:text-emerald-100"
          >
            <span className="flex flex-wrap items-center gap-2">
              <strong>{DAY_LABELS[block.slot_day]}</strong>
              <span className="text-emerald-700 dark:text-emerald-300">·</span>
              <span>
                {slotToLabel(block.start_slot_in_day, slotMinutes)} –{" "}
                {slotToLabel(block.end_slot_in_day, slotMinutes)}
              </span>
              {block.host && (
                <span className="ml-1 inline-flex items-center rounded-full bg-brand-100 px-2 py-0.5 text-xs font-bold text-brand-700 dark:bg-brand-900/40 dark:text-brand-200">
                  {block.host}
                </span>
              )}
            </span>
            <span className="font-semibold text-emerald-700 dark:text-emerald-300">
              {block.students_covered_in_block}/{result.total_students} students
              {block.students_covered_hard !== undefined &&
                block.students_covered_soft !== undefined && (
                  <span className="ml-1 font-normal text-emerald-600 dark:text-emerald-400">
                    ({block.students_covered_hard} hard, {block.students_covered_soft} soft)
                  </span>
                )}
            </span>
          </li>
        ))}
      </ul>

      <div className="flex flex-wrap items-center gap-2">
        <button type="button" className="btn-primary" onClick={() => setShowCalendar(true)}>
          View result calendar
        </button>
      </div>

      {shareUrl && <ShareBanner shareUrl={shareUrl} />}

      <Modal
        open={showCalendar}
        onClose={() => setShowCalendar(false)}
        title="Optimal time slots (calendar view)"
        widthClass="max-w-5xl"
      >
        <p className="muted mb-3">
          Highlighted cells show the recommended office-hour windows. Each block shows its
          host (when more than one teacher is configured).
        </p>
        <ResultCalendar blocks={result.blocks} slotMinutes={slotMinutes} />
      </Modal>
    </article>
  );
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-xl bg-white px-4 py-3 text-emerald-900 shadow-sm dark:bg-slate-950 dark:text-emerald-100">
      <div className="text-xs font-semibold uppercase tracking-wide text-emerald-700 dark:text-emerald-300">
        {label}
      </div>
      <div className="mt-1 text-xl font-bold">{value}</div>
      {sub && (
        <div className="mt-0.5 text-xs text-emerald-600 dark:text-emerald-400">{sub}</div>
      )}
    </div>
  );
}
