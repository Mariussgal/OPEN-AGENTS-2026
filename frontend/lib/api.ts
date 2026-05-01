import type { AuditReport, AuditSummary, AuditRequest, PriceQuote, StreamEvent } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ─── Price Quote ──────────────────────────────────────────────────────────────

export async function getPriceQuote(target: string): Promise<PriceQuote> {
    const res = await fetch(`${API_BASE}/audit/quote?target=${encodeURIComponent(target)}`);
    if (!res.ok) throw new Error("Failed to get price quote");
    return res.json();
}

// ─── Audit History ────────────────────────────────────────────────────────────

export async function getAuditHistory(): Promise<AuditSummary[]> {
    const res = await fetch(`${API_BASE}/audits`);
    if (!res.ok) throw new Error("Failed to fetch audit history");
    return res.json();
}

// ─── Audit Report ─────────────────────────────────────────────────────────────

export async function getAuditReport(id: string): Promise<AuditReport> {
    const res = await fetch(`${API_BASE}/audits/${id}`);
    if (!res.ok) throw new Error("Failed to fetch audit report");
    return res.json();
}

// ─── Streaming Audit ──────────────────────────────────────────────────────────
// In production: connects to FastAPI SSE endpoint

export function streamAudit(
    request: AuditRequest,
    onEvent: (event: StreamEvent) => void,
    onDone: (reportId: string) => void,
    onError: (error: string) => void
): () => void {
    // ── Real SSE connection ──────────────────────────────────────────────────
    const params = new URLSearchParams({
        mode: request.mode,
        ...(request.target.kind === "address"
            ? { address: request.target.value }
            : { path: request.target.value }),
    });

    const es = new EventSource(`${API_BASE}/audit/stream?${params}`);

    es.onmessage = (e) => {
        try {
            const event: StreamEvent = JSON.parse(e.data);
            onEvent(event);
            if (event.type === "done" && event.data?.report_id) {
                onDone(event.data.report_id as string);
                es.close();
            }
            if (event.type === "error") {
                onError(event.message);
                es.close();
            }
        } catch {
            onError("Failed to parse stream event");
        }
    };

    es.onerror = () => {
        onError("Stream connection failed");
        es.close();
    };

    return () => es.close();
}

// ─── Export Report ────────────────────────────────────────────────────────────

export function downloadReportJson(report: AuditReport) {
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `Onchor-ai-report-${report.id}.json`;
    a.click();
    URL.revokeObjectURL(url);
}

export async function getWalletInfo() {
    const res = await fetch(`${API_BASE}/wallet`);
    if (!res.ok) throw new Error("Failed to fetch wallet info");
    return res.json();
}

export async function getMemoryStats() {
    const res = await fetch(`${API_BASE}/memory`);
    if (!res.ok) throw new Error("Failed to fetch memory stats");
    return res.json();
}