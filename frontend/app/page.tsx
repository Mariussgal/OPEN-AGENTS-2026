"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import { useState } from "react";

// ─── Copy button ──────────────────────────────────────────────────────────────

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  function copy() {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }
  return (
    <button
      onClick={copy}
      className="shrink-0 text-xs text-zinc-500 hover:text-zinc-300 transition-colors bg-white/5 hover:bg-white/10 px-2.5 py-1.5 rounded-md font-medium"
    >
      {copied ? "Copied" : "Copy"}
    </button>
  );
}

// ─── Code line ────────────────────────────────────────────────────────────────

function CodeLine({ command, comment }: { command: string; comment?: string }) {
  return (
    <div className="flex items-center justify-between group bg-zinc-900/50 border border-white/5 rounded-xl p-3 hover:border-white/10 transition-all">
      <div className="flex items-center gap-3 overflow-hidden">
        <span className="font-mono text-xs text-zinc-500 shrink-0">$</span>
        <span className="font-mono text-sm text-zinc-200 truncate">{command}</span>
        {comment && <span className="font-mono text-xs text-zinc-600 shrink-0 hidden md:block"># {comment}</span>}
      </div>
      <CopyButton text={command} />
    </div>
  );
}

// ─── Data ─────────────────────────────────────────────────────────────────────

const COMPARISON = [
  { tool: "Slither / Mythril", memory: "None", payment: "Free", limit: "Unfiltered false positives" },
  { tool: "GPT-4 / Claude direct", memory: "Conversation context", payment: "Subscription", limit: "Resets every session" },
  { tool: "Onchor.ai", memory: "Tridimensional (Cognee)", payment: "x402 USDC pay-per-use", limit: "—", highlight: true },
];

const PHASES = [
  { id: 1, name: "Resolve", desc: "Detects contract address or local files. Identifies known forks and reduces scope to the diff only." },
  { id: 2, name: "Inventory", desc: "Structural parse without LLM. Flags delegatecall, unchecked, assembly. Deduplicates findings." },
  { id: 3, name: "Slither", desc: "Static analysis JSON. On detected fork, only modified files are scanned." },
  { id: 4, name: "Triage", desc: "claude-haiku-4-5 scores each file 0–10. Score < 3 stops the pipeline safely." },
  { id: 5, name: "Investigation", desc: "claude-sonnet reads code adversarially with 7 tools, 30 turns, cross-referencing memory patterns.", core: true },
  { id: 6, name: "Anchor", desc: "JSON report anchored onchain via KeeperHub. Zero HIGH findings mints an ENS certificate." },
];

const DEMO_LINES: { text: string; cls: string }[] = [
  { text: "Onchor.ai v0.1.0", cls: "text-zinc-500" },
  { text: "-----------------------------------------------------", cls: "text-zinc-800" },
  { text: "[x402]    Paying 0.50 USDC for audit...   ✓ tx: 0x8fa3...", cls: "text-zinc-400" },
  { text: "[Phase 1] Resolving...          ✓ 1 file (EulerVault.sol)", cls: "text-zinc-300" },
  { text: "[Phase 2] Inventory...          ✓ 2 flags (delegatecall, unchecked)", cls: "text-zinc-300" },
  { text: "[Phase 3] Slither...            ✓ 3 findings (1 HIGH, 1 MED, 1 LOW)", cls: "text-zinc-300" },
  { text: "[Phase 4] Triage...             risk_score: 8.4 / 10", cls: "text-zinc-300" },
  { text: "[Phase 5] Investigating...", cls: "text-zinc-300" },
  { text: "  > query_memory('reentrancy external call')", cls: "text-zinc-500" },
  { text: "  Memory hit: Euler Finance hack (2024-03-15) — $197M", cls: "text-blue-400" },
  { text: "  Finding CONFIRMED — anchoring onchain now...", cls: "text-zinc-300" },
  { text: "  ✓ f-001 anchored → 0x7f2e... (KeeperHub)", cls: "text-zinc-300" },
  { text: "[Phase 6] Verifying anchors... ✓ 2/2 confirmed", cls: "text-zinc-300" },
  { text: "-----------------------------------------------------", cls: "text-zinc-800" },
  { text: "VERDICT: HIGH RISK (7.8/10)", cls: "text-zinc-100 font-medium" },
  { text: "[HIGH] EulerVault.sol:142  Reentrancy — withdraw() external before state", cls: "text-zinc-300" },
  { text: "[MED]  EulerVault.sol:89   Missing access control — setFeeRecipient()", cls: "text-zinc-400" },
  { text: "Onchain proof: https://sepolia.etherscan.io/tx/0x3bc4...", cls: "text-zinc-500" },
];

const STACK = [
  { name: "KeeperHub", role: "Onchain anchoring notary" },
  { name: "0G Storage", role: "Decentralized pattern storage" },
  { name: "ENS", role: "Audit certificates mapping" },
  { name: "x402", role: "HTTP-native USDC payments" },
  { name: "Cognee", role: "Tridimensional memory" },
  { name: "Anthropic", role: "Haiku and Sonnet models" },
];

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function HomePage() {
  const router = useRouter();

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-zinc-100 relative selection:bg-white/20 font-sans">

      {/* Subtle modern background blur */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full max-w-3xl h-[400px] bg-white opacity-[0.02] rounded-[100%] blur-[100px] pointer-events-none" />

      {/* Nav */}
      <nav className="relative z-10 flex items-center justify-between px-6 py-6 max-w-6xl mx-auto">
        <div className="flex items-center gap-3">
          <Image src="/OnchorAI-logo.png" alt="Onchor.ai Logo" width={32} height={32} className="rounded-lg" />
          <span className="font-semibold text-sm tracking-tight">Onchor.ai</span>
          <span className="text-xs text-zinc-500 bg-white/5 px-2 py-0.5 rounded-full">v0.1.0</span>
        </div>
        <div className="flex items-center gap-6">
          <button
            onClick={() => router.push("/history")}
            className="text-sm text-zinc-400 hover:text-zinc-100 transition-colors font-medium"
          >
            Audit History
          </button>
          <a
            href="https://github.com/cnm-agency/Onchor-ai"
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-zinc-400 hover:text-zinc-100 transition-colors font-medium flex items-center gap-1"
          >
            GitHub <span className="text-zinc-600">↗</span>
          </a>
        </div>
      </nav>

      <main className="relative z-10 max-w-6xl mx-auto px-6 pt-24 pb-32 space-y-32">

        {/* ── Hero ───────────────────────────────────────────────────────── */}
        <section className="text-center max-w-4xl mx-auto flex flex-col items-center">
          <div className="inline-flex items-center gap-2 mb-8 bg-white/5 border border-white/10 rounded-full px-4 py-1.5">
            <div className="w-1.5 h-1.5 rounded-full bg-blue-500" />
            <span className="text-xs font-medium text-zinc-300">ETHGlobal Open Agents 2026</span>
          </div>

          <h1 className="text-5xl md:text-7xl font-bold tracking-tight mb-8 whitespace-nowrap text-[#0DFC67] leading-[1.1]">The audit tool that <span className="text-zinc-400">remembers.</span></h1>

          <p className="text-lg text-zinc-400 max-w-2xl text-balance mb-12 leading-relaxed">
            A minimalist CLI agent that cross-references your Solidity against 1,847 real-world vulnerability patterns and anchors every confirmed finding onchain.
          </p>

          <div className="w-full max-w-md mx-auto">
            <CodeLine command="pip install Onchor-ai" />
          </div>
        </section>

        {/* ── Getting started ─────────────────────────────────────────────── */}
        <section className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-start max-w-5xl mx-auto">
          <div>
            <h2 className="text-2xl font-semibold tracking-tight mb-4 text-[#0DFC67]">Quick start</h2>
            <p className="text-zinc-400 mb-8 leading-relaxed">
              Initialize your environment, fund your local wallet with USDC, and start auditing smart contracts directly from your terminal.
            </p>
            <div className="space-y-4">
              <div className="p-5 bg-zinc-900/40 border border-white/5 rounded-3xl">
                <h3 className="text-sm font-medium mb-3 text-[#0DFC67]">1. Install</h3>
                <CodeLine command="pip install Onchor-ai" />
              </div>
              <div className="p-5 bg-zinc-900/40 border border-white/5 rounded-3xl">
                <h3 className="text-sm font-medium mb-3 text-[#0DFC67]">2. Initialize</h3>
                <CodeLine command="Onchor-ai init" />
              </div>
              <div className="p-5 bg-zinc-900/40 border border-white/5 rounded-3xl">
                <h3 className="text-sm font-medium mb-3 text-[#0DFC67]">3. Audit</h3>
                <CodeLine command="Onchor-ai audit ./src/" />
              </div>
            </div>
          </div>

          <div className="bg-[#0f0f11] border border-white/10 rounded-[2rem] p-6 lg:p-8 overflow-hidden shadow-2xl relative">
            <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-white/20 to-transparent" />
            <div className="flex items-center gap-2 mb-6">
              <div className="w-3 h-3 rounded-full bg-zinc-800" />
              <div className="w-3 h-3 rounded-full bg-zinc-800" />
              <div className="w-3 h-3 rounded-full bg-zinc-800" />
              <span className="text-xs text-zinc-600 font-mono ml-2">Onchor-ai audit</span>
            </div>
            <div className="space-y-1.5">
              {DEMO_LINES.map((line, i) => (
                <div key={i} className={`font-mono text-xs leading-relaxed ${line.cls}`}>
                  {line.text}
                </div>
              ))}
              <div className="flex items-center gap-1 mt-4">
                <span className="font-mono text-xs text-zinc-500">$</span>
                <span className="w-2 h-3 bg-zinc-400 animate-pulse inline-block" />
              </div>
            </div>
          </div>
        </section>



        {/* ── Pipeline ───────────────────────────────────────────────────── */}
        <section className="max-w-5xl mx-auto">
          <h2 className="text-2xl font-semibold tracking-tight mb-8 text-center text-[#0DFC67]">How it works</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {PHASES.map((phase) => (
              <div key={phase.id} className="bg-zinc-900/30 border border-white/5 p-8 rounded-[2rem] hover:bg-zinc-900/50 transition-colors">
                <div className="flex items-center justify-between mb-4">
                  <span className="text-lg font-medium text-zinc-200">{phase.name}</span>
                  <span className="text-xs font-mono text-zinc-500 bg-white/5 px-2.5 py-1 rounded-lg">{phase.id}</span>
                </div>
                <p className="text-sm text-zinc-400 leading-relaxed">{phase.desc}</p>
                {phase.core && (
                  <div className="mt-5 inline-block text-xs font-medium bg-zinc-200 text-zinc-900 px-3 py-1.5 rounded-lg">
                    Core execution
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>

        {/* ── Stack ──────────────────────────────────────────────────────── */}
        <section className="text-center max-w-5xl mx-auto">
          <h2 className="text-2xl font-semibold tracking-tight mb-8 text-[#0DFC67]">Built with modern primitives</h2>
          <div className="flex flex-wrap justify-center gap-3">
            {STACK.map((s) => (
              <div key={s.name} className="bg-zinc-900/40 border border-white/5 px-5 py-3.5 rounded-full flex items-center gap-3">
                <span className="font-medium text-sm text-zinc-200">{s.name}</span>
                <span className="w-1 h-1 rounded-full bg-zinc-700" />
                <span className="text-sm text-zinc-500">{s.role}</span>
              </div>
            ))}
          </div>
        </section>

        {/* ── Pricing ────────────────────────────────────────────────────── */}
        <section className="max-w-4xl mx-auto">
          <div className="bg-zinc-900/30 border border-white/5 rounded-[2.5rem] p-8 md:p-14 text-center">
            <h2 className="text-2xl font-semibold tracking-tight mb-4 text-[#0DFC67]">Simple pricing</h2>
            <p className="text-zinc-400 mb-10 max-w-lg mx-auto">Pay per use via HTTP-native USDC. No API keys required.</p>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
              {[
                { scope: "≤ 3 files", price: "0.50", example: "Simple ERC20" },
                { scope: "≤ 10 files", price: "1.00", example: "Vault + Router" },
                { scope: "≤ 30 files", price: "2.00", example: "Full DeFi protocol" },
                { scope: "> 30 files", price: "4.00", example: "Uniswap v4 scale" },
              ].map((tier) => (
                <div key={tier.scope} className="bg-zinc-900/40 border border-white/5 rounded-3xl p-6 text-center">
                  <div className="text-2xl font-semibold text-zinc-100 mb-2">${tier.price}</div>
                  <div className="text-sm font-medium text-zinc-400 mb-2">{tier.scope}</div>
                  <div className="text-xs text-zinc-600">{tier.example}</div>
                </div>
              ))}
            </div>
            <p className="text-sm text-zinc-500">
              Run free without anchoring using the <span className="font-mono bg-white/5 px-2 py-1 rounded-md text-zinc-300">--local</span> flag.
            </p>
          </div>
        </section>

      </main>

      {/* Footer */}
      <footer className="relative z-10 border-t border-white/5 px-6 py-8 mt-12">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <span className="text-sm text-zinc-500">Marius · Cyriac · Nohem — CNM Agency</span>
          <span className="text-sm text-zinc-500">ETHGlobal Open Agents 2026</span>
        </div>
      </footer>

    </div>
  );
}