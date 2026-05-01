/**
 * Registry des commandes du shell Onchor.ai (frontend).
 *
 * Chaque commande retourne un tableau de "ShellLine". Une ligne peut être
 * du texte coloré (style sémantique) ou un payload spécial (banner, table).
 *
 * Le ton est volontairement sec et pro security — pas de fioritures,
 * pas d'emoji, output factuel comme nmap/metasploit/burp.
 */

import { ASCII_LOGO } from "@/components/branding/AsciiLogo";

export type LineStyle =
  | "log"       // texte par défaut
  | "muted"     // commentaire / dim
  | "comment"   // # ...
  | "brand"     // violet brand
  | "accent"    // teal succès
  | "warn"      // jaune
  | "danger"    // rouge / HIGH
  | "label"     // gris clair label
  | "rule";     // séparateur

export type ProgressLine = {
  kind: "progress";
  /** Valeur de progression entre 0 et 100. */
  value: number;
  /** Label à gauche de la barre (ex: "audit progress"). */
  label: string;
  /** Hint à droite de la barre (ex: "phase 3/6 · triage"). */
  sublabel?: string;
  /** running = brand · done = accent · fail = red. */
  status?: "running" | "done" | "fail";
};

export type ShellLine =
  | { kind: "text"; style: LineStyle; content: string }
  | { kind: "banner"; content: string }     // logo ASCII préformaté
  | { kind: "raw"; content: string }        // texte brut sans style spécifique
  | ProgressLine;                            // barre de progression dynamique

/**
 * API exposée aux runners async (commandes streaming type `audit`).
 * Permet d'ajouter / remplacer des lignes dans l'entrée courante au fil
 * du temps, et d'attendre proprement entre deux étapes.
 */
export type StreamApi = {
  /** Ajoute une ligne et renvoie son index dans l'output. */
  append: (line: ShellLine) => number;
  /** Remplace la ligne à l'index donné (utilisé pour la barre de progression). */
  replace: (index: number, line: ShellLine) => void;
  /** Pause le runner. */
  sleep: (ms: number) => Promise<void>;
  /** True si l'utilisateur a `clear` ou rechargé : le runner doit s'arrêter. */
  cancelled: () => boolean;
};

export type CommandResult = {
  lines: ShellLine[];
  /** Si true, le shell efface tout le buffer avant d'afficher (clear). */
  clear?: boolean;
  /** Si true, applique une fade-in douce à chaque ligne ajoutée. */
  typewriter?: boolean;
  /**
   * Runner asynchrone optionnel. S'il est défini, il est appelé après que
   * l'entrée a été montée avec `lines`, et peut streamer du contenu
   * supplémentaire dans cette même entrée (logs, progress bar, etc.).
   */
  run?: (api: StreamApi) => Promise<void>;
};

export type CommandHandler = (args: string[]) => CommandResult;

const t = (style: LineStyle, content: string): ShellLine => ({
  kind: "text",
  style,
  content,
});
const blank = (): ShellLine => ({ kind: "text", style: "log", content: "" });
const rule = (): ShellLine => ({
  kind: "text",
  style: "rule",
  content: "─".repeat(60),
});

// ─── Commands ────────────────────────────────────────────────────────────────

