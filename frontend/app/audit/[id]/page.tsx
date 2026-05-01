"use client";

import Image from "next/image";
import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import {
    ChevronLeft, Terminal, Shield, AlertTriangle, AlertCircle,
    Info, ExternalLink, Copy, Check, Database, Link, FileCode
} from "lucide-react";
import { getAuditReport, downloadReportJson } from "@/lib/api";
import type { AuditReport, Finding, Severity, Verdict } from "@/lib/types";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function useCopy(text: string) {
    const [copied, setCopied] = useState(false);
    function copy() {
        navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    }
    return { copied, copy };
}

const SEVERITY_CONFIG: Record<Severity, { color: string; bg: string; border: string; label: string }> = {
    HIGH: { color: "text-red-400", bg: "bg-red-400/10", border: "border-red-400/30", label: "HIGH" },
    MEDIUM: { color: "text-yellow-400", bg: "bg-yellow-400/10", border: "border-yellow-400/30", label: "MEDIUM" },
    LOW: { color: "text-blue-400", bg: "bg-blue-400/10", border: "border-blue-400/30", label: "LOW" },
    INFO: { color: "text-zinc-400", bg: "bg-zinc-400/10", border: "border-zinc-400/30", label: "INFO" },
};

const VERDICT_CONFIG: Record<Verdict, { label: string; color: string; icon: React.ElementType }> = {
    HIGH_RISK: { label: "HIGH RISK", color: "text-red-400", icon: AlertTriangle },
    MEDIUM_RISK: { label: "MEDIUM RISK", color: "text-yellow-400", icon: AlertCircle },
    LOW_RISK: { label: "LOW RISK", color: "text-blue-400", icon: Info },
    SAFE: { label: "SAFE", color: "text-[#0DFC67]", icon: Shield },
    CERTIFIED: { label: "CERTIFIED", color: "text-[#0DFC67]", icon: Shield },
};

function shortHash(hash: string) {
    return `${hash.slice(0, 8)}...${hash.slice(-6)}`;
}

// ─── Finding card ─────────────────────────────────────────────────────────────

