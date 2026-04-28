"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Check, Copy, Menu, X } from "lucide-react";
import { Shell } from "@/components/shell/Shell";
import { TerminalWindow } from "@/components/branding/TerminalWindow";

// ─── Static data ──────────────────────────────────────────────────────────────

const PHASES = [
  {
    id: 0,
    name: "Resolve",
    desc: "Detects the contract address or local file. Identifies known forks (Uniswap, Aave, OZ) and reduces scope to the diff only.",
  },
  {
    id: 1,
    name: "Inventory",
    desc: "Structural parse without LLM. Flags delegatecall, unchecked, assembly. Cross-references known findings via Cognee.",
  },
  {
    id: 2,
    name: "Slither",
    desc: "Static analysis JSON output. On detected fork, only modified files are scanned to save tokens and noise.",
  },
  {
    id: 3,
    name: "Triage",
    desc: "claude-haiku-4-5 scores each file 0–10. Score below 3 stops the pipeline with a SAFE verdict.",
  },
  {
    id: 4,
    name: "Investigation",
    desc: "claude-sonnet reads code adversarially with 7 tools, 30 turns, cross-referencing memory patterns.",
    core: true,
  },
  {
    id: 5,
    name: "Anchor",
    desc: "Direct Execution API verifies and completes anchors. Mints an ENS certificate when zero HIGH findings.",
  },
];

const STACK = [
  { name: "KeeperHub", role: "Onchain anchoring notary" },
  { name: "0G Storage", role: "Decentralized pattern storage" },
  { name: "ENS", role: "Audit certificate registry" },
  { name: "x402", role: "HTTP-native USDC payments" },
  { name: "Cognee", role: "Tridimensional memory" },
  { name: "Anthropic", role: "Haiku and Sonnet models" },
];

const PRICING = [
  { scope: "≤ 3 files", price: "0.50", example: "Simple ERC20" },
  { scope: "≤ 10 files", price: "1.00", example: "Vault + Router" },
  { scope: "≤ 30 files", price: "2.00", example: "Full DeFi protocol" },
  { scope: "> 30 files", price: "4.00", example: "Uniswap v4 scale" },
];

