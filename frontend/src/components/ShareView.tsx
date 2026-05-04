import { useEffect, useState } from "react";
import { fetchSharedResult } from "../lib/api";
import type { OptimizeResult } from "../types";
import { ResultPanel } from "./ResultPanel";
import { UncoveredStudents } from "./UncoveredStudents";

interface ShareViewProps {
  token: string;
}

export function ShareView({ token }: ShareViewProps) {
  const [result, setResult] = useState<OptimizeResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setResult(null);
    setError(null);
    fetchSharedResult(token)
      .then((r) => {
        if (!cancelled) setResult(r);
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  if (error) {
    return (
      <div className="status-error">
        <strong>{error}</strong>
        <div className="mt-1 text-xs">
          The link may be malformed or truncated. <a className="underline" href="/">Open the scheduler</a>.
        </div>
      </div>
    );
  }

  if (!result) {
    return (
      <div className="card">
        <div className="muted">Loading shared schedule…</div>
      </div>
    );
  }

  const slotMinutes = (24 * 60) / (result.slots_per_day || 48);

  return (
    <div className="flex flex-col gap-5">
      <div className="status border-brand-200 bg-brand-50 text-brand-900 dark:border-brand-900/40 dark:bg-brand-950/30 dark:text-brand-100">
        You are viewing a read-only shared schedule.{" "}
        <a className="font-semibold underline" href="/">
          Open the scheduler
        </a>{" "}
        to make your own.
      </div>
      <ResultPanel result={result} shareUrl={null} />
      <UncoveredStudents result={result} slotMinutes={slotMinutes} />
    </div>
  );
}
