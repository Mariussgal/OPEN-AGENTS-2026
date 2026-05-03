"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import { useState, useRef, useEffect } from "react";
import { Check, Copy, Menu, X } from "lucide-react";
import { Shell } from "@/components/shell/Shell";
import { TerminalWindow } from "@/components/branding/TerminalWindow";
import { APP_VERSION } from "@/lib/app-version";

// ─── Static data ──────────────────────────────────────────────────────────────

const PHASES = [
  {
    id: 0,
    name: "Target Resolution",
    desc: "Detects address or local source. Identifies forks (Uniswap, Euler, OZ) and automatically reduces scope to custom diffs only.",
  },
  {
    id: 1,
    name: "Semantic Inventory",
    desc: "Cognee structural parsing. Indexes the 0G library to retrieve past hacks and relevant security patterns for the specific codebase.",
  },
  {
    id: 2,
    name: "Static Analysis",
    desc: "Slither deep scan. Runs 89+ deterministic detectors to provide high-precision raw signals and data-flow graphs for the AI agent.",
  },
  {
    id: 3,
    name: "Cost-Gate Triage",
    desc: "GPT-4o-mini scoring. Rapidly assesses each file (0–10). A score below 3 halts the pipeline instantly with a SAFE verdict.",
  },
  {
    id: 4,
    name: "Adversarial Agent",
    desc: "Sonnet 4.5 investigation. An autonomous LLM agent with 7 security tools and 30-turn recursion for deep vulnerability discovery.",
    core: true,
  },
  {
    id: 5,
    name: "Onchain Anchor",
    desc: "Immutable Notarization. Confirmed findings are anchored to 0G Storage and notarized onchain via KeeperHub direct execution.",
  },
  {
    id: 6,
    name: "Final Report",
    desc: "Verified Proof. Generates enriched JSON reports with fix sketches and historical refs, plus a minted ENS audit certificate.",
  },
];