const INSTALL_CMD = "pip install onchor-ai";
const HERO_BG_ASCII = String.raw`                                                                                                                                                               
                                                                                                                                                               
                                                                               .                                                                               
                                                                              ..::                                                                             
                                                                             ...:::                                                                            
                                                                            ....::::                                                                           
                                                                           .....:::::                                                                          
                                                                          ......::::::                                                                         
                                                                        :.......:::::::                                                                        
                                                                       :........::::::::                                                                       
                                                                      :.........:::::::::                                                                      
                                                                     :..........::::::::::                                                                     
                                                                    ............:::::::::::                                                                    
                                                                   .............::::::::::::                                                                   
                                                                  ..............:::::::::::::                                                                  
                                                                 ...............::::::::::::::                                                                 
                                                                ................:::::::::::::::                                                                
                                                               .................::::::::::::::::                                                               
                                                              ..................::::::::::::::::::                                                             
                                                             ...................:::::::::::::::::::                                                            
                                                            ....................:::::::::::::::::::-                                                           
                                                           .....................:::::::::::::::::::::                                                          
                                                          ......................:::::::::::::::::::::-                                                         
                                                        :.......................:::::::::::::::::::::::                                                        
                                                       -........................::::::::::::::::::::::::                                                       
                                                      ..........................:::::::::::::::::::::::::                                                      
                                                     .........................::-:::::::::::::::::::::::::                                                     
                                                    ......................::::::-----::::::::::::::::::::::                                                    
                                                   ..................:::::::::::----------::::::::::::::::::                                                   
                                                  ...............:::::::::::::::--------------:::::::::::::::                                                  
                                                 ...........::::::::::::::::::::-------------------:::::::::::                                                 
                                                ........::::::::::::::::::::::::------------------------:::::::                                                
                                               :...:::::::::::::::::::::::::::::----------------------------::::                                               
                                              ::::::::::::::::::::::::::::::::::--------------------------------:                                              
                                                ::::::::::::::::::::::::::::::::-------------------------------                                                
                                                   :::::::::::::::::::::::::::::----------------------------                                                   
                                                      ::::::::::::::::::::::::::-------------------------                                                      
                                              :..        :::::::::::::::::::::::----------------------        :::                                              
            .                                  :...:        -:::::::::::::::::::-------------------        -::::                                  ::           
            ...:                                 .....:        -::::::::::::::::----------------        -:::::=                                 ::::           
            ......                                .......:        ::::::::::::::-------------        -:::::::                                -:::::-           
            .........                              .........:        -::::::::::----------        -:::::::::                               :::::::::           
            ...........                              ...........        ::::::::-------        ::::::::::::                             ::::::::::::           
            ..............                            .............        .::::----        ::::::::::::::                            ::::::::::::::           
            ................                           ...............        ::-        :::::::::::::::                           :::::::::::::::::           
            ..................                          :...............:             :::::::::::::::::                          :::::::::::::::::::           
            ....................:                         .................:        :::::::::::::::::-                         :::::::::::::::::::::           
            .......................                        ...................:  :::::::::::::::::::-                       -:::::::::::::::::::::::           
            .........................                       ....................:::::::::::::::::::                       ::::::::::::::::::::::::::           
            ............................                     :..................::::::::::::::::::                     :::::::::::::::::::::::::::::           
            ..............................                     .................:::::::::::::::::                    :::::::::::::::::::::::::::::::           
            ................................                    ................::::::::::::::::                   :::::::::::::::::::::::::::::::::           
            ..........................:                          ...............::::::::::::::                           :::::::::::::::::::::::::::           
            ......................:                                .............:::::::::::::                                :::::::::::::::::::::::           
            .......................:                                ............::::::::::::                                ::::::::::::::::::::::::           
            .........................                               ............:::::::::::                               ::::::::::::::::::::::::::           
            ..........................                              ............:::::::::::                              :::::::::::::::::::::::::::           
            ............................                            ............:::::::::::                            ::::::::::::::::::: :::::::::           
            .......   :...................                          :...........:::::::::::                          ::::::::::::::::::::   ::::::::           
            .....      ......................                       ............::::::::::::                      -:::::::::::::::::::::      ::::::           
            ...          ......................:                   .............::::::::::::-                   :::::::::::::::::::::::          :::           
                          ........................:              ...............::::::::::::::              :::::::::::::::::::::::::                          
                           ............................:-    ::.................:::::::::::::::::-    --::::::::::::::::::::::::::::                           
                             ...................................................:::::::::::::::::::::::::::::::::::::::::::::::::::                            
                              ..................................................:::::::::::::::::::::::::::::::::::::::::::::::::                              
                                ................................................:::::::::::::::::::::::::::::::::::::::::::::::                                
                                  ..............................................::::::::::::::::::::::::::::::::::::::::::::::                                 
                                    ............................................::::::::::::::::::::::::::::::::::::::::::::                                   
                                      ..........................................::::::::::::::::::::::::::::::::::::::::::                                     
                                        :.......................................:::::::::::::::::::::::::::::::::::::::                                        
                                           .....................................::::::::::::::::::::::::::::::::::::                                           
                                              :.................................:::::::::::::::::::::::::::::::::                                              
                                                 ...............................::::::::::::::::::::::::::::::                                                 
                                                     ...........................::::::::::::::::::::::::::                                                     
                                                         :......................::::::::::::::::::::::                                                         
                                                             :..................::::::::::::::::::                                                             
                                                                ................:::::::::::::::                                                                
                                                                   .............::::::::::::                                                                   
                                                                     -..........::::::::::                                                                     
                                                                        ........::::::::                                                                       
                                                                         :......::::::                                                                         
                                                                           .....::::                                                                           
                                                                             ...:::                                                                            
                                                                              ..:                                                                              
                                                                                                                                                               
                                                                                                                                                               
                                                                                                                                                               `;

// ─── Sub-components ───────────────────────────────────────────────────────────

