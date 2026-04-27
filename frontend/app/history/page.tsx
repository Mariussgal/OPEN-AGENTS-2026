"use client";

import Image from "next/image";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Terminal, ChevronLeft, ExternalLink, Shield, AlertTriangle, AlertCircle, Info } from "lucide-react";
import { getAuditHistory } from "@/lib/api";
import type { AuditSummary, Verdict } from "@/lib/types";

// ─── Verdict config ───────────────────────────────────────────────────────────

const VERDICT_CONFIG: Record<Verdict, { label: string; color: string; bg: string; icon: React.ElementType }> = {
    HIGH_RISK: { label: "HIGH RISK", color: "text-red-400", bg: "bg-red-400/10 border-red-400/20", icon: AlertTriangle },
    MEDIUM_RISK: { label: "MEDIUM RISK", color: "text-yellow-400", bg: "bg-yellow-400/10 border-yellow-400/20", icon: AlertCircle },
    LOW_RISK: { label: "LOW RISK", color: "text-blue-400", bg: "bg-blue-400/10 border-blue-400/20", icon: Info },
    SAFE: { label: "SAFE", color: "text-[#0DFC67]", bg: "bg-[#0DFC67]/10 border-[#0DFC67]/20", icon: Shield },
    CERTIFIED: { label: "CERTIFIED", color: "text-[#0DFC67]", bg: "bg-[#0DFC67]/10 border-[#0DFC67]/20", icon: Shield },
};

// ─── Risk score bar ───────────────────────────────────────────────────────────

function RiskBar({ score }: { score: number }) {
    const color = score >= 7 ? "#ff4444" : score >= 4 ? "#f59e0b" : "#0DFC67";
    return (
        <div className="flex items-center gap-2">
            <div className="w-16 h-1 bg-white/5 rounded-full overflow-hidden">
                <div
                    className="h-full rounded-full transition-all duration-500"
                    style={{ width: `${(score / 10) * 100}%`, backgroundColor: color }}
                />
            </div>
            <span className="text-xs" style={{ color }}>{score.toFixed(1)}</span>
        </div>
    );
}

// ─── Target display ───────────────────────────────────────────────────────────