const help: CommandHandler = () => ({
  lines: [
    t("log", " Usage: onchor-ai [OPTIONS] COMMAND [ARGS]..."),
    blank(),
    t("muted", " Onchor.ai — Solidity Security Copilot avec mémoire collective."),
    t("muted", " Audit contracts, paiements USDC testnet (x402), ancrages KeeperHub, patterns"),
    t("muted", " 0G. Détail et options propres à chaque commande : utilise -h après le nom de"),
    t("muted", " la commande."),
    blank(),
    t("label", "╭─ Commandes disponibles ──────────────────────────────────────────────────────╮"),
    t("log", "│ audit     Auditer fichier, dossier ou adresse 0x (contrat vérifié).          │"),
    t("log", "│ doctor    Vérifier clés & connexions réseau (~/.onchor-ai ou .env).          │"),
    t("log", "│ init      Initialiser le dossier projet .onchor/ (config locale).            │"),
    t("log", "│ status    Afficher mode, version, solde USDC côté serveur local.             │"),
    t("label", "╰──────────────────────────────────────────────────────────────────────────────╯"),
    blank(),
    t("label", "╭─ Navigation Web (Demo CLI) ──────────────────────────────────────────────────╮"),
    t("log", "│ memory    Voir les statistiques de la mémoire collective 0G.                 │"),
    t("log", "│ history   Ouvrir la page d'historique des audits.                            │"),
    t("log", "│ pipeline  Voir l'architecture en 6 phases du pipeline.                       │"),
    t("log", "│ pricing   Voir les tarifs x402.                                              │"),
    t("log", "│ stack     Voir la stack technologique.                                       │"),
    t("log", "│ clear     Effacer l'écran.                                                   │"),
    t("label", "╰──────────────────────────────────────────────────────────────────────────────╯"),
    blank(),
    t("comment", "# tip: ↑/↓ to navigate history · Tab to autocomplete"),
  ],
});

const version: CommandHandler = () => ({
  lines: [
    t("brand", "onchor-ai 0.1.0"),
    t("muted", "Solidity Security Copilot — persistent collective memory"),
    blank(),
    t("label", "build"),
    t("log", "  release    : 0.1.0-rc1"),
    t("log", "  commit     : 6bd2b87"),
    t("log", "  network    : base-sepolia (chain 84532)"),
    t("log", "  llm        : claude-sonnet-4-5 / gpt-4o-mini"),
    blank(),
    t("comment", "# CNM Agency — ETHGlobal Open Agents 2026"),
  ],
});

const status: CommandHandler = () => ({
  lines: [
    t("label", "session"),
    t("log", "  user           : guest"),
    t("log", "  mode           : --local (demo)"),
    t("log", "  network        : base-sepolia"),
    t("log", "  wallet         : 0x0000…0000 (not configured)"),
    t("log", "  balance        : 0.00 USDC"),
    blank(),
    t("comment", "# run `init` to generate a local wallet"),
  ],
});

const doctor: CommandHandler = () => ({
  lines: [
    t("label", "Onchor.ai Doctor - System Check"),
    blank(),
    t("accent", "✓ Python Environment: Python 3.12+ detected"),
    t("accent", "✓ Dependencies: Installed correctly"),
    t("warn", "⚠ ANTHROPIC_API_KEY: Not configured in demo mode"),
    t("warn", "⚠ OPENAI_API_KEY: Not configured in demo mode"),
    t("warn", "⚠ Web3 Wallet: No local key found (~/.onchor-ai/config.json)"),
    blank(),
    t("comment", "# Run this locally via `pip install onchor-ai` to configure your agent."),
  ],
});

const init: CommandHandler = () => ({
  lines: [
    t("muted", "[init] generating local wallet..."),
    t("muted", "[init] encrypting keystore (AES-256-GCM)..."),
    t("muted", "[init] writing ~/.onchor/config.json..."),
    t("muted", "[init] writing ~/.onchor-ai/memory/..."),
    blank(),
    t("accent", "✓ wallet generated"),
    t("log", "  address    : 0x4DB6Bf931e0AC52E6a35601da70aAB3fF26657C4"),
    t("log", "  network    : base-sepolia"),
    t("log", "  wallet     : ~/.onchor/"),
    t("log", "  memory     : ~/.onchor-ai/memory"),
    blank(),
    t("warn", "next: fund your wallet with USDC to run paid audits"),
    t("comment", "# faucet: https://faucet.circle.com (Base Sepolia)"),
  ],
});

