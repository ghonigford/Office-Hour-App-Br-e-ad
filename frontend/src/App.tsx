import { useCallback, useEffect, useMemo, useState } from "react";
import { EditorProvider, useEditor } from "./state/editor";
import { ToastProvider, useToast } from "./state/toast";
import { useTheme } from "./state/theme";
import { Header } from "./components/Header";
import { SettingsCard } from "./components/SettingsCard";
import { StudentEditor } from "./components/StudentEditor";
import { TeacherEditor } from "./components/TeacherEditor";
import { Heatmap } from "./components/Heatmap";
import { RunCard } from "./components/RunCard";
import { ResultPanel } from "./components/ResultPanel";
import { UncoveredStudents } from "./components/UncoveredStudents";
import { ShareView } from "./components/ShareView";
import { ToastViewport } from "./components/ToastViewport";
import { runOptimize } from "./lib/api";
import { compressMany } from "./lib/slots";
import type { OptimizeRequest, OptimizeResult } from "./types";

function getShareToken(): string | null {
  const path = window.location.pathname;
  const match = path.match(/^\/r\/([^/]+)\/?$/);
  return match ? decodeURIComponent(match[1]) : null;
}

export default function App() {
  const { theme, toggle } = useTheme();
  const shareToken = getShareToken();

  return (
    <ToastProvider>
      <div className="mx-auto flex min-h-screen max-w-6xl flex-col gap-5 px-4 py-6 sm:px-6 sm:py-8">
        <Header theme={theme} onToggleTheme={toggle} shareView={shareToken !== null} />
        {shareToken ? (
          <ShareView token={shareToken} />
        ) : (
          <EditorProvider>
            <Workspace />
          </EditorProvider>
        )}
        <Footer />
      </div>
      <ToastViewport />
    </ToastProvider>
  );
}

function Workspace() {
  const { state } = useEditor();
  const { push } = useToast();
  const [result, setResult] = useState<OptimizeResult | null>(null);
  const [shareUrl, setShareUrl] = useState<string | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runScheduler = useCallback(async () => {
    setIsRunning(true);
    setError(null);
    try {
      const studentRows = compressMany(state.students, state.settings);
      const teacherRows = compressMany(
        state.teachers.slice(0, state.settings.numTeachers),
        state.settings,
      );

      const usingStudentCsv = state.studentInputMode === "csv" && state.studentCsvText.trim();
      const usingTeacherCsv = state.teacherInputMode === "csv" && state.teacherCsvText.trim();

      const payload: OptimizeRequest = {
        settings: {
          slot_minutes: state.settings.slotMinutes,
          day_start_hour: state.settings.dayStartHour,
          day_end_hour: state.settings.dayEndHour,
          num_teachers: state.settings.numTeachers,
          slot_length_slots: state.settings.slotLengthSlots,
          num_blocks: state.settings.numBlocks,
        },
        students: usingStudentCsv
          ? { csv_text: state.studentCsvText }
          : { rows_v2: studentRows },
        teachers: usingTeacherCsv
          ? { csv_text: state.teacherCsvText }
          : { rows_v2: teacherRows },
      };

      const response = await runOptimize(payload);
      setResult(response.result);
      const url = new URL(`/r/${response.share_token}`, window.location.origin).toString();
      setShareUrl(url);
      push("success", "Schedule optimized");
      window.requestAnimationFrame(() => {
        document.getElementById("result-anchor")?.scrollIntoView({ behavior: "smooth" });
      });
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Unexpected error";
      setError(msg);
      push("error", msg);
    } finally {
      setIsRunning(false);
    }
  }, [state, push]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
        e.preventDefault();
        if (!isRunning) runScheduler();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isRunning, runScheduler]);

  const slotMinutes = useMemo(() => {
    if (!result) return state.settings.slotMinutes;
    return (24 * 60) / (result.slots_per_day || 48);
  }, [result, state.settings.slotMinutes]);

  return (
    <>
      {error && <div className="status-error">{error}</div>}
      {result && (
        <div id="result-anchor" className="flex flex-col gap-5">
          <ResultPanel result={result} shareUrl={shareUrl} />
          <UncoveredStudents result={result} slotMinutes={slotMinutes} />
        </div>
      )}
      <SettingsCard />
      <div className="grid gap-5 lg:grid-cols-2">
        <StudentEditor />
        <TeacherEditor />
      </div>
      <RunCard isRunning={isRunning} onRun={runScheduler} />
      <Heatmap />
    </>
  );
}

function Footer() {
  return (
    <footer className="muted text-center text-xs">
      Office Hours Scheduler · pymoo + Flask + React. Press{" "}
      <kbd className="rounded border border-slate-300 bg-slate-100 px-1.5 py-0.5 font-mono dark:border-slate-700 dark:bg-slate-800">
        ⌘/Ctrl + Enter
      </kbd>{" "}
      to run.
    </footer>
  );
}
