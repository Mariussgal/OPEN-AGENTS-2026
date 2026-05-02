"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  bootBanner,
  COMMAND_NAMES,
  COMMANDS,
  notFound,
  type ShellLine,
  type StreamApi,
} from "./commands";

export type ShellEntry = {
  /** Stable identifier for React keys. */
  id: string;
  /** Typed command (with prompt) — null for initial banner. */
  prompt: string | null;
  /** Output lines. */
  output: ShellLine[];
  /** If true, output should animate line-by-line. */
  typewriter?: boolean;
};

/** Active stream controller — allows external cancellation. */
type StreamController = {
  cancelled: boolean;
  /** Mutable buffer mirroring current entry output. */
  output: ShellLine[];
};

export type ShellApi = {
  entries: ShellEntry[];
  input: string;
  setInput: (value: string) => void;
  submit: (forceInput?: string) => void;
  /** History navigation: -1 = up, 1 = down. */
  navigateHistory: (delta: -1 | 1) => void;
  /** Tab autocomplete. */
  autocomplete: () => void;
  /** Full reset (used by `clear`). */
  reset: () => void;
  /** List of available commands (for UI autocomplete). */
  commandNames: string[];
};

const PROMPT = "guest@onchor:~$";

let nextId = 0;
const makeId = () => `e${++nextId}`;

function initialEntries(): ShellEntry[] {
  return [
    {
      id: makeId(),
      prompt: null,
      output: bootBanner(),
    },
  ];
}

