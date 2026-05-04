import { useEditor } from "../state/editor";

interface RunCardProps {
  isRunning: boolean;
  onRun: () => void;
}

export function RunCard({ isRunning, onRun }: RunCardProps) {
  const { state, dispatch } = useEditor();
  const { settings } = state;

  return (
    <article className="card">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="card-title">Run optimization</h2>
          <p className="muted">
            Manual grid input is used when present; otherwise CSV uploads are used. The
            optimizer picks the requested number of non-overlapping blocks.
          </p>
        </div>
        <span className="muted text-xs">
          Press <kbd className="rounded border border-slate-300 bg-slate-100 px-1.5 py-0.5 text-[0.65rem] font-mono dark:border-slate-700 dark:bg-slate-800">⌘/Ctrl + Enter</kbd> to run
        </span>
      </div>

      <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <div className="flex flex-col gap-1">
          <label className="input-label" htmlFor="slot-length">
            Block length (slots)
          </label>
          <input
            id="slot-length"
            className="input"
            type="number"
            min={1}
            max={48}
            value={settings.slotLengthSlots}
            onChange={(e) =>
              dispatch({
                type: "set_settings",
                patch: {
                  slotLengthSlots: Math.max(1, Math.min(48, Number(e.target.value) || 1)),
                },
              })
            }
          />
          <span className="muted text-xs">
            Each block is{" "}
            {settings.slotMinutes * settings.slotLengthSlots} minutes long.
          </span>
        </div>

        <div className="flex flex-col gap-1">
          <label className="input-label" htmlFor="num-blocks">
            Number of blocks
          </label>
          <input
            id="num-blocks"
            className="input"
            type="number"
            min={1}
            max={20}
            value={settings.numBlocks}
            onChange={(e) =>
              dispatch({
                type: "set_settings",
                patch: {
                  numBlocks: Math.max(1, Math.min(20, Number(e.target.value) || 1)),
                },
              })
            }
          />
        </div>

        <div className="flex flex-col gap-1">
          <label className="input-label opacity-0" aria-hidden="true">
            &nbsp;
          </label>
          <button
            type="button"
            className="btn-primary h-[42px] w-full"
            disabled={isRunning}
            onClick={onRun}
          >
            {isRunning ? (
              <>
                <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent" />
                Running…
              </>
            ) : (
              "Run Scheduler"
            )}
          </button>
        </div>
      </div>
    </article>
  );
}
