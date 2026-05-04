import { useEffect, type ReactNode } from "react";

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  footer?: ReactNode;
  widthClass?: string;
}

export function Modal({
  open,
  onClose,
  title,
  children,
  footer,
  widthClass = "max-w-3xl",
}: ModalProps) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 p-4 backdrop-blur-sm"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className={`w-full ${widthClass} max-h-[90vh] overflow-auto rounded-2xl border border-slate-200 bg-white p-5 shadow-card animate-scale-in dark:border-slate-800 dark:bg-slate-950 dark:shadow-cardDark`}
      >
        <div className="mb-3 flex items-start justify-between gap-3">
          <h2 className="card-title">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            className="btn-ghost h-8 w-8 rounded-full p-0 text-lg"
            aria-label="Close"
          >
            ×
          </button>
        </div>
        <div>{children}</div>
        {footer ? (
          <div className="mt-4 flex flex-wrap items-center justify-end gap-2">{footer}</div>
        ) : null}
      </div>
    </div>
  );
}