function FindingCard({ finding }: { finding: Finding }) {
    const [expanded, setExpanded] = useState(false);
    const sc = SEVERITY_CONFIG[finding.severity];
    const { copied, copy } = useCopy(finding.onchain_proof ?? "");

    return (
        <div className={`border ${sc.border} bg-zinc-900/30 rounded-2xl overflow-hidden mb-3`}>
            {/* Header */}
            <button
                onClick={() => setExpanded(!expanded)}
                className="w-full flex items-start gap-4 p-4 text-left hover:bg-white/[0.02] transition-colors"
            >
                <div className={`shrink-0 mt-0.5 px-2 py-0.5 text-xs font-medium border ${sc.bg} ${sc.border} ${sc.color}`}>
                    {sc.label}
                </div>
                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                        <span className="text-sm text-zinc-200">{finding.title}</span>
                        <span className={`text-xs px-1.5 py-0.5 border ${finding.confidence === "CONFIRMED"
                                ? "text-[#0DFC67] border-[#0DFC6730] bg-[#0DFC6710]"
                                : finding.confidence === "LIKELY"
                                    ? "text-yellow-400 border-yellow-400/30 bg-yellow-400/10"
                                    : "text-zinc-500 border-zinc-700 bg-zinc-800"
                            }`}>
                            {finding.confidence}
                        </span>
                    </div>
                    <div className="flex items-center gap-3">
                        <span className="text-xs text-zinc-600">
                            {finding.file}{finding.line ? `:${finding.line}` : ""}
                        </span>
                        {finding.onchain_proof && (
                            <span className="text-xs text-[#0DFC67]">✓ anchored</span>
                        )}
                    </div>
                </div>
                <span className="text-xs text-zinc-600 shrink-0 mt-1">
                    {expanded ? "▲" : "▼"}
                </span>
            </button>

            {/* Expanded */}
            {expanded && (
                <div className="border-t border-white/5 divide-y divide-white/5 bg-zinc-900/40">

                    {/* Description */}
                    <div className="p-4">
                        <div className="text-xs text-zinc-500 font-medium mb-2">Description</div>
                        <p className="text-xs text-zinc-300 leading-relaxed">{finding.description}</p>
                    </div>

                    {/* Prior audit ref (memory hit) */}
                    {finding.prior_audit_ref && (
                        <div className="p-4 bg-[#0DFC6708]">
                            <div className="text-xs text-zinc-500 font-medium mb-2">Memory hit</div>
                            <div className="flex items-start gap-2">
                                <Database className="w-3.5 h-3.5 text-cyan-400 shrink-0 mt-0.5" />
                                <span className="text-xs text-cyan-400">{finding.prior_audit_ref}</span>
                            </div>
                        </div>
                    )}

                    {/* Fix sketch */}
                    {finding.fix_sketch && (
                        <div className="p-4">
                            <div className="text-xs text-zinc-500 font-medium mb-3">Fix</div>
                            <div className="bg-zinc-900/50 border border-white/5 p-4 overflow-x-auto w-full">
                                <pre className="text-xs text-zinc-300 leading-relaxed whitespace-pre w-max">
                                    {finding.fix_sketch}
                                </pre>
                            </div>
                        </div>
                    )}

                    {/* Onchain proof */}
                    {finding.onchain_proof && (
                        <div className="p-4">
                            <div className="text-xs text-zinc-500 font-medium mb-2">Onchain proof</div>
                            <div className="flex items-center gap-3">
                                <Link className="w-3.5 h-3.5 text-[#0DFC67] shrink-0" />
                                <span className="text-xs text-zinc-400">{shortHash(finding.onchain_proof)}</span>
                                <button onClick={copy} className="text-zinc-600 hover:text-zinc-400 transition-colors">
                                    {copied ? <Check className="w-3 h-3 text-[#0DFC67]" /> : <Copy className="w-3 h-3" />}
                                </button>
                                <a
                                    href={`https://sepolia.basescan.org/tx/${finding.onchain_proof}`}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="text-xs text-[#0DFC67] hover:text-[#0DFC67] transition-colors flex items-center gap-1"
                                >
                                    Basescan <ExternalLink className="w-3 h-3" />
                                </a>
                            </div>
                        </div>
                    )}

                </div>
            )}
        </div>
    );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function AuditDetailPage() {
    const router = useRouter();
    const params = useParams();
    const id = params.id as string;

    const [report, setReport] = useState<AuditReport | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        getAuditReport(id)
            .then(setReport)
            .finally(() => setLoading(false));
    }, [id]);

    if (loading) {
        return (
            <div className="min-h-screen bg-[#0a0a0a] flex items-center justify-center">
                <div className="flex items-center gap-3">
                    <div className="w-1.5 h-1.5 rounded-full bg-[#0DFC67] animate-pulse" />
                    <span className="text-xs text-zinc-500">Loading report...</span>
                </div>
            </div>
        );
    }

    if (!report) {
        return (
            <div className="min-h-screen bg-[#0a0a0a] flex items-center justify-center">
                <div className="text-center">
                    <p className="text-sm text-zinc-500 mb-2">Report not found.</p>
                    <button onClick={() => router.push("/history")} className="text-xs text-[#0DFC67] hover:text-[#0DFC67] transition-colors">
                        ← Back to history
                    </button>
                </div>
            </div>
        );
    }

    const vc = VERDICT_CONFIG[report.verdict];
    const VIcon = vc.icon;
    const highFindings = report.findings.filter(f => f.severity === "HIGH");
    const medFindings = report.findings.filter(f => f.severity === "MEDIUM");
    const lowFindings = report.findings.filter(f => f.severity === "LOW");
    const infoFindings = report.findings.filter(
        f => f.severity === "INFO" || f.severity === "INFORMATIONAL"
    );
    const riskColor = report.risk_score >= 7 ? "#ff4444" : report.risk_score >= 4 ? "#f59e0b" : "#0DFC67";
    const date = new Date(report.created_at).toLocaleDateString("en-GB", {
        day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit"
    });

    return (
        <div className="min-h-screen bg-[#0a0a0a] text-zinc-100 relative selection:bg-white/20 font-sans">

            {/* Subtle modern background blur */}
            <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full max-w-3xl h-[400px] bg-white opacity-[0.02] rounded-[100%] blur-[100px] pointer-events-none" />

            {/* Nav */}
            <nav className="relative z-10 flex flex-col sm:flex-row items-center justify-between px-6 py-6 max-w-6xl mx-auto border-b border-white/5 gap-4 sm:gap-0">
                <button
                    onClick={() => router.push("/history")}
                    className="flex items-center gap-3 hover:opacity-80 transition-opacity"
                >
                    <ChevronLeft className="w-4 h-4 text-zinc-400 shrink-0" />
                    <Image src="/OnchorAI-logo.png" alt="Onchor.ai Logo" width={32} height={32} className="rounded-lg shrink-0" />
                    <span className="font-semibold text-sm tracking-tight text-zinc-100">Audit History</span>
                </button>
                <div className="flex items-center gap-2">
                    <Terminal className="w-4 h-4 text-[#0DFC67] shrink-0" />
                    <span className="font-medium text-sm text-zinc-400 text-center">Report</span>
                </div>
            </nav>

            <main className="relative z-10 max-w-4xl mx-auto px-6 pt-12 pb-24 space-y-10">

                {/* ── Verdict header ──────────────────────────────────────── */}
                <div className="border border-white/5 bg-zinc-900/30 p-8 rounded-[2rem]">
                    <div className="flex items-start justify-between gap-6 flex-wrap">

                        <div>
                            {/* Target */}
                            <div className="flex items-center gap-2 mb-3">
                                {report.target.kind === "address"
                                    ? <Link className="w-3.5 h-3.5 text-[#0DFC67]" />
                                    : <FileCode className="w-3.5 h-3.5 text-zinc-500" />
                                }
                                <span className="text-sm text-zinc-300">
                                    {report.target.kind === "address"
                                        ? report.target.value
                                        : report.target.value
                                    }
                                </span>
                                {report.target.kind === "address" && (
                                    <a
                                        href={`https://sepolia.basescan.org/address/${report.target.value}`}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="text-zinc-600 hover:text-[#0DFC67] transition-colors"
                                    >
                                        <ExternalLink className="w-3 h-3" />
                                    </a>
                                )}
                            </div>

                            {/* Verdict badge */}
                            <div className={`inline-flex items-center gap-2 text-lg font-bold mb-1 ${vc.color}`}>
                                <VIcon className="w-5 h-5" />
                                {vc.label}
                            </div>
                            <div className="text-xs text-zinc-600">{date}</div>
                        </div>

                        {/* Risk score */}
                        <div className="text-right">
                            <div className="text-5xl font-bold" style={{ color: riskColor }}>
                                {report.risk_score.toFixed(1)}
                            </div>
                            <div className="text-xs text-zinc-600">/ 10</div>
                        </div>

                    </div>

                    {/* Stats row */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-8">
                        {[
                            { label: "HIGH", value: highFindings.length, color: "text-red-400" },
                            { label: "MEDIUM", value: medFindings.length, color: "text-yellow-400" },
                            { label: "LOW", value: lowFindings.length, color: "text-blue-400" },
                            { label: "Memory hits", value: report.memory_hits.length, color: "text-cyan-400" },
                        ].map((s) => (
                            <div key={s.label} className="bg-zinc-900/40 border border-white/5 rounded-2xl px-6 py-5 text-center">
                                <div className={`text-xl font-bold ${s.color}`}>{s.value}</div>
                                <div className="text-xs text-zinc-600 font-medium">{s.label}</div>
                            </div>
                        ))}
                    </div>
                </div>

                {/* ── Memory hits ─────────────────────────────────────────── */}
                {report.memory_hits.length > 0 && (
                    <div>
                        <h2 className="text-xs text-zinc-500 font-medium mb-4">
                            Memory hits
                        </h2>
                        <div className="space-y-2">
                            {report.memory_hits.map((hit, i) => (
                                <div key={i} className="border border-white/5 bg-zinc-900/40 p-5 rounded-2xl flex items-start gap-3 mb-3">
                                    <Database className="w-3.5 h-3.5 text-cyan-400 shrink-0 mt-0.5" />
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-3 flex-wrap mb-1">
                                            <span className="text-xs text-cyan-400">{hit.match}</span>
                                            {hit.amount && (
                                                <span className="text-xs text-red-400 font-semibold">{hit.amount}</span>
                                            )}
                                            <span className="text-xs text-zinc-600 border border-zinc-700 px-1.5 py-0.5">
                                                +{hit.confidence_boost} confidence
                                            </span>
                                        </div>
                                        <div className="text-xs text-zinc-600">
                                            query: <span className="text-zinc-500">&quot;{hit.query}&quot;</span>
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* ── Findings ────────────────────────────────────────────── */}
                <div>
                    <h2 className="text-xs text-zinc-500 font-medium mb-4">
                        Findings ({report.findings.length})
                    </h2>

                    {report.findings.length === 0 ? (
                        <div className="border border-white/5 bg-zinc-900/30 p-8 text-center">
                            <Shield className="w-6 h-6 text-[#0DFC67] mx-auto mb-2" />
                            <p className="text-xs text-zinc-500">No findings. Contract looks clean.</p>
                        </div>
                    ) : (
                        <div className="space-y-2">
                            {[...highFindings, ...medFindings, ...lowFindings].map((finding) => (
                                <FindingCard key={finding.id} finding={finding} />
                            ))}
                            {infoFindings.length > 0 && (
                                <details className="mt-2">
                                    <summary className="text-xs text-zinc-500 cursor-pointer hover:text-zinc-400 py-2">
                                        {infoFindings.length} informational finding(s) — click to expand
                                    </summary>
                                    <div className="mt-2 space-y-2">
                                        {infoFindings.map((finding) => (
                                            <FindingCard key={finding.id} finding={finding} />
                                        ))}
                                    </div>
                                </details>
                            )}
                        </div>
                    )}
                </div>

                {(report as any).ens?.certified && (
                    <div className="border border-green-500/30 rounded-lg p-4 bg-green-500/5">
                        <div className="flex items-center gap-2 mb-2">
                            <span className="text-green-400 text-lg">🏅</span>
                            <span className="font-semibold text-green-400">CERTIFIED</span>
                        </div>
                        <p className="text-sm text-gray-300 font-mono">{(report as any).ens.subname}</p>
                        <div className="mt-2 flex gap-3 text-xs">
                            <a href={(report as any).ens.url} target="_blank" rel="noopener noreferrer" className="text-green-400 hover:underline">
                                ENS Sepolia ↗
                            </a>
                            <a href={`https://sepolia.etherscan.io/tx/${(report as any).ens.mint_tx}`} target="_blank" rel="noopener noreferrer" className="text-gray-400 hover:underline">
                                Mint tx ↗
                            </a>
                        </div>
                        <p className="text-xs text-gray-500 mt-1 font-mono">
                            report_hash: {(report as any).report?.report_hash}
                        </p>
                    </div>
                )}

                {/* ── Metadata ────────────────────────────────────────────── */}
                <div>
                    <h2 className="text-xs text-zinc-500 font-medium mb-4">Metadata</h2>
                    <div className="border border-white/5 bg-zinc-900/30 divide-y divide-white/5 rounded-2xl overflow-hidden">
                        {[
                            { label: "Audit ID", value: report.id },
                            { label: "Mode", value: report.mode },
                            { label: "Files analyzed", value: report.files_analyzed.join(", ") },
                            ...(report.upstream_detected ? [{ label: "Upstream detected", value: report.upstream_detected }] : []),
                            ...(report.payment_tx ? [{ label: "Payment tx", value: shortHash(report.payment_tx) }] : []),
                            ...(report.report_hash ? [{ label: "0G report hash", value: shortHash(report.report_hash) }] : []),
                        ].map((row) => (
                            <div key={row.label} className="grid grid-cols-1 md:grid-cols-3 px-4 py-3 gap-1 md:gap-0">
                                <span className="text-xs text-zinc-600">{row.label}</span>
                                <span className="md:col-span-2 text-xs text-zinc-400 break-all">{row.value}</span>
                            </div>
                        ))}
                    </div>
                </div>

                {/* ── Actions ─────────────────────────────────────────────── */}
                <div className="flex items-center gap-4 pt-2">
                    <button
                        onClick={() => downloadReportJson(report)}
                        className="text-sm bg-white text-black hover:bg-zinc-200 px-5 py-2.5 rounded-full font-medium transition-colors flex items-center gap-2"
                    >
                        Download JSON
                    </button>
                    {report.payment_tx && (
                        <a
                            href={`https://sepolia.basescan.org/tx/${report.payment_tx}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-xs text-[#0DFC67] hover:text-[#0DFC67] transition-colors flex items-center gap-1.5"
                        >
                            Onchain proof <ExternalLink className="w-3 h-3" />
                        </a>
                    )}
                </div>

            </main>
        </div>
    );
}