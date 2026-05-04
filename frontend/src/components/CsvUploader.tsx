import { useRef } from "react";
import type { EntityKind } from "../types";

interface CsvUploaderProps {
  kind: EntityKind;
  csvText: string;
  csvName: string;
  onChange: (text: string, name: string) => void;
  onClear: () => void;
}

export function CsvUploader({
  kind,
  csvText,
  csvName,
  onChange,
  onClear,
}: CsvUploaderProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);

  const handleFile = async (file: File | undefined | null) => {
    if (!file) return;
    const text = await file.text();
    onChange(text, file.name);
  };

  return (
    <div className="flex flex-col gap-3">
      <div>
        <label className="input-label" htmlFor={`${kind}-csv-input`}>
          {kind === "student" ? "Student" : "Teacher"} CSV file
        </label>
        <div className="mt-1 flex flex-wrap items-center gap-2">
          <button
            type="button"
            className="btn-secondary"
            onClick={() => inputRef.current?.click()}
          >
            Choose file…
          </button>
          <span className="muted truncate">{csvName || "No file selected"}</span>
          {csvText && (
            <button type="button" className="btn-ghost ml-auto" onClick={onClear}>
              Remove
            </button>
          )}
          <input
            ref={inputRef}
            id={`${kind}-csv-input`}
            type="file"
            accept=".csv,text/csv"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              void handleFile(f);
              e.currentTarget.value = "";
            }}
          />
        </div>
      </div>
      <ul className="space-y-1 pl-5 text-sm text-slate-500 dark:text-slate-400 list-disc">
        {kind === "student" ? (
          <>
            <li>
              Headers: <code className="text-xs">id,day,start_slot,end_slot</code> (legacy) or
              with optional <code className="text-xs">strength</code> column.
            </li>
            <li>
              Days use short names (<code className="text-xs">mon</code>,{" "}
              <code className="text-xs">tue</code>, …). Slots are integers in the configured
              granularity.
            </li>
            <li>
              Wide template (
              <code className="text-xs">student,Monday_start,Monday_end,...</code>) is also
              accepted.
            </li>
          </>
        ) : (
          <>
            <li>
              Single teacher: <code className="text-xs">day,start_slot,end_slot</code>.
            </li>
            <li>
              Multi-teacher:{" "}
              <code className="text-xs">teacher_id,day,start_slot,end_slot[,strength]</code>.
            </li>
          </>
        )}
      </ul>
      {csvText && (
        <details className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-3 text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-900/40 dark:text-slate-300">
          <summary className="cursor-pointer font-semibold">
            Preview ({csvText.split("\n").length} lines)
          </summary>
          <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap font-mono">
            {csvText}
          </pre>
        </details>
      )}
    </div>
  );
}
