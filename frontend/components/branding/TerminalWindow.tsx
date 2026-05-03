"use client";

import type { ReactNode } from "react";

type Props = {
  title?: string;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
  /** Show a pulsing dot next to title as a "live" signal. */
  live?: boolean;
};

/**
 * Terminal-style window: title bar + 3 left dots, dark body.
 * Consistent with the `onchor-ai` style (monochrome dots, no gradient).
 */
export function TerminalWindow({
  title = "onchor-ai",
  children,
  className = "",
  bodyClassName = "",
  live = false,
}: Props) {
  return (
    <div
      className={[
        "terminal-box rounded-md overflow-hidden shadow-[0_0_0_1px_rgba(124,92,255,0.05)] flex flex-col",
        className,
      ].join(" ")}
    >
      {/* Header — hauteur fixe */}
      <div className="flex-none flex items-center justify-between px-3 py-2 border-b border-[--terminal-border] bg-[--card]">
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-[--terminal-comment]" />
          <span className="w-2.5 h-2.5 rounded-full bg-[--terminal-comment]" />
          <span className="w-2.5 h-2.5 rounded-full bg-[--terminal-comment]" />
        </div>
        <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.2em] font-mono text-[--terminal-muted]">
          {live && (
            <span className="w-1.5 h-1.5 rounded-full bg-[--terminal-accent] animate-pulse-brand" />
          )}
          <span>{title}</span>
        </div>
        <div className="w-12" />
      </div>

      {/* Body — fills remaining space, min-h-0 is crucial for flex overflow */}
      <div className={["bg-[--terminal-bg] flex-1 min-h-0 p-4 sm:p-6", bodyClassName].join(" ")}>
        {children}
      </div>
    </div>
  );
}