const STACK = [
  { name: "KeeperHub", role: "Onchain anchoring notary" },
  { name: "0G Storage", role: "Decentralized pattern storage" },
  { name: "ENS", role: "Audit certificate registry" },
  { name: "x402", role: "HTTP-native USDC payments" },
  { name: "Cognee", role: "Tridimensional memory" },
  { name: "OpenAI & Anthropic", role: "gpt-4o-mini & claude-sonnet" },
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
        "group inline-flex min-w-0 items-center justify-center gap-2 sm:gap-3 terminal-box rounded-sm pl-3 pr-1 py-1.5 hover:border-[--terminal-brand]/60 transition-colors max-w-full",
        className,
      ].join(" ")}
    >
      {showPrompt && <span className="font-mono text-xs text-[--terminal-accent] shrink-0">$</span>}
      <code className="font-mono text-xs sm:text-sm lg:text-base text-[--terminal-label] truncate min-w-0">{cmd}</code>
      <button
        onClick={copy}
        aria-label="Copy install command"
        className="shrink-0 p-1.5 lg:p-2 rounded-sm text-[--terminal-muted] hover:text-[--terminal-accent] hover:bg-[--terminal-bg] transition-colors"
      >
        {copied ? <Check className="w-3.5 h-3.5 lg:w-4 lg:h-4" /> : <Copy className="w-3.5 h-3.5 lg:w-4 lg:h-4" />}
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
        href="https://github.com/Mariussgal/OPEN-AGENTS-2026"
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
  const [activePhase, setActivePhase] = useState(0);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;

    const handleScroll = () => {
      const scrollLeft = el.scrollLeft;
      const width = el.offsetWidth;
      // Cards are min-w-[280px] + gap-4
      const itemWidth = 280 + 16; 
      const index = Math.round(scrollLeft / itemWidth);
      setActivePhase(index);
    };

    el.addEventListener("scroll", handleScroll, { passive: true });
    return () => el.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <div className="min-h-screen bg-[--background] text-[--foreground] relative overflow-x-hidden">
      {/* Subtle brand glow behind hero */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full max-w-3xl h-[420px] bg-[--terminal-brand] opacity-[0.06] rounded-[100%] blur-[120px] pointer-events-none" />

      {/* ═════ HEADER — sticky, 3 equal columns ════════════════════════════ */}
      <header className="sticky top-0 z-30 backdrop-blur-md bg-[--background]/80 border-b border-[--terminal-border]">
        {/* Desktop layout: 3 columns — brand | centered text | nav */}
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-3 grid grid-cols-[minmax(0,1fr)_auto] md:grid-cols-3 items-center gap-3">

          {/* Col 1 — brand (left) */}
          <div className="flex justify-start">
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
                v{APP_VERSION}
              </span>
            </button>
          </div>

          {/* Col 2 — text (center) */}
          <div className="hidden md:flex justify-center">
            <span className="text-[10px] uppercase tracking-[0.25em] font-mono text-[--terminal-muted] whitespace-nowrap">
              ETHGlobal · Open Agents 2026
            </span>
          </div>

          {/* Col 3 — nav (right) */}
          <div className="flex justify-end items-center gap-4">
            <nav className="hidden md:flex items-center gap-6">
              <NavLinks />
            </nav>

            {/* Mobile: burger */}
            <button
              className="md:hidden text-[--terminal-muted] hover:text-[--terminal-accent] transition-colors p-1"
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

      <main className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 pt-10 sm:pt-20 pb-20 sm:pb-32 space-y-20 sm:space-y-28 lg:space-y-32">

        {/* ═════ HERO ═════════════════════════════════════════════════════ */}
        <section className="text-center max-w-5xl mx-auto flex flex-col items-center justify-center relative min-h-[calc(100svh-88px)] sm:min-h-[calc(100vh-140px)] py-16 sm:py-20">
          {/* ASCII background — below title on mobile, top-aligned on sm+ */}
          <div className="pointer-events-none absolute top-24 sm:-top-8 left-1/2 -translate-x-1/2 w-screen select-none overflow-visible flex justify-center items-start" aria-hidden>
            <pre
              className="font-mono text-[7px] leading-[0.9] text-[--terminal-brand]/18 whitespace-pre origin-top scale-[0.56] min-[420px]:scale-[0.66] sm:scale-[0.76] lg:scale-[1.15] xl:scale-[1.28]"
              style={{ width: "max-content" }}
            >
              {HERO_BG_ASCII}
            </pre>
          </div>

          {/* Veil to keep text readable */}
          <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-[--background]/50 via-[--background]/72 to-[--background]" />

          <h1
            className="relative z-10 animate-fade-in-up opacity-0 text-4xl min-[380px]:text-5xl sm:text-5xl md:text-6xl lg:text-8xl xl:text-[6.75rem] font-bold tracking-tight mb-5 sm:mb-8 lg:mb-10 text-balance leading-[1.05] px-1"
            style={{ animationDelay: "100ms" }}
          >
            <span className="text-[--terminal-label]">The audit tool that</span>{" "}
            <span className="text-[--terminal-brand] glow-brand">remembers.</span>
          </h1>

          <div
            className="relative z-10 animate-fade-in-up opacity-0 flex flex-col items-center justify-center gap-3 mb-6 sm:mb-10 w-full px-2 sm:px-0"
            style={{ animationDelay: "200ms" }}
          >
            <CopyCommand cmd={INSTALL_CMD} className="w-full sm:w-auto max-w-sm sm:max-w-none lg:text-base lg:px-4 lg:py-2" />
          </div>

          <p
            className="relative z-10 animate-fade-in-up opacity-0 text-sm sm:text-lg lg:text-xl text-[--terminal-muted] lg:text-[--terminal-label] max-w-2xl lg:max-w-3xl text-balance leading-relaxed font-mono px-1 lg:[text-shadow:0_1px_10px_var(--background),0_0_24px_var(--background)]"
            style={{ animationDelay: "300ms" }}
          >
            A Solidity security copilot with persistent collective memory.
            Cross-references your code against thousands of past audits and
            anchors every confirmed finding onchain.
          </p>

          <a
            href="#playground"
            className="relative z-10 animate-fade-in-up opacity-0 font-mono text-xs uppercase tracking-[0.18em] text-[--terminal-muted] hover:text-[--terminal-accent] transition-colors px-3 py-2 mt-8 sm:mt-16"
            style={{ animationDelay: "800ms" }}
          >
            try the playground ↓
          </a>
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
              type <span className="text-[--terminal-accent]">help</span>.
            </p>
          </div>

          <TerminalWindow title="onchor-ai" live className="h-[420px] min-[380px]:h-[460px] sm:h-[520px]" bodyClassName="p-0">
            <Shell />
          </TerminalWindow>
        </section>

        {/* ═════ HOW IT WORKS — 7 phases ═══════════════════════════════════ */}
        <section className="max-w-5xl mx-auto w-full">
          <div className="text-center mb-10">
            <span className="text-[10px] uppercase tracking-[0.25em] font-mono text-[--terminal-muted]">
              architecture
            </span>
            <h2 className="mt-2 text-2xl sm:text-3xl font-semibold tracking-tight text-[--terminal-label]">
              How it works
            </h2>
          </div>

          <div 
            ref={scrollRef}
            className="flex overflow-x-auto sm:flex-wrap sm:justify-center gap-4 pb-6 sm:pb-0 snap-x snap-mandatory scrollbar-hide"
          >
            {PHASES.map((phase) => (
              <div
                key={phase.id}
                className="terminal-box rounded-sm p-4 sm:p-5 hover:border-[--terminal-brand]/60 transition-colors flex flex-col min-w-[280px] sm:min-w-0 sm:w-[calc(50%-0.5rem)] lg:w-[calc(33.33%-0.7rem)] snap-start"
              >
                <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
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
          {/* Pagination dots for mobile */}
          <div className="flex justify-center gap-2 mt-2 sm:hidden">
            {PHASES.map((phase) => (
              <div
                key={`dot-${phase.id}`}
                className={`w-1.5 h-1.5 rounded-full transition-all duration-300 ${
                  activePhase === phase.id 
                    ? "bg-[--terminal-brand] w-3" 
                    : "bg-[--terminal-border]"
                }`}
              />
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

          <div className="relative w-full overflow-hidden flex flex-col gap-4 py-4">
            {/* Smooth edge masks */}
            <div className="absolute inset-y-0 left-0 w-24 sm:w-32 bg-gradient-to-r from-[--background] to-transparent z-10 pointer-events-none" />
            <div className="absolute inset-y-0 right-0 w-24 sm:w-32 bg-gradient-to-l from-[--background] to-transparent z-10 pointer-events-none" />

            {/* Row 1: Right Moving (Infrastructure) */}
            <div className="flex w-max animate-marquee-right items-stretch">
              {[...STACK.slice(0, 3), ...STACK.slice(0, 3), ...STACK.slice(0, 3), ...STACK.slice(0, 3)].map((s, i) => (
                <div key={`${s.name}-r1-${i}`} className="shrink-0 px-2">
                  <div className="terminal-box h-full px-4 py-2.5 rounded-sm flex items-center justify-center gap-3 whitespace-nowrap">
                    <span className="font-mono text-xs text-[--terminal-brand]">{s.name}</span>
                    <span className="text-[--terminal-comment]">::</span>
                    <span className="font-mono text-xs text-[--terminal-muted]">{s.role}</span>
                  </div>
                </div>
              ))}
            </div>

            {/* Row 2: Left Moving (API & AI) */}
            <div className="flex w-max animate-marquee-left items-stretch">
              {[...STACK.slice(3), ...STACK.slice(3), ...STACK.slice(3), ...STACK.slice(3)].map((s, i) => (
                <div key={`${s.name}-r2-${i}`} className="shrink-0 px-2">
                  <div className="terminal-box h-full px-4 py-2.5 rounded-sm flex items-center justify-center gap-3 whitespace-nowrap">
                    <span className="font-mono text-xs text-[--terminal-brand]">{s.name}</span>
                    <span className="text-[--terminal-comment]">::</span>
                    <span className="font-mono text-xs text-[--terminal-muted]">{s.role}</span>
                  </div>
                </div>
              ))}
            </div>
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

            <div className="grid grid-cols-1 min-[420px]:grid-cols-2 md:grid-cols-4 gap-3 mb-6">
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
          </TerminalWindow>
        </section>

      </main>

      {/* ═════ FOOTER ═══════════════════════════════════════════════════════ */}
      <footer className="relative z-10 border-t border-[--terminal-border] px-4 sm:px-6 py-6">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-3 text-center sm:text-left">
          <span className="text-xs font-mono text-[--terminal-muted]">
            <span className="text-[--terminal-comment]"></span> Marius · Cyriac · Nohem — CNM Agency
          </span>
          <span className="text-xs font-mono text-[--terminal-muted]">
            <span className="text-[--terminal-comment]"></span> ETHGlobal Open Agents 2026
          </span>
        </div>
      </footer>
    </div>
  );
}
