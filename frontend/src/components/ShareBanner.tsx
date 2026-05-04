import { useEffect, useRef, useState } from "react";
import { useToast } from "../state/toast";

interface ShareBannerProps {
  shareUrl: string;
}

export function ShareBanner({ shareUrl }: ShareBannerProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [copied, setCopied] = useState(false);
  const { push } = useToast();

  useEffect(() => {
    if (!copied) return;
    const id = window.setTimeout(() => setCopied(false), 1800);
    return () => window.clearTimeout(id);
  }, [copied]);

  const onCopy = async () => {
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      push("success", "Share link copied");
    } catch {
      inputRef.current?.select();
      try {
        document.execCommand("copy");
        setCopied(true);
        push("success", "Share link copied");
      } catch {
        push("error", "Could not copy link — please copy manually.");
      }
    }
  };

  return (
    <div className="mt-3 flex flex-wrap items-center gap-2">
      <span className="muted">Read-only share link:</span>
      <input
        ref={inputRef}
        readOnly
        value={shareUrl}
        className="input min-w-[240px] flex-1 font-mono text-xs"
        onFocus={(e) => e.currentTarget.select()}
      />
      <button type="button" className="btn-secondary" onClick={onCopy}>
        {copied ? "Copied!" : "Copy share link"}
      </button>
    </div>
  );
}