/** Main shell hook. No UI logic, state only. */
export function useShell(): ShellApi {
  const [entries, setEntries] = useState<ShellEntry[]>(() => initialEntries());
  const [input, setInput] = useState("");

  // Typed command history (for ↑/↓).
  const historyRef = useRef<string[]>([]);
  const historyIndexRef = useRef<number>(-1);

  // Active streams (audit, etc.) — keyed by entry id for cancellation.
  const streamsRef = useRef<Map<string, StreamController>>(new Map());

  // Cancel all streams on unmount (navigation, hot reload, etc.).
  useEffect(() => {
    const streams = streamsRef.current;
    return () => {
      streams.forEach((ctrl) => {
        ctrl.cancelled = true;
      });
      streams.clear();
    };
  }, []);

  /**
   * Start async runner on `entryId`. Entry must already be mounted
   * with initial lines. Runner can append/replace through passed API.
   */
  const startStream = useCallback(
    (entryId: string, initialLines: ShellLine[], runner: (api: StreamApi) => Promise<void>) => {
      const ctrl: StreamController = {
        cancelled: false,
        output: [...initialLines],
      };
      streamsRef.current.set(entryId, ctrl);

      // Patch matching entry in state from mutable buffer.
      const flush = () => {
        if (ctrl.cancelled) return;
        const snapshot = [...ctrl.output];
        setEntries((prev) =>
          prev.map((e) => (e.id === entryId ? { ...e, output: snapshot } : e)),
        );
      };

      const api: StreamApi = {
        append: (line) => {
          if (ctrl.cancelled) return -1;
          const idx = ctrl.output.length;
          ctrl.output.push(line);
          flush();
          return idx;
        },
        replace: (idx, line) => {
          if (ctrl.cancelled) return;
          if (idx < 0 || idx >= ctrl.output.length) return;
          ctrl.output[idx] = line;
          flush();
        },
        sleep: (ms) =>
          new Promise<void>((resolve) => {
            // Poll cancel flag to end sleep early if user runs `clear`
            // during an ongoing audit.
            const tick = 50;
            let elapsed = 0;
            const handle = setInterval(() => {
              elapsed += tick;
              if (ctrl.cancelled || elapsed >= ms) {
                clearInterval(handle);
                resolve();
              }
            }, tick);
          }),
        cancelled: () => ctrl.cancelled,
      };

      // Fire and forget — do not block shell.
      void runner(api).finally(() => {
        streamsRef.current.delete(entryId);
      });
    },
    [],
  );

  /** Cancel all streams (used by `clear`). */
  const cancelAllStreams = useCallback(() => {
    streamsRef.current.forEach((ctrl) => {
      ctrl.cancelled = true;
    });
    streamsRef.current.clear();
  }, []);

  const submit = useCallback((forceInput?: string) => {
    const raw = (forceInput ?? input).trim();
    setInput("");
    historyIndexRef.current = -1;

    if (!raw) {
      // Enter on empty line -> append empty entry as feedback.
      setEntries((prev) => [
        ...prev,
        { id: makeId(), prompt: "", output: [] },
      ]);
      return;
    }

    historyRef.current = [...historyRef.current, raw];

    let cmdToParse = raw;
    if (cmdToParse.toLowerCase().startsWith("onchor-ai")) {
      cmdToParse = cmdToParse.replace(/^onchor-ai\s*/i, "").trim();
    }
    
    if (cmdToParse === "" && raw.toLowerCase() === "onchor-ai") {
      cmdToParse = "help";
    }

    const [cmdName, ...args] = cmdToParse.split(/\s+/);
    const handler = COMMANDS[cmdName.toLowerCase()];

    if (!handler) {
      setEntries((prev) => [
        ...prev,
        { id: makeId(), prompt: raw, output: notFound(cmdName) },
      ]);
      return;
    }

    const result = handler(args);

    // Side effects: navigation for special commands.
    if (cmdName === "history") {
      window.location.href = "/history";
    } else if (cmdName === "memory-page") {
      window.location.href = "/memory";
    } else if (cmdName === "github") {
      window.open("https://github.com/cnm-agency/Onchor-ai", "_blank");
    }

    if (result.clear) {
      cancelAllStreams();
      setEntries([]);
      return;
    }

    const entryId = makeId();
    setEntries((prev) => [
      ...prev,
      {
        id: entryId,
        prompt: raw,
        output: result.lines,
        typewriter: result.typewriter,
      },
    ]);

    // If command exposes async runner, start it now.
    if (result.run) {
      startStream(entryId, result.lines, result.run);
    }
  }, [input, startStream, cancelAllStreams]);

  const navigateHistory = useCallback((delta: -1 | 1) => {
    const history = historyRef.current;
    if (history.length === 0) return;

    const current = historyIndexRef.current;
    let next = current + (delta === -1 ? -1 : 1);

    // -1 = go up in history (e.g. 5 entries -> indices 4..0).
    if (current === -1 && delta === -1) next = history.length - 1;

    if (next < 0) next = 0;
    if (next >= history.length) {
      historyIndexRef.current = -1;
      setInput("");
      return;
    }

    historyIndexRef.current = next;
    setInput(history[next]);
  }, []);

  const autocomplete = useCallback(() => {
    const value = input.trim();
    if (!value) return;
    const matches = COMMAND_NAMES.filter((name) => name.startsWith(value));
    if (matches.length === 1) {
      setInput(matches[0] + " ");
      return;
    }
    if (matches.length > 1) {
      // Show completion candidates in output buffer like a real shell.
      setEntries((prev) => [
        ...prev,
        {
          id: makeId(),
          prompt: value,
          output: [
            { kind: "text", style: "muted", content: matches.join("  ") },
          ],
        },
      ]);
    }
  }, [input]);

  const reset = useCallback(() => {
    cancelAllStreams();
    setEntries(initialEntries());
    historyRef.current = [];
    historyIndexRef.current = -1;
    setInput("");
  }, [cancelAllStreams]);

  return useMemo(
    () => ({
      entries,
      input,
      setInput,
      submit,
      navigateHistory,
      autocomplete,
      reset,
      commandNames: COMMAND_NAMES,
    }),
    [entries, input, submit, navigateHistory, autocomplete, reset]
  );
}

export const SHELL_PROMPT = PROMPT;
