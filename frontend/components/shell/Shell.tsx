"use client";

import { useEffect, useRef } from "react";
import { useShell, SHELL_PROMPT, type ShellEntry } from "./useShell";
import type { LineStyle, ProgressLine, ShellLine } from "./commands";

const STYLE_CLASSES: Record<LineStyle, string> = {
  log: "text-[--terminal-label]",
  muted: "text-[--terminal-muted]",
  comment: "text-[--terminal-comment]",
  brand: "text-[--terminal-brand]",
  accent: "text-[--terminal-accent]",
  warn: "text-[--terminal-yellow]",
  danger: "text-[--terminal-red]",
  label: "text-[--terminal-label] font-semibold",
  rule: "text-[--terminal-border]",
};

const PROGRESS_BAR_WIDTH = 28;

function ProgressView({ line }: { line: ProgressLine }) {
  const value = Math.max(0, Math.min(100, line.value));
  const filled = Math.round((value / 100) * PROGRESS_BAR_WIDTH);
  const empty = PROGRESS_BAR_WIDTH - filled;
  const pct = `${value.toString().padStart(3, " ")}%`;

  const fillColor =
    line.status === "done"
      ? "text-[--terminal-accent]"
      : line.status === "fail"
      ? "text-[--terminal-red]"
      : "text-[--terminal-brand]";
  const pctColor =
    line.status === "done"
      ? "text-[--terminal-accent] glow-accent"
      : line.status === "fail"
      ? "text-[--terminal-red]"
      : "text-[--terminal-brand]";

  return (
    <div className="whitespace-pre font-mono">
      <span className="text-[--terminal-label]">{line.label.padEnd(14, " ")}</span>
      <span className="text-[--terminal-comment]">[</span>
      <span className={fillColor}>{"█".repeat(filled)}</span>
      <span className="text-[--terminal-comment]">{"░".repeat(empty)}</span>
      <span className="text-[--terminal-comment]">]</span>
      {"  "}
      <span className={pctColor}>{pct}</span>
      {line.sublabel && (
        <>
          {"   "}
          <span className="text-[--terminal-muted]">· {line.sublabel}</span>
        </>
      )}
      {line.status === "running" && (
        <span className="text-[--terminal-brand] animate-blink ml-2">▍</span>
      )}
    </div>
  );
}

function LineView({ line }: { line: ShellLine }) {
  if (line.kind === "banner") {
    return (
      <pre className="text-[--terminal-brand] glow-brand whitespace-pre leading-tight text-[10px] sm:text-xs md:text-sm">
        {line.content}
      </pre>
    );
  }
  if (line.kind === "raw") {
    return <pre className="whitespace-pre">{line.content}</pre>;
  }
  if (line.kind === "progress") {
    return <ProgressView line={line} />;
  }
  return (
    <pre className={`whitespace-pre ${STYLE_CLASSES[line.style]}`}>
      {line.content || "\u00A0"}
    </pre>
  );
}

function EntryView({ entry }: { entry: ShellEntry }) {
  // Pour les entrées streamées (typewriter), chaque nouvelle ligne fade-in
  // au montage. Les remontages dus à `replace()` ne re-déclenchent pas
  // l'animation car les keys sont stables (index dans output).
  const lineWrapper = entry.typewriter ? "animate-fade-in-up" : "";

  return (
    <div className="space-y-0.5">
      {entry.prompt !== null && (
        <div className="flex items-baseline gap-2">
          <span className="text-[--terminal-accent] shrink-0">{SHELL_PROMPT}</span>
          <span className="text-[--terminal-label] break-all">{entry.prompt}</span>
        </div>
      )}
      {entry.output.length > 0 && (
        <div>
          {entry.output.map((line, i) => (
            <div key={i} className={lineWrapper}>
              <LineView line={line} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function Shell() {
  const { entries, input, setInput, submit, navigateHistory, autocomplete } = useShell();
  const inputRef = useRef<HTMLInputElement>(null);
  const scrollerRef = useRef<HTMLDivElement>(null);

  // Garde le focus sur l'input dès que le composant se monte / on clique dans le shell.
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Autoscroll en bas à chaque nouvel entry.
  useEffect(() => {
    const el = scrollerRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [entries]);

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      e.preventDefault();
      submit();
      return;
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      navigateHistory(-1);
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      navigateHistory(1);
      return;
    }
    if (e.key === "Tab") {
      e.preventDefault();
      autocomplete();
      return;
    }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "l") {
      e.preventDefault();
      // Ctrl+L / Cmd+L : émule `clear`
      setInput("");
      // Ré-injection en passant par submit avec "clear"
      setTimeout(() => {
        setInput("clear");
        setTimeout(() => submit(), 0);
      }, 0);
    }
  }

  return (
    <div
      className="flex flex-col h-full w-full bg-[--terminal-bg] text-[--terminal-label] font-mono text-sm"
      onClick={() => inputRef.current?.focus()}
    >
      {/* Output buffer — min-h-0 requis pour que flex-1 + overflow-y-auto fonctionne */}
      <div
        ref={scrollerRef}
        className="flex-1 min-h-0 overflow-y-auto px-4 sm:px-6 py-4 space-y-3 leading-relaxed"
        onWheel={(e) => e.stopPropagation()}
      >
        {entries.map((entry) => (
          <EntryView key={entry.id} entry={entry} />
        ))}
      </div>

      {/* Prompt input */}
      <div className="flex items-baseline gap-2 px-4 sm:px-6 py-3 border-t border-[--terminal-border]">
        <span className="text-[--terminal-accent] shrink-0 select-none">{SHELL_PROMPT}</span>
        <div className="relative flex-1">
          <input
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            className="w-full bg-transparent outline-none text-[--terminal-label] caret-[--terminal-accent] font-mono"
            spellCheck={false}
            autoCapitalize="none"
            autoCorrect="off"
            aria-label="onchor-ai shell input"
            placeholder="type `help` and press enter"
          />
        </div>
      </div>
    </div>
  );
}
