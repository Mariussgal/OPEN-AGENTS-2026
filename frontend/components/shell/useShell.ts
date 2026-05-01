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
  /** Identifiant stable pour les keys React. */
  id: string;
  /** Commande tapée (avec le prompt) — null pour le banner initial. */
  prompt: string | null;
  /** Lignes de sortie. */
  output: ShellLine[];
  /** Si true, l'output doit s'afficher caractère par caractère / ligne par ligne. */
  typewriter?: boolean;
};

/** Contrôleur d'un stream actif — permet l'annulation depuis l'extérieur. */
type StreamController = {
  cancelled: boolean;
  /** Buffer mutable qui reflète l'output courant de l'entrée. */
  output: ShellLine[];
};

export type ShellApi = {
  entries: ShellEntry[];
  input: string;
  setInput: (value: string) => void;
  submit: () => void;
  /** Navigation historique : -1 = remonte, 1 = descend. */
  navigateHistory: (delta: -1 | 1) => void;
  /** Auto-complétion sur Tab. */
  autocomplete: () => void;
  /** Reset complet (utilisé par la commande `clear`). */
  reset: () => void;
  /** Liste des commandes disponibles (pour autocomplete UI). */
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

/**
 * Hook principal du shell. Ne touche pas à l'UI — pure logique d'état.
 */
export function useShell(): ShellApi {
  const [entries, setEntries] = useState<ShellEntry[]>(() => initialEntries());
  const [input, setInput] = useState("");

  // Historique des commandes tapées (pour ↑/↓).
  const historyRef = useRef<string[]>([]);
  const historyIndexRef = useRef<number>(-1);

  // Streams actifs (audit, etc.) — keyed by entry id pour cancellation.
  const streamsRef = useRef<Map<string, StreamController>>(new Map());

  // Annule tous les streams au démontage (navigation, hot reload, etc.).
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
   * Lance un runner async sur l'entrée `entryId`. L'entrée doit déjà avoir
   * été montée avec ses lignes initiales. Le runner peut ensuite append /
   * replace via l'API qu'on lui passe.
   */
  const startStream = useCallback(
    (entryId: string, initialLines: ShellLine[], runner: (api: StreamApi) => Promise<void>) => {
      const ctrl: StreamController = {
        cancelled: false,
        output: [...initialLines],
      };
      streamsRef.current.set(entryId, ctrl);

      // Patch l'entrée correspondante dans le state à partir du buffer mutable.
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
            // On poll la flag d'annulation pour libérer le sleep tôt si
            // l'utilisateur fait `clear` pendant un audit en cours.
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

      // Fire and forget — on ne bloque pas le shell.
      void runner(api).finally(() => {
        streamsRef.current.delete(entryId);
      });
    },
    [],
  );

  /** Annule tous les streams (utilisé par `clear`). */
  const cancelAllStreams = useCallback(() => {
    streamsRef.current.forEach((ctrl) => {
      ctrl.cancelled = true;
    });
    streamsRef.current.clear();
  }, []);

  const submit = useCallback(() => {
    const raw = input.trim();
    setInput("");
    historyIndexRef.current = -1;

    if (!raw) {
      // Enter sur ligne vide → ajoute une ligne vide pour donner du feedback.
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

    // Side effects : navigation pour quelques commandes spéciales.
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

    // Si la commande expose un runner async, on le démarre maintenant.
    if (result.run) {
      startStream(entryId, result.lines, result.run);
    }
  }, [input, startStream, cancelAllStreams]);

  const navigateHistory = useCallback((delta: -1 | 1) => {
    const history = historyRef.current;
    if (history.length === 0) return;

    const current = historyIndexRef.current;
    let next = current + (delta === -1 ? -1 : 1);

    // -1 = remonter dans le passé (ex : 5 entrées → indices 4..0).
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
      // Affiche les candidats dans le buffer comme le ferait un vrai shell.
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