const memory: CommandHandler = () => ({
  lines: [
    t("label", "collective memory — stats"),
    blank(),
    t("log", "  total patterns      : 1,847"),
    t("log", "  high severity       :   612"),
    t("log", "  medium severity     :   738"),
    t("log", "  low severity        :   497"),
    blank(),
    t("label", "sources (bootstrap)"),
    t("log", "  rekt.news           :  ~500 patterns"),
    t("log", "  immunefi disclosure :  ~300 patterns"),
    t("log", "  audit reports (oz)  : ~1000 patterns"),
    blank(),
    t("label", "anonymization"),
    t("comment", "# never stored: contract_address, project_name, raw_code"),
    t("comment", "# stored:       normalized_snippet, abstract_description, fix_pattern"),
    blank(),
    t("accent", "storage:  0G Storage KV (testnet Galileo)"),
    t("accent", "anchor:   AnchorRegistry.sol (Sepolia 0x4DC065…d775F8)"),
  ],
});

const pricing: CommandHandler = () => ({
  lines: [
    t("label", "x402 pricing — pay-per-audit (USDC, base-sepolia)"),
    blank(),
    t("rule", "┌──────────────┬─────────┬────────────────────────┐"),
    t("rule", "│ scope        │  price  │ example                │"),
    t("rule", "├──────────────┼─────────┼────────────────────────┤"),
    t("log",  "│ ≤  3 files   │  $0.50  │ simple ERC20           │"),
    t("log",  "│ ≤ 10 files   │  $1.00  │ vault + router         │"),
    t("log",  "│ ≤ 30 files   │  $2.00  │ full DeFi protocol     │"),
    t("log",  "│ >  30 files  │  $4.00  │ uniswap v4 scale       │"),
    t("rule", "└──────────────┴─────────┴────────────────────────┘"),
    blank(),
    t("comment", "# free tier: `audit --local` (no anchoring, local memory only)"),
    t("comment", "# contribute patterns to earn -0.25 USDC per validated entry"),
  ],
});

const pipeline: CommandHandler = () => ({
  lines: [
    t("label", "audit pipeline — 6 phases"),
    blank(),
    t("brand", "  [0] resolve       address / file → ResolvedContract"),
    t("brand", "                    upstream fork detection (uniswap, aave, oz)"),
    t("brand", "  [1] inventory     structural parse · flags · dedup via cognee"),
    t("brand", "  [2] slither       static analysis · diff-only on forks"),
    t("brand", "  [3] triage        claude-haiku · risk_score 0–10 · gate <3 = SAFE"),
    t("accent","  [4] investigate   claude-sonnet · adversarial agent · 7 tools"),
    t("brand", "                    read_contract / search_pattern / get_call_graph"),
    t("brand", "                    get_storage_layout / query_memory"),
    t("brand", "                    simulate_call / anchor_finding"),
    t("brand", "  [5] anchor        keeperhub direct execution · safety net"),
    t("brand", "  [6] report        json + onchain proof + ENS cert"),
    blank(),
    t("comment", "# core execution: phase 4 — adversarial reading before checklist"),
  ],
});

const stack: CommandHandler = () => ({
  lines: [
    t("label", "technology stack"),
    blank(),
    t("log", "  KeeperHub          onchain anchoring notary (MCP + direct API)"),
    t("log", "  0G Storage         decentralized pattern storage (KV testnet)"),
    t("log", "  ENS                audit certificate registry (namespace SDK)"),
    t("log", "  x402               HTTP-native USDC payments (eip-3009)"),
    t("log", "  Cognee             tridimensional persistent memory"),
    t("log", "  Anthropic          claude-haiku-4-5 + claude-sonnet-4-5"),
    t("log", "  Slither            static analysis (trail of bits)"),
    t("log", "  FastAPI            backend api server"),
    t("log", "  Next.js 16         frontend (this page)"),
  ],
});

const progress = (
  value: number,
  sublabel: string,
  status: ProgressLine["status"] = "running",
): ProgressLine => ({
  kind: "progress",
  value,
  label: "audit progress",
  sublabel,
  status,
});