function TargetLabel({ target }: { target: AuditSummary["target"] }) {
    if (target.kind === "address") {
        return (
            <span className="text-xs text-[#0DFC67]">
                {target.value.slice(0, 6)}...{target.value.slice(-4)}
            </span>
        );
    }
    return <span className="text-xs text-zinc-400">{target.value}</span>;
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function HistoryPage() {
    const router = useRouter();
    const [audits, setAudits] = useState<AuditSummary[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        getAuditHistory()
            .then(setAudits)
            .finally(() => setLoading(false));
    }, []);

    return (
        <div className="min-h-screen bg-[#0a0a0a] text-zinc-100 relative selection:bg-white/20 font-sans">

            {/* Subtle modern background blur */}
            <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full max-w-3xl h-[400px] bg-white opacity-[0.02] rounded-[100%] blur-[100px] pointer-events-none" />

            {/* Nav */}
            <nav className="relative z-10 flex items-center justify-between px-6 py-6 max-w-6xl mx-auto border-b border-white/5">
                <button
                    onClick={() => router.push("/")}
                    className="flex items-center gap-3 hover:opacity-80 transition-opacity"
                >
                    <ChevronLeft className="w-4 h-4 text-zinc-400" />
                    <Image src="/OnchorAI-logo.png" alt="Onchor.ai Logo" width={32} height={32} className="rounded-lg" />
                    <span className="font-semibold text-sm tracking-tight text-zinc-100">Onchor.ai</span>
                </button>
                <div className="flex items-center gap-2">
                    <Terminal className="w-4 h-4 text-[#0DFC67]" />
                    <span className="font-medium text-sm text-zinc-400">Audit History</span>
                </div>
            </nav>

            <main className="relative z-10 max-w-4xl mx-auto px-6 pt-12 pb-24">

                {/* Header */}
                <div className="mb-10">
                    <h1 className="text-4xl font-bold tracking-tight mb-4 text-white">Audit History</h1>
                    <p className="text-zinc-400 leading-relaxed">
                        Read-only view of audits run from the CLI.
                        Run <span className="text-zinc-300">Onchor-ai audit ./src/</span> to add a new entry.
                    </p>
                </div>

                {/* Loading */}
                {loading && (
                    <div className="flex items-center gap-3 py-12">
                        <div className="w-1.5 h-1.5 rounded-full bg-[#0DFC67] animate-pulse" />
                        <span className="text-zinc-400 leading-relaxed">Loading audits...</span>
                    </div>
                )}

                {/* Empty */}
                {!loading && audits.length === 0 && (
                    <div className="border border-white/5 bg-zinc-900/30 p-12 text-center rounded-[2rem]">
                        <Terminal className="w-8 h-8 text-zinc-700 mx-auto mb-4" />
                        <p className="text-sm text-zinc-500 mb-2">No audits yet.</p>
                        <p className="text-xs text-zinc-700">
                            Run <span className="text-zinc-500">Onchor-ai audit ./your-contracts/</span> to get started.
                        </p>
                    </div>
                )}

                {/* Table header */}
                {!loading && audits.length > 0 && (
                    <>
                        <div className="grid grid-cols-12 gap-4 px-4 pb-2 border-b border-white/5 mb-1">
                            <div className="col-span-4 text-sm font-medium text-zinc-500">Target</div>
                            <div className="col-span-2 text-sm font-medium text-zinc-500">Verdict</div>
                            <div className="col-span-2 text-sm font-medium text-zinc-500">Risk</div>
                            <div className="col-span-2 text-sm font-medium text-zinc-500">Findings</div>
                            <div className="col-span-2 text-sm font-medium text-zinc-500">Date</div>
                        </div>

                        <div className="space-y-px">
                            {audits.map((audit) => {
                                const vc = VERDICT_CONFIG[audit.verdict];
                                const VIcon = vc.icon;
                                const date = new Date(audit.created_at);
                                const dateStr = date.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });

                                return (
                                    <button
                                        key={audit.id}
                                        onClick={() => router.push(`/audit/${audit.id}`)}
                                        className="w-full grid grid-cols-12 gap-4 items-center px-6 py-5 bg-zinc-900/30 border border-white/5 rounded-2xl mb-3 hover:border-white/10 hover:bg-zinc-900/50 transition-all duration-200 text-left group"
                                    >
                                        {/* Target */}
                                        <div className="col-span-4 flex items-center gap-3 min-w-0">
                                            <TargetLabel target={audit.target} />
                                            {audit.ens_cert && (
                                                <span className="text-xs bg-[#0DFC6715] text-[#0DFC67] px-1.5 py-0.5 border border-[#0DFC6730] shrink-0">
                                                    ENS
                                                </span>
                                            )}
                                        </div>

                                        {/* Verdict */}
                                        <div className="col-span-2">
                                            <div className={`inline-flex items-center gap-1.5 px-2 py-1 border text-xs font-medium ${vc.bg} ${vc.color}`}>
                                                <VIcon className="w-3 h-3" />
                                                {vc.label}
                                            </div>
                                        </div>

                                        {/* Risk bar */}
                                        <div className="col-span-2">
                                            <RiskBar score={audit.risk_score} />
                                        </div>

                                        {/* Findings */}
                                        <div className="col-span-2 flex items-center gap-2">
                                            {audit.high_count > 0 && (
                                                <span className="text-xs text-red-400">{audit.high_count}H</span>
                                            )}
                                            {audit.medium_count > 0 && (
                                                <span className="text-xs text-yellow-400">{audit.medium_count}M</span>
                                            )}
                                            {audit.high_count === 0 && audit.medium_count === 0 && (
                                                <span className="text-xs text-zinc-600">—</span>
                                            )}
                                            {audit.price_paid && (
                                                <span className="text-xs text-zinc-600 ml-1">{audit.price_paid} USDC</span>
                                            )}
                                        </div>

                                        {/* Date + arrow */}
                                        <div className="col-span-2 flex items-center justify-between">
                                            <span className="text-xs text-zinc-600">{dateStr}</span>
                                            <ExternalLink className="w-3 h-3 text-zinc-700 group-hover:text-zinc-500 transition-colors" />
                                        </div>
                                    </button>
                                );
                            })}
                        </div>

                        {/* Footer stats */}
                        <div className="mt-6 pt-4 border-t border-white/5 flex items-center gap-8">
                            <div>
                                <span className="text-xs text-zinc-600">Total audits </span>
                                <span className="text-xs text-zinc-400">{audits.length}</span>
                            </div>
                            <div>
                                <span className="text-xs text-zinc-600">HIGH findings </span>
                                <span className="text-xs text-red-400">
                                    {audits.reduce((acc, a) => acc + a.high_count, 0)}
                                </span>
                            </div>
                            <div>
                                <span className="text-xs text-zinc-600">USDC spent </span>
                                <span className="text-xs text-[#0DFC67]">
                                    {audits.reduce((acc, a) => acc + (a.price_paid ?? 0), 0).toFixed(2)}
                                </span>
                            </div>
                            <div>
                                <span className="text-xs text-zinc-600">Certified </span>
                                <span className="text-xs text-[#0DFC67]">
                                    {audits.filter((a) => a.verdict === "CERTIFIED").length}
                                </span>
                            </div>
                        </div>
                    </>
                )}

            </main>
        </div>
    );
}