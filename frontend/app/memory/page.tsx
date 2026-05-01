"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import { Terminal, ChevronLeft, ChevronDown, Database, Shield, ExternalLink, Loader2 } from "lucide-react";
import { useState, useEffect } from "react";
import { getMemoryStats } from "@/lib/api";

const SEVERITY_COLOR: Record<string, string> = {
  HIGH:   "text-red-400 border-red-400/30 bg-red-400/10",
  MEDIUM: "text-yellow-400 border-yellow-400/30 bg-yellow-400/10",
  LOW:    "text-blue-400 border-blue-400/30 bg-blue-400/10",
};

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function MemoryPage() {
  const router = useRouter();
  
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [expandedHits, setExpandedHits] = useState<Record<number, boolean>>({});

  const toggleHit = (index: number) => {
    setExpandedHits(prev => ({ ...prev, [index]: !prev[index] }));
  };

  useEffect(() => {
    getMemoryStats()
      .then(setStats)
      .catch((e) => console.error(e))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0a0a0a] flex items-center justify-center">
        <Loader2 className="w-6 h-6 text-[#0DFC67] animate-spin" />
      </div>
    );
  }

  const memoryData = stats || {
    total_patterns: 0,
    confirmed_patterns: 0,
    sources: [],
    pattern_types: [],
    recent_hits: [],
  };

  const totalPatterns = memoryData.total_patterns;

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-zinc-100 relative selection:bg-white/20 font-sans">
      
      {/* Subtle modern background blur */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full max-w-3xl h-[400px] bg-white opacity-[0.02] rounded-[100%] blur-[100px] pointer-events-none" />
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[500px] h-[200px] bg-[#0DFC67] opacity-[0.03] rounded-full blur-3xl pointer-events-none" />

      {/* Nav */}
      <nav className="relative z-10 flex flex-col sm:flex-row items-center justify-between px-6 py-6 max-w-6xl mx-auto border-b border-white/5 gap-4 sm:gap-0">
        <button
          onClick={() => router.push("/")}
          className="flex items-center gap-3 hover:opacity-80 transition-opacity"
        >
          <ChevronLeft className="w-4 h-4 text-zinc-400 shrink-0" />
          <Image src="/OnchorAI-logo.png" alt="Onchor.ai Logo" width={32} height={32} className="rounded-lg shrink-0" />
          <span className="font-semibold text-sm tracking-tight text-zinc-100">Onchor.ai</span>
        </button>
        <div className="flex items-center gap-2">
          <Terminal className="w-4 h-4 text-[#0DFC67] shrink-0" />
          <span className="font-medium text-sm text-zinc-400 text-center">Collective Memory</span>
        </div>
      </nav>

      <main className="relative z-10 max-w-4xl mx-auto px-6 pt-12 pb-24 space-y-12">

        {/* Header */}
        <div>
          <div className="flex items-center gap-2 mb-4">
            <div className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
            <span className="text-xs font-medium text-cyan-400">Live — 0G Storage</span>
          </div>
          <h1 className="text-4xl font-bold tracking-tight mb-4 text-white">Collective Memory</h1>
          <p className="text-zinc-400 leading-relaxed max-w-xl">
            Anonymized vulnerability patterns stored on 0G Storage — decentralized and permanent.
            Unlocked by the paid tier. A forked repo starts with zero patterns.{" "}
            <span className="text-zinc-300">This base is the moat.</span>
          </p>
        </div>

        {/* ── Top stats ───────────────────────────────────────────── */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-8">
          {[
            { value: totalPatterns.toLocaleString(), label: "Total patterns",     color: "text-[#0DFC67]" },
            { value: memoryData.confirmed_patterns.toLocaleString(), label: "CONFIRMED",  color: "text-[#0DFC67]" },
            { value: "0",  label: "Hacks referenced", color: "text-red-400"  },
            { value: memoryData.sources.length.toString(), label: "Sources", color: "text-cyan-400" },
          ].map((s) => (
            <div key={s.label} className="bg-zinc-900/40 border border-white/5 rounded-2xl px-6 py-5 text-center">
              <div className={`text-2xl font-bold mb-1 ${s.color}`}>{s.value}</div>
              <div className="text-xs text-zinc-500 font-medium">{s.label}</div>
            </div>
          ))}
        </div>

        {/* ── Sources ─────────────────────────────────────────────── */}
        <div>
          <h2 className="text-xs font-medium text-zinc-500 mb-4">Sources</h2>
          <div className="border border-white/5 bg-zinc-900/30 divide-y divide-white/5 rounded-2xl overflow-hidden">
            {memoryData.sources.map((source: any) => {
              const pct = totalPatterns > 0 ? Math.round((source.count / totalPatterns) * 100) : 0;
              return (
                <div key={source.name} className="px-5 py-4 flex items-center gap-4 hover:bg-white/[0.02] transition-colors">
                  <Database className="w-4 h-4 text-zinc-500 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-2 gap-2">
                      {source.url ? (
                        <a 
                          href={source.url} 
                          target="_blank" 
                          rel="noopener noreferrer"
                          className="text-sm font-medium text-zinc-300 truncate hover:text-[#0DFC67] transition-colors flex items-center gap-1.5"
                        >
                          {source.name} <ExternalLink className="w-3 h-3 opacity-50" />
                        </a>
                      ) : (
                        <span className="text-sm font-medium text-zinc-300 truncate">{source.name}</span>
                      )}
                      <span className={`text-xs font-medium ${source.color} shrink-0`}>{source.count} patterns</span>
                    </div>
                    <div className="w-full h-1 bg-white/5 rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all duration-700"
                        style={{
                          width: `${pct}%`,
                          backgroundColor: source.color.replace("text-", "").includes("red")
                            ? "#f87171" : source.color.includes("yellow") ? "#facc15"
                            : source.color.includes("blue") ? "#60a5fa" : "#c084fc",
                        }}
                      />
                    </div>
                  </div>
                  <span className="text-xs font-medium text-zinc-500 w-8 text-right shrink-0">{pct}%</span>
                </div>
              );
            })}
            {memoryData.sources.length === 0 && (
              <div className="px-5 py-6 text-center text-zinc-500 text-sm">
                No sources indexed yet.
              </div>
            )}
          </div>
        </div>

        {/* ── Pattern types ────────────────────────────────────────── */}
        <div>
          <h2 className="text-xs font-medium text-zinc-500 mb-4">Pattern types</h2>
          <div className="space-y-3 bg-zinc-900/30 border border-white/5 p-6 rounded-2xl">
            {memoryData.pattern_types.map((p: any) => (
              <div key={p.type} className="flex items-center gap-4">
                <span className="text-sm font-medium text-zinc-400 w-24 md:w-36 shrink-0 truncate">{p.type}</span>
                <div className="flex-1 h-1.5 bg-white/5 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-[#0DFC67] rounded-full transition-all duration-700 opacity-60"
                    style={{ width: `${p.pct}%` }}
                  />
                </div>
                <span className="text-sm font-medium text-zinc-500 w-8 text-right shrink-0">{p.count}</span>
              </div>
            ))}
            {memoryData.pattern_types.length === 0 && (
              <div className="text-center text-zinc-500 text-sm py-4">
                No patterns identified yet.
              </div>
            )}
          </div>
        </div>

        {/* ── Recent memory hits ───────────────────────────────────── */}
        <div>
          <h2 className="text-xs font-medium text-zinc-500 mb-4">
            Recent Memory Hits
          </h2>
          <div className="divide-y divide-white/5 border border-white/5 bg-zinc-900/30 rounded-2xl overflow-hidden">
            {memoryData.recent_hits.map((hit: any, i: number) => {
              const isExpanded = expandedHits[i];
              return (
                <div key={i} className="flex flex-col border-b border-white/5 last:border-b-0 hover:bg-white/[0.02] transition-colors">
                  <div 
                    className="px-5 py-4 flex items-center gap-4 flex-wrap cursor-pointer"
                    onClick={() => toggleHit(i)}
                  >
                    <div className={`text-xs px-2 py-0.5 border font-medium rounded-md shrink-0 ${SEVERITY_COLOR[hit.severity]}`}>
                      {hit.severity}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-zinc-200 mb-0.5 line-clamp-1">{hit.match}</div>
                      <div className="text-xs text-zinc-500 flex items-center gap-2">
                        <span>pattern: <span className="text-zinc-400 font-medium">{hit.pattern}</span></span>
                        {hit.tx_hash && (
                          <>
                            <span>•</span>
                            <a 
                              href={`https://chainscan-galileo.0g.ai/tx/${hit.tx_hash}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-[#0DFC67] hover:underline flex items-center gap-1"
                              onClick={(e) => e.stopPropagation()}
                            >
                              <ExternalLink className="w-3 h-3" /> 0G Tx
                            </a>
                          </>
                        )}
                        {hit.root_hash && (
                          <>
                            <span>•</span>
                            <span className="text-cyan-400 flex items-center gap-1">
                              <Database className="w-3 h-3" /> {hit.root_hash.slice(0, 10)}...{hit.root_hash.slice(-8)}
                            </span>
                          </>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-4 shrink-0">
                      {hit.amount !== "N/A" && (
                        <span className="text-sm text-red-400 font-semibold">{hit.amount}</span>
                      )}
                      <span className="text-xs text-zinc-400 font-medium bg-white/5 border border-white/10 rounded-md px-2 py-1">
                        {hit.confirmations} confirmations
                      </span>
                      <ChevronDown className={`w-4 h-4 text-zinc-500 transition-transform ${isExpanded ? "rotate-180" : ""}`} />
                    </div>
                  </div>
                  
                  {isExpanded && (
                    <div className="px-5 pb-5 pt-2 border-t border-white/5 bg-black/20">
                      <div className="space-y-4">
                        <div>
                          <div className="text-xs font-medium text-zinc-500 mb-1">Abstract Description</div>
                          <div className="text-sm text-zinc-300 leading-relaxed bg-zinc-900/50 p-3 rounded-lg border border-white/5">
                            {hit.match}
                          </div>
                        </div>
                        <div className="flex flex-wrap gap-4">
                          {hit.pattern_hash && (
                            <div>
                              <div className="text-xs font-medium text-zinc-500 mb-1">Pattern Hash</div>
                              <div className="text-xs font-mono text-zinc-400 bg-zinc-900/50 px-2 py-1 rounded border border-white/5">
                                {hit.pattern_hash}
                              </div>
                            </div>
                          )}
                          {hit.keywords && hit.keywords.length > 0 && (
                            <div>
                              <div className="text-xs font-medium text-zinc-500 mb-1">Semantic Keywords</div>
                              <div className="flex flex-wrap gap-2">
                                {hit.keywords.map((kw: string, kidx: number) => (
                                  <span key={kidx} className="text-xs bg-white/5 text-zinc-300 px-2 py-0.5 rounded border border-white/10">
                                    {kw}
                                  </span>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
            {memoryData.recent_hits.length === 0 && (
              <div className="px-5 py-6 text-center text-zinc-500 text-sm">
                No recent hits in memory.
              </div>
            )}
          </div>
        </div>

        {/* ── How anonymization works ──────────────────────────────── */}
        <div>
          <h2 className="text-xs font-medium text-zinc-500 mb-4">
            How anonymization works
          </h2>
          <div className="border border-white/5 bg-zinc-900/30 p-6 rounded-2xl space-y-6">
            <div className="flex items-start gap-3">
              <Shield className="w-5 h-5 text-[#0DFC67] shrink-0" />
              <div>
                <div className="text-sm font-medium text-zinc-200 mb-1">What we store</div>
                <p className="text-sm text-zinc-500 leading-relaxed">
                  Normalized snippet (identifiers replaced), abstract description, fix pattern, severity, confidence count.
                </p>
              </div>
            </div>
            <div className="border border-white/5 bg-zinc-950/50 p-5 rounded-xl overflow-x-auto w-full">
              <pre className="text-xs text-zinc-400 leading-relaxed font-mono whitespace-pre w-max">{`{
  pattern_hash:         "sha256(normalized_snippet)",
  pattern_type:         "reentrancy",
  normalized_snippet:   "call{value: VAR_AMOUNT}(ADDR_RECIPIENT)\\n                         MAPPING_USER[msg.sender][VAR_INDEX] = 0",
  abstract_description: "external call before state update",
  fix_pattern:          "Apply CEI: effect before interaction",
  severity:             "HIGH",
  confirmation_count:   14
}`}</pre>
            </div>
            <div className="flex items-start gap-3">
              <Shield className="w-5 h-5 text-red-400 shrink-0" />
              <div>
                <div className="text-sm font-medium text-zinc-200 mb-1">What we never store</div>
                <p className="text-sm text-zinc-500">
                  contract_address · project_name · raw_code · wallet addresses
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* ── 0G Storage link ──────────────────────────────────────── */}
        <div className="border border-cyan-500/20 bg-cyan-500/5 p-6 rounded-2xl flex items-start justify-between gap-4 flex-wrap">
          <div className="flex items-start gap-4">
            <Database className="w-5 h-5 text-cyan-400 shrink-0 mt-0.5" />
            <div>
              <div className="text-sm font-medium text-cyan-400 mb-1">Stored on 0G Storage — decentralized</div>
              <p className="text-sm text-cyan-400/70 leading-relaxed">
                Every pattern is stored on 0G KV Storage indexed by{" "}
                <span className="text-cyan-300 font-medium">pattern_hash</span>.
                The rootHash is anchored onchain via KeeperHub.
                If our service goes down, the base remains accessible.
              </p>
            </div>
          </div>
          <a
            href="https://storagescan-galileo.0g.ai/address/0xe97F62b7Bf214303419189ECD3D6688FdfF30Fd8"
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm font-medium text-cyan-400 hover:text-[#0DFC67] transition-colors flex items-center gap-1.5 shrink-0"
          >
            View Onchain Activity <ExternalLink className="w-4 h-4" />
          </a>
        </div>

      </main>
    </div>
  );
}
