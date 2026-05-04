import { useState } from "react";
import { Modal } from "./Modal";
import type { Theme } from "../state/theme";

interface HeaderProps {
  theme: Theme;
  onToggleTheme: () => void;
  shareView?: boolean;
}

export function Header({ theme, onToggleTheme, shareView }: HeaderProps) {
  const [showInfo, setShowInfo] = useState(false);

  return (
    <header className="card flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-start gap-3">
        <div className="hidden h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-brand-600 text-white shadow-md dark:bg-brand-500 dark:text-slate-950 sm:flex">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="h-6 w-6"
          >
            <rect x="3" y="5" width="18" height="16" rx="3" />
            <path d="M3 11h18M8 3v4M16 3v4" />
            <circle cx="12" cy="15" r="2.5" fill="currentColor" stroke="none" />
          </svg>
        </div>
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight sm:text-3xl">
            Office Hours Scheduler
          </h1>
          <p className="muted mt-1 max-w-2xl">
            {shareView
              ? "You're viewing a read-only shared schedule."
              : "Pick the office-hour blocks that maximize how many students can attend. Mark availability, set granularity and day window, optionally split across multiple teachers, and the optimizer chooses the best non-overlapping blocks."}
          </p>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          className="btn-secondary"
          onClick={() => setShowInfo(true)}
          title="Show input format help"
        >
          <span aria-hidden="true">ℹ</span>
          <span>Help</span>
        </button>
        <button
          type="button"
          className="btn-ghost"
          onClick={onToggleTheme}
          aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
          title={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
        >
          {theme === "dark" ? (
            <>
              <SunIcon /> <span className="hidden sm:inline">Light</span>
            </>
          ) : (
            <>
              <MoonIcon /> <span className="hidden sm:inline">Dark</span>
            </>
          )}
        </button>
      </div>

      <Modal
        open={showInfo}
        onClose={() => setShowInfo(false)}
        title="Input format help"
        widthClass="max-w-xl"
      >
        <div className="grid gap-3 text-sm text-slate-700 dark:text-slate-300">
          <div>
            <div className="font-semibold text-slate-900 dark:text-slate-100">
              Student CSV (legacy)
            </div>
            <code className="mt-1 inline-block rounded bg-slate-100 px-2 py-1 text-xs dark:bg-slate-800">
              id,day,start_slot,end_slot
            </code>
          </div>
          <div>
            <div className="font-semibold text-slate-900 dark:text-slate-100">
              Student CSV (with strength)
            </div>
            <code className="mt-1 inline-block rounded bg-slate-100 px-2 py-1 text-xs dark:bg-slate-800">
              id,day,start_slot,end_slot,strength
            </code>{" "}
            where <code className="text-xs">strength</code> is{" "}
            <code className="text-xs">hard</code> or <code className="text-xs">soft</code>.
          </div>
          <div>
            <div className="font-semibold text-slate-900 dark:text-slate-100">
              Teacher CSV (multi-teacher)
            </div>
            <code className="mt-1 inline-block rounded bg-slate-100 px-2 py-1 text-xs dark:bg-slate-800">
              teacher_id,day,start_slot,end_slot[,strength]
            </code>
          </div>
          <div>
            <div className="font-semibold text-slate-900 dark:text-slate-100">
              Hard vs Soft
            </div>
            Hard slots count fully (1.0); soft slots count half (0.5). The optimizer maximizes
            total weighted unique coverage.
          </div>
          <div>
            <div className="font-semibold text-slate-900 dark:text-slate-100">
              Mark unavailable mode
            </div>
            Instead of marking when you ARE free, mark when you are NOT free. Hard-busy =
            definitely busy, soft-busy = busy but movable; everything else inside the day
            window is treated as free.
          </div>
        </div>
      </Modal>
    </header>
  );
}

function SunIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      className="h-4 w-4"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      className="h-4 w-4"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
    </svg>
  );
}
