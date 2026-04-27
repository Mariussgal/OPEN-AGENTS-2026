import type { AuditReport, AuditSummary, AuditRequest, PriceQuote, StreamEvent } from "./types";
import { MOCK_EULER_REPORT, MOCK_HISTORY, MOCK_STREAM_EVENTS } from "./mock-data";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const IS_MOCK = process.env.NEXT_PUBLIC_USE_MOCK === "true" || !process.env.NEXT_PUBLIC_API_URL;

// ─── Helper ───────────────────────────────────────────────────────────────────

function sleep(ms: number) {
    return new Promise((resolve) => setTimeout(resolve, ms));
}

// ─── Price Quote ──────────────────────────────────────────────────────────────

export async function getPriceQuote(target: string): Promise<PriceQuote> {
    if (IS_MOCK) {
        await sleep(400);
        const isAddress = target.startsWith("0x") && target.length === 42;
        return {
            files_count: isAddress ? 1 : 4,
            price_usdc: isAddress ? 0.5 : 1.0,
            scope_label: isAddress ? "≤ 3 fichiers" : "≤ 10 fichiers",
        };
    }

    const res = await fetch(`${API_BASE}/audit/quote?target=${encodeURIComponent(target)}`);
    if (!res.ok) throw new Error("Failed to get price quote");
    return res.json();
}

// ─── Audit History ────────────────────────────────────────────────────────────

export async function getAuditHistory(): Promise<AuditSummary[]> {
    if (IS_MOCK) {
        await sleep(300);
        return MOCK_HISTORY;
    }

    const res = await fetch(`${API_BASE}/audits`);
    if (!res.ok) throw new Error("Failed to fetch audit history");
    return res.json();
}

// ─── Audit Report ─────────────────────────────────────────────────────────────

export async function getAuditReport(id: string): Promise<AuditReport> {
    if (IS_MOCK) {
        await sleep(200);
        // Always return the Euler demo report for any id in mock mode
        return { ...MOCK_EULER_REPORT, id };
    }

    const res = await fetch(`${API_BASE}/audits/${id}`);
    if (!res.ok) throw new Error("Failed to fetch audit report");
    return res.json();
}

// ─── Streaming Audit ──────────────────────────────────────────────────────────
// In production: connects to FastAPI SSE endpoint
// In mock: replays MOCK_STREAM_EVENTS with realistic timing

export function streamAudit(
    request: AuditRequest,
    onEvent: (event: StreamEvent) => void,
    onDone: (reportId: string) => void,
    onError: (error: string) => void
): () => void {
    if (IS_MOCK) {
        let cancelled = false;
        let timeoutIds: ReturnType<typeof setTimeout>[] = [];

        MOCK_STREAM_EVENTS.forEach((event) => {
            const tid = setTimeout(() => {
                if (!cancelled) {
                    onEvent({ ...event, timestamp: Date.now() });
                    if (event.type === "done" && event.data?.report_id) {
                        onDone(event.data.report_id as string);
                    }
                }
            }, event.timestamp);
            timeoutIds.push(tid);
        });

        return () => {
            cancelled = true;
            timeoutIds.forEach(clearTimeout);
        };
    }

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
    if (IS_MOCK) {
        return {
            address: "0x4DB6Bf931e0AC52E6a35601da70aAB3fF26657C4",
            balance_usdc: 4.25,
            network: "ETH Sepolia",
        };
    }
    const res = await fetch(`${API_BASE}/wallet`);
    if (!res.ok) throw new Error("Failed to fetch wallet info");
    return res.json();
}