const auditDemo: CommandHandler = () => {
  return {
    lines: [
      t("danger", "ERROR: Web audits are disabled in production."),
      blank(),
      t("log", "Onchor.ai is the Etherscan of smart contract security."),
      t("log", "To guarantee on-chain proofs and decentralized execution, all audits"),
      t("log", "must be run from your local CLI."),
      blank(),
      t("accent", "Install the CLI:"),
      t("log", "  pip install onchor-ai"),
      blank(),
      t("accent", "Run an audit:"),
      t("log", "  onchor-ai audit ./my-contracts/"),
      blank(),
      t("comment", "# View your audit history securely by typing `history`"),
    ],
  };
};

const clear: CommandHandler = () => ({ clear: true, lines: [] });

const banner = (): ShellLine[] => [
  { kind: "banner", content: ASCII_LOGO },
  blank(),
  t("muted", "Solidity Security Copilot · Persistent Collective Memory"),
  t("comment", "# type `help` to list available commands"),
  blank(),
];

// ─── man pages ───────────────────────────────────────────────────────────────
const MAN_PAGES: Record<string, ShellLine[]> = {
  audit: [
    t("label", "AUDIT(1)                  Onchor.ai Manual                 AUDIT(1)"),
    blank(),
    t("label", "NAME"),
    t("log",  "       audit — run a complete security audit"),
    blank(),
    t("label", "SYNOPSIS"),
    t("log",  "       onchor-ai audit <path|address> [--local|--dev]"),
    blank(),
    t("label", "DESCRIPTION"),
    t("log",  "       Runs the full 6-phase pipeline against the target."),
    t("log",  "       Triggers an x402 USDC payment unless --local or --dev."),
    blank(),
    t("label", "OPTIONS"),
    t("log",  "       --local   skip payment, use local memory only"),
    t("log",  "       --dev     bypass everything (no x402, no anchor)"),
  ],
  memory: [
    t("label", "MEMORY(1)                Onchor.ai Manual                 MEMORY(1)"),
    blank(),
    t("log", "       Collective memory is anonymized and immutable."),
    t("log", "       Patterns are stored on 0G Storage and anchored via KeeperHub."),
  ],
};

const man: CommandHandler = (args) => {
  const cmd = (args[0] || "").toLowerCase();
  if (!cmd) {
    return {
      lines: [
        t("warn", "What manual page do you want?"),
        t("muted", "usage: man <command>"),
      ],
    };
  }
  const page = MAN_PAGES[cmd];
  if (!page) {
    return { lines: [t("danger", `No manual entry for ${cmd}`)] };
  }
  return { lines: page };
};

// ─── External-link commands (handled by the shell with side effects) ─────────
const navHistory: CommandHandler = () => ({
  lines: [t("muted", "opening /history…")],
});
const navMemoryPage: CommandHandler = () => ({
  lines: [t("muted", "opening /memory…")],
});
const navGithub: CommandHandler = () => ({
  lines: [t("muted", "opening github.com/cnm-agency/Onchor-ai…")],
});

const exitCmd: CommandHandler = () => ({
  lines: [
    t("warn", "you can't escape — there is no exit from this shell."),
    t("comment", "# (try `clear` instead)"),
  ],
});

// ─── Registry ─────────────────────────────────────────────────────────────────
export const COMMANDS: Record<string, CommandHandler> = {
  help,
  "?": help,
  version,
  v: version,
  whoami: status,
  status,
  doctor,
  init,
  memory,
  pricing,
  pipeline,
  stack,
  audit: auditDemo,
  history: navHistory,
  "memory-page": navMemoryPage,
  github: navGithub,
  man,
  clear,
  cls: clear,
  exit: exitCmd,
  quit: exitCmd,
  q: exitCmd,
};

export const COMMAND_NAMES = Object.keys(COMMANDS).sort();

export function bootBanner(): ShellLine[] {
  return banner();
}

export function notFound(cmd: string): ShellLine[] {
  return [
    {
      kind: "text",
      style: "danger",
      content: `command not found: ${cmd}`,
    },
    { kind: "text", style: "comment", content: "# type `help` for the list of commands" },
  ];
}
