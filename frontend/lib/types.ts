// ─── Audit Input ─────────────────────────────────────────────────────────────

export type AuditTarget =
    | { kind: "address"; value: string }
    | { kind: "path"; value: string };

export type AuditMode = "paid" | "local" | "dev";

export interface AuditRequest {
    target: AuditTarget;
    mode: AuditMode;
}

// ─── Pipeline Phases ──────────────────────────────────────────────────────────

export type PhaseStatus = "pending" | "running" | "done" | "skipped" | "error";

export type PhaseId = 0 | 1 | 2 | 3 | 4 | 5 | 6;

export interface Phase {
    id: PhaseId;
    name: string;
    status: PhaseStatus;
    detail?: string;
}

// ─── SSE Stream Events ────────────────────────────────────────────────────────

export type StreamEventType =
    | "phase_start"
    | "phase_done"
    | "log"
    | "memory_hit"
    | "finding_suspected"
    | "finding_confirmed"
    | "anchor_tx"
    | "ens_minted"
    | "payment_confirmed"
    | "price_quote"
    | "done"
    | "error";

export interface StreamEvent {
    type: StreamEventType;
    phase?: PhaseId;
    message: string;
    data?: Record<string, unknown>;
    timestamp: number;
}

// ─── Findings ─────────────────────────────────────────────────────────────────

export type Severity = "HIGH" | "MEDIUM" | "LOW" | "INFO" | "INFORMATIONAL";
export type Confidence = "SUSPECTED" | "LIKELY" | "CONFIRMED";

export interface Finding {
    id: string; // e.g. "f-001"
    severity: Severity;
    confidence: Confidence;
    title: string;
    file: string;
    line?: number;
    description: string;
    recommendation: string;
    fix_sketch?: string;
    prior_audit_ref?: string; // Cognee memory ref
    onchain_proof?: string; // KeeperHub tx hash
    pattern_hash?: string;
    root_hash?: string; // 0G rootHash
}

// ─── Audit Report ─────────────────────────────────────────────────────────────

export type Verdict = "HIGH_RISK" | "MEDIUM_RISK" | "LOW_RISK" | "SAFE" | "CERTIFIED" | "FINDINGS_FOUND";

export interface MemoryHit {
    query: string;
    match: string; // e.g. "Euler Finance hack (2024-03-15)"
    amount?: string; // e.g. "$197M"
    confidence_boost: number; // +1 or +2
}

export interface OnchainMeta {
    anchor_registry?: string;
    network?: string;
    etherscan_base?: string;
    tx_proof?: string;
    keeperhub_executions?: string[];
}

export interface AuditReport {
    id: string;
    created_at: string;
    target: AuditTarget;
    mode: AuditMode;
    verdict: Verdict;
    risk_score: number; // 0–10
    files_analyzed: string[];
    upstream_detected?: string; // e.g. "Uniswap/v2-core"
    price_paid?: number; // USDC
    payment_tx?: string;
    findings: Finding[];
    memory_hits: MemoryHit[];
    onchain?: OnchainMeta;
    ens_cert?: string; // e.g. "vault-0x7f2e.certified.Onchor-ai.eth"
    report_hash?: string; // 0G rootHash
}

// ─── History ──────────────────────────────────────────────────────────────────

export interface AuditSummary {
    id: string;
    created_at: string;
    target: AuditTarget;
    verdict: Verdict;
    risk_score: number;
    high_count: number;
    medium_count: number;
    price_paid?: number;
    ens_cert?: string;
}

// ─── Payment ──────────────────────────────────────────────────────────────────

export interface PriceQuote {
    files_count: number;
    price_usdc: number;
    scope_label: string; // e.g. "<= 10 files"
}