function CopyCommand({
  cmd,
  className = "",
  showPrompt = true,
}: {
  cmd: string;
  className?: string;
  showPrompt?: boolean;
}) {
  const [copied, setCopied] = useState(false);
  function copy() {
    navigator.clipboard.writeText(cmd);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  }
  return (
    <div
      className={[
        "group inline-flex items-center gap-3 terminal-box rounded-sm pl-3 pr-1 py-1.5 hover:border-[--terminal-brand]/60 transition-colors",
        className,
      ].join(" ")}
    >
      {showPrompt && <span className="font-mono text-xs text-[--terminal-accent] shrink-0">$</span>}
      <code className="font-mono text-xs sm:text-sm text-[--terminal-label] truncate">{cmd}</code>
      <button
        onClick={copy}
        aria-label="Copy install command"
        className="shrink-0 p-1.5 rounded-sm text-[--terminal-muted] hover:text-[--terminal-accent] hover:bg-[--terminal-bg] transition-colors"
      >
        {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
      </button>
    </div>
  );
}

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const router = useRouter();
  const click = (path: string) => {
    onNavigate?.();
    router.push(path);
  };
  return (
    <>
      <button
        onClick={() => click("/memory")}
        className="font-mono text-xs uppercase tracking-[0.18em] text-[--terminal-muted] hover:text-[--terminal-accent] transition-colors"
      >
        memory
      </button>
      <button
        onClick={() => click("/history")}
        className="font-mono text-xs uppercase tracking-[0.18em] text-[--terminal-muted] hover:text-[--terminal-accent] transition-colors"
      >
        history
      </button>
      <a
        href="https://github.com/cnm-agency/Onchor-ai"
        target="_blank"
        rel="noopener noreferrer"
        onClick={() => onNavigate?.()}
        className="font-mono text-xs uppercase tracking-[0.18em] text-[--terminal-muted] hover:text-[--terminal-accent] transition-colors flex items-center gap-1"
      >
        github <span aria-hidden>↗</span>
      </a>
    </>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function HomePage() {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className="min-h-screen bg-[--background] text-[--foreground] relative overflow-x-hidden">
      {/* Glow brand discret derrière le hero */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full max-w-3xl h-[420px] bg-[--terminal-brand] opacity-[0.06] rounded-[100%] blur-[120px] pointer-events-none" />

      {/* ═════ HEADER — sticky, 3 colonnes égales ══════════════════════════ */}
      <header className="sticky top-0 z-30 backdrop-blur-md bg-[--background]/80 border-b border-[--terminal-border]">
        {/* Layout desktop : 3 colonnes flex — brand | install centré | nav */}
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-3 flex items-center">

          {/* Col 1 — brand (gauche) */}
          <button
            onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
            className="flex items-center gap-2.5 shrink-0"
          >
            <Image
              src="/OnchorAI-logo.png"
              alt="Onchor.ai"
              width={26}
              height={26}
              className="rounded-sm"
            />
            <span className="font-mono text-sm tracking-tight">
              <span className="text-[--terminal-brand] font-semibold">onchor</span>
              <span className="text-[--terminal-comment]">.</span>
              <span className="text-[--terminal-accent]">ai</span>
            </span>
            <span className="hidden sm:inline-block text-[10px] uppercase tracking-[0.2em] text-[--terminal-muted] border border-[--terminal-border] px-1.5 py-0.5 rounded-sm">
              v0.1.0
            </span>
          </button>

          {/* Col 2 — install command (centre absolu) */}
          <div className="hidden md:flex flex-1 justify-center px-4">
            <CopyCommand cmd={INSTALL_CMD} className="w-full max-w-xs" />
          </div>

          {/* Col 3 — nav (droite) */}
          <nav className="hidden md:flex items-center gap-6 ml-auto shrink-0">
            <NavLinks />
          </nav>

          {/* Mobile : install compacte + burger */}
          <div className="flex md:hidden items-center gap-2 ml-auto">
            <CopyCommand cmd={INSTALL_CMD} className="max-w-[160px]" showPrompt={false} />
            <button
              className="text-[--terminal-muted] hover:text-[--terminal-accent] transition-colors p-1"
              onClick={() => setMenuOpen(!menuOpen)}
              aria-label="Toggle menu"
            >
              {menuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          </div>
        </div>

        {/* Mobile dropdown */}
        {menuOpen && (
          <div className="md:hidden border-t border-[--terminal-border] px-4 py-4 flex flex-col gap-4 bg-[--card]">
            <NavLinks onNavigate={() => setMenuOpen(false)} />
          </div>
        )}
      </header>

      <main className="relative z-10 max-w-6xl mx-auto px-4 sm:px-6 pt-16 sm:pt-20 pb-32 space-y-28 sm:space-y-32">

        {/* ═════ HERO ═════════════════════════════════════════════════════ */}
        {/*
          Le <pre> ASCII occupe toute la largeur de la page (overflow visible)
          et est positionné par rapport au <section> qui déborde de son max-w.
        */}
        <section className="text-center max-w-4xl mx-auto flex flex-col items-center relative">
          {/* ASCII background — overflow intentionnel, whitespace-pre strict */}
          <div className="pointer-events-none absolute -top-20 left-1/2 -translate-x-1/2 w-screen select-none overflow-hidden" aria-hidden>
            <pre
              className="font-mono text-[7px] leading-[0.9] text-[--terminal-brand]/20 whitespace-pre mx-auto"
              style={{ width: "max-content" }}
            >
              {HERO_BG_ASCII}
            </pre>
          </div>

          {/* Voile pour garder le texte lisible */}
          <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-[--background]/30 via-[--background]/60 to-[--background]" />

          <div className="animate-fade-in-up inline-flex items-center gap-2 mb-6 sm:mb-8 border border-[--terminal-border] px-3 py-1 rounded-sm">
            <span className="w-1.5 h-1.5 rounded-full bg-[--terminal-accent] animate-pulse-brand" />
            <span className="text-[10px] uppercase tracking-[0.25em] font-mono text-[--terminal-muted]">
              ETHGlobal · Open Agents 2026
            </span>
          </div>

          <h1
            className="animate-fade-in-up opacity-0 text-4xl sm:text-5xl md:text-6xl lg:text-7xl font-bold tracking-tight mb-6 sm:mb-8 text-balance leading-[1.05]"
            style={{ animationDelay: "100ms" }}
          >
            <span className="text-[--terminal-label]">The audit tool that</span>{" "}
            <span className="text-[--terminal-brand] glow-brand">remembers.</span>
          </h1>

          <div
            className="animate-fade-in-up opacity-0 flex flex-col items-center justify-center gap-3 mb-8 sm:mb-10"
            style={{ animationDelay: "200ms" }}
          >
            <CopyCommand cmd={INSTALL_CMD} />
            <a
              href="#playground"
              className="font-mono text-xs uppercase tracking-[0.18em] text-[--terminal-muted] hover:text-[--terminal-accent] transition-colors px-3 py-2"
            >
              try the playground ↓
            </a>
          </div>

          <p
            className="animate-fade-in-up opacity-0 text-base sm:text-lg text-[--terminal-muted] max-w-2xl text-balance leading-relaxed font-mono mt-10 sm:mt-14"
            style={{ animationDelay: "300ms" }}
          >
            A Solidity security copilot with persistent collective memory.
            Cross-references your code against thousands of past audits and
            anchors every confirmed finding onchain.
          </p>
        </section>

        {/* ═════ INTERACTIVE PLAYGROUND ══════════════════════════════════ */}
        <section
          id="playground"
          className="max-w-5xl mx-auto w-full scroll-mt-24"
        >
          <div className="text-center mb-6">
            <span className="text-[10px] uppercase tracking-[0.25em] font-mono text-[--terminal-muted]">
              live · interactive
            </span>
            <h2 className="mt-2 text-2xl sm:text-3xl font-semibold tracking-tight text-[--terminal-label]">
              Try it in your browser
            </h2>
            <p className="mt-3 text-sm text-[--terminal-muted] max-w-xl mx-auto font-mono">
              <span className="text-[--terminal-comment]">#</span> the same shell
              you get with{" "}
              <span className="text-[--terminal-accent]">onchor-ai</span>.
              type <span className="text-[--terminal-accent]">help</span>,{" "}
              <span className="text-[--terminal-accent]">audit</span> or{" "}
              <span className="text-[--terminal-accent]">memory</span>.
            </p>
          </div>

          <TerminalWindow title="onchor-ai" live className="h-[480px] sm:h-[520px]" bodyClassName="p-0">
            <Shell />
          </TerminalWindow>
        </section>

        {/* ═════ HOW IT WORKS — 6 phases ═══════════════════════════════════ */}
        <section className="max-w-5xl mx-auto w-full">
          <div className="text-center mb-10">
            <span className="text-[10px] uppercase tracking-[0.25em] font-mono text-[--terminal-muted]">
              architecture
            </span>
            <h2 className="mt-2 text-2xl sm:text-3xl font-semibold tracking-tight text-[--terminal-label]">
              How it works
            </h2>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4">
            {PHASES.map((phase) => (
              <div
                key={phase.id}
                className="terminal-box rounded-sm p-5 hover:border-[--terminal-brand]/60 transition-colors flex flex-col"
              >
                <div className="flex items-center justify-between mb-3">
                  <span className="font-mono text-sm font-semibold text-[--terminal-label]">
                    {phase.name}
                  </span>
                  <span className="text-[10px] font-mono text-[--terminal-muted] border border-[--terminal-border] px-2 py-0.5 rounded-sm flex items-center gap-1.5">
                    <span className="w-1 h-1 rounded-full bg-[--terminal-brand]" />
                    phase.{phase.id}
                  </span>
                </div>
                <p className="text-sm text-[--terminal-muted] leading-relaxed font-mono">
                  {phase.desc}
                </p>
                {phase.core && (
                  <div className="mt-4 self-start inline-flex items-center gap-2 text-[10px] uppercase tracking-[0.2em] font-mono bg-[--terminal-brand] text-[--background] px-2.5 py-1 rounded-sm">
                    <span className="w-1.5 h-1.5 rounded-full bg-[--background] animate-pulse" />
                    core execution
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>

        {/* ═════ STACK ════════════════════════════════════════════════════ */}
        <section className="max-w-5xl mx-auto w-full text-center">
          <div className="mb-10">
            <span className="text-[10px] uppercase tracking-[0.25em] font-mono text-[--terminal-muted]">
              built with
            </span>
            <h2 className="mt-2 text-2xl sm:text-3xl font-semibold tracking-tight text-[--terminal-label]">
              Modern primitives
            </h2>
          </div>

          <div className="flex flex-wrap justify-center gap-2.5">
            {STACK.map((s) => (
              <div
                key={s.name}
                className="terminal-box px-4 py-2.5 rounded-sm flex items-center gap-3"
              >
                <span className="font-mono text-xs text-[--terminal-brand]">{s.name}</span>
                <span className="text-[--terminal-comment]">::</span>
                <span className="font-mono text-xs text-[--terminal-muted] whitespace-nowrap">
                  {s.role}
                </span>
              </div>
            ))}
          </div>
        </section>

        {/* ═════ PRICING ══════════════════════════════════════════════════ */}
        <section className="max-w-4xl mx-auto w-full">
          <TerminalWindow title="onchor-ai pricing">
            <div className="text-center mb-8">
              <span className="text-[10px] uppercase tracking-[0.25em] font-mono text-[--terminal-muted]">
                x402 · base-sepolia
              </span>
              <h2 className="mt-2 text-xl sm:text-2xl font-semibold tracking-tight text-[--terminal-label]">
                Simple pricing
              </h2>
              <p className="mt-2 text-sm text-[--terminal-muted] font-mono">
                <span className="text-[--terminal-comment]">#</span> pay per use
                via HTTP-native USDC. no API keys required.
              </p>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
              {PRICING.map((tier) => (
                <div
                  key={tier.scope}
                  className="terminal-box rounded-sm p-4 text-center flex flex-col justify-center transition-colors hover:border-[--terminal-brand]/70"
                >
                  <div className="text-xl md:text-2xl font-semibold text-[--terminal-accent] font-mono mb-1">
                    ${tier.price}
                  </div>
                  <div className="text-[11px] md:text-xs font-mono text-[--terminal-label] mb-1">
                    {tier.scope}
                  </div>
                  <div className="text-[10px] md:text-[11px] font-mono text-[--terminal-comment] leading-tight">
                    {tier.example}
                  </div>
                </div>
              ))}
            </div>

            <p className="text-xs sm:text-sm text-[--terminal-muted] text-center font-mono">
              Run free without anchoring with the{" "}
              <span className="border border-[--terminal-border] px-1.5 py-0.5 rounded-sm text-[--terminal-accent]">
                --local
              </span>{" "}
              flag.
            </p>
          </TerminalWindow>
        </section>

      </main>

      {/* ═════ FOOTER ═══════════════════════════════════════════════════════ */}
      <footer className="relative z-10 border-t border-[--terminal-border] px-4 sm:px-6 py-6">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-3 text-center sm:text-left">
          <span className="text-xs font-mono text-[--terminal-muted]">
            <span className="text-[--terminal-comment]">#</span> Marius · Cyriac · Nohem — CNM Agency
          </span>
          <span className="text-xs font-mono text-[--terminal-muted]">
            <span className="text-[--terminal-comment]">#</span> ETHGlobal Open Agents 2026
          </span>
        </div>
      </footer>
    </div>
  );
}
