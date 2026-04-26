import type { AuditReport, AuditSummary, StreamEvent } from "./types";

// ─── EulerVault Demo Report ───────────────────────────────────────────────────
// Based on the real deployed contract: 0x49Ca165Bd6AEe88825f59c557bC52A685e0594B5

export const MOCK_EULER_REPORT: AuditReport = {
    id: "audit-euler-001",
    created_at: "2026-04-26T10:23:00Z",
    target: { kind: "address", value: "0x49Ca165Bd6AEe88825f59c557bC52A685e0594B5" },
    mode: "paid",
    verdict: "HIGH_RISK",
    risk_score: 8.4,
    files_analyzed: ["EulerVault.sol"],
    price_paid: 0.5,
    payment_tx: "0x8fa3c2e1d4b5a9f0e2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5",
    findings: [
        {
            id: "f-001",
            severity: "HIGH",
            confidence: "CONFIRMED",
            title: "Reentrancy in withdraw()",
            file: "EulerVault.sol",
            line: 142,
            description:
                "withdraw() calls external address before zeroing user balance. An attacker can re-enter the function and drain funds before the balance update takes effect.",
            recommendation: "Apply CEI pattern (Checks-Effects-Interactions): update state before external calls.",
            fix_sketch: `// ❌ Vulnerable\nfunction withdraw(uint256 amount) external {\n    (bool ok,) = msg.sender.call{value: amount}('');\n    balances[msg.sender] -= amount; // state updated AFTER call\n}\n\n// ✅ Fixed (CEI)\nfunction withdraw(uint256 amount) external {\n    balances[msg.sender] -= amount; // effect first\n    (bool ok,) = msg.sender.call{value: amount}(''); // then interact\n    require(ok, "Transfer failed");\n}`,
            prior_audit_ref: "Euler Finance hack (2024-03-15) — $197M",
            onchain_proof: "0x7f2e3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f",
            pattern_hash: "0xa3f8c2d1e4b5a9f0e2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4",
        },
        {
            id: "f-002",
            severity: "MEDIUM",
            confidence: "CONFIRMED",
            title: "Missing access control on setFeeRecipient()",
            file: "EulerVault.sol",
            line: 89,
            description:
                "setFeeRecipient() has no onlyOwner or access control modifier. Any address can redirect protocol fees to an arbitrary recipient.",
            recommendation: "Add onlyOwner modifier or equivalent access control.",
            fix_sketch: `// ❌ Vulnerable\nfunction setFeeRecipient(address recipient) external {\n    feeRecipient = recipient;\n}\n\n// ✅ Fixed\nfunction setFeeRecipient(address recipient) external onlyOwner {\n    feeRecipient = recipient;\n}`,
            onchain_proof: "0x3bc4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4",
            pattern_hash: "0xb4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5",
        },
        {
            id: "f-003",
            severity: "LOW",
            confidence: "LIKELY",
            title: "Unchecked return value on transfer()",
            file: "EulerVault.sol",
            line: 201,
            description:
                "The return value of ERC20 transfer() is not checked. Some non-standard tokens return false on failure instead of reverting.",
            recommendation: "Use OpenZeppelin's SafeERC20.safeTransfer() instead.",
            fix_sketch: `// ❌ Unchecked\ntoken.transfer(recipient, amount);\n\n// ✅ Safe\nusing SafeERC20 for IERC20;\ntoken.safeTransfer(recipient, amount);`,
        },
    ],
    memory_hits: [
        {
            query: "reentrancy external call before state update",
            match: "Euler Finance hack (2024-03-15) — $197M — reentrancy in epoch-based vault withdrawal",
            amount: "$197M",
            confidence_boost: 2,
        },
        {
            query: "missing access control setFeeRecipient",
            match: "Rekt.news: Uranium Finance (2021-04-28) — $50M — unprotected admin function",
            amount: "$50M",
            confidence_boost: 1,
        },
    ],
};

// ─── Mock History ─────────────────────────────────────────────────────────────

export const MOCK_HISTORY: AuditSummary[] = [
    {
        id: "audit-euler-001",
        created_at: "2026-04-26T10:23:00Z",
        target: { kind: "address", value: "0x49Ca165Bd6AEe88825f59c557bC52A685e0594B5" },
        verdict: "HIGH_RISK",
        risk_score: 8.4,
        high_count: 1,
        medium_count: 1,
        price_paid: 0.5,
    },
    {
        id: "audit-token-002",
        created_at: "2026-04-25T14:11:00Z",
        target: { kind: "path", value: "./src/Token.sol" },
        verdict: "CERTIFIED",
        risk_score: 1.2,
        high_count: 0,
        medium_count: 0,
        price_paid: 0.5,
        ens_cert: "token-0x8a3f.certified.Onkhor-ai.eth",
    },
    {
        id: "audit-router-003",
        created_at: "2026-04-24T09:45:00Z",
        target: { kind: "path", value: "./src/" },
        verdict: "MEDIUM_RISK",
        risk_score: 4.7,
        high_count: 0,
        medium_count: 3,
        price_paid: 1.0,
    },
];

// ─── Mock SSE Stream ──────────────────────────────────────────────────────────
// Simulates what the FastAPI backend would stream

export const MOCK_STREAM_EVENTS: StreamEvent[] = [
    { type: "payment_confirmed", message: "Paying 0.50 USDC for audit...", data: { tx: "0x8fa3..." }, timestamp: 0 },
    { type: "phase_start", phase: 0, message: "Resolving target...", timestamp: 300 },
    { type: "log", phase: 0, message: "1 file detected (EulerVault.sol)", timestamp: 600 },
    { type: "price_quote", message: "Audit price: 0.50 USDC (≤ 3 files)", data: { price: 0.5, files: 1 }, timestamp: 800 },
    { type: "phase_done", phase: 0, message: "Resolved — 1 file", timestamp: 1000 },
    { type: "phase_start", phase: 1, message: "Inventory...", timestamp: 1200 },
    { type: "log", phase: 1, message: "2 flags detected: unchecked, external-call", timestamp: 1600 },
    { type: "phase_done", phase: 1, message: "2 flags", timestamp: 1800 },
    { type: "phase_start", phase: 2, message: "Running Slither...", timestamp: 2000 },
    { type: "log", phase: 2, message: "3 findings (1 HIGH, 1 MED, 1 LOW)", timestamp: 2800 },
    { type: "phase_done", phase: 2, message: "3 findings", timestamp: 3000 },
    { type: "phase_start", phase: 3, message: "Triage — risk scoring...", timestamp: 3200 },
    { type: "log", phase: 3, message: "risk_score: 8.4 / 10 — proceeding to investigation", timestamp: 3800 },
    { type: "phase_done", phase: 3, message: "risk_score: 8.4", timestamp: 4000 },
    { type: "phase_start", phase: 4, message: "Investigating (adversarial mode)...", timestamp: 4200 },
    { type: "log", phase: 4, message: "> read_contract(EulerVault.sol, withdraw)", timestamp: 4600 },
    { type: "log", phase: 4, message: "> query_memory('reentrancy external call')", timestamp: 5200 },
    {
        type: "memory_hit",
        phase: 4,
        message: "Memory hit: Euler Finance hack (2024-03-15) — $197M",
        data: { match: "Euler Finance hack (2024-03-15)", amount: "$197M", boost: 2 },
        timestamp: 5600,
    },
    { type: "finding_suspected", phase: 4, message: "Finding SUSPECTED → CONFIRMED — Reentrancy in withdraw()", timestamp: 6000 },
    { type: "log", phase: 4, message: "Anchoring onchain...", timestamp: 6200 },
    {
        type: "anchor_tx",
        phase: 4,
        message: "✓ f-001 anchored → 0x7f2e... (KeeperHub)",
        data: { finding_id: "f-001", tx: "0x7f2e..." },
        timestamp: 6800,
    },
    { type: "log", phase: 4, message: "> read_contract(EulerVault.sol, setFeeRecipient)", timestamp: 7200 },
    { type: "log", phase: 4, message: "> query_memory('missing access control')", timestamp: 7600 },
    {
        type: "memory_hit",
        phase: 4,
        message: "Memory hit: Uranium Finance (2021-04-28) — $50M",
        data: { match: "Uranium Finance (2021-04-28)", amount: "$50M", boost: 1 },
        timestamp: 7900,
    },
    { type: "finding_confirmed", phase: 4, message: "Finding CONFIRMED — Missing access control on setFeeRecipient()", timestamp: 8200 },
    {
        type: "anchor_tx",
        phase: 4,
        message: "✓ f-002 anchored → 0x3bc4... (KeeperHub)",
        data: { finding_id: "f-002", tx: "0x3bc4..." },
        timestamp: 8700,
    },
    { type: "phase_done", phase: 4, message: "2 findings confirmed, 2 anchored", timestamp: 9000 },
    { type: "phase_start", phase: 5, message: "Verifying anchors...", timestamp: 9200 },
    { type: "phase_done", phase: 5, message: "2/2 anchors confirmed", timestamp: 9800 },
    { type: "phase_start", phase: 6, message: "Generating report...", timestamp: 10000 },
    { type: "log", phase: 6, message: "HIGH findings detected — skipping ENS certification", timestamp: 10400 },
    { type: "phase_done", phase: 6, message: "Report ready", timestamp: 10800 },
    {
        type: "done",
        message: "VERDICT: HIGH RISK (8.4/10)",
        data: { verdict: "HIGH_RISK", risk_score: 8.4, report_id: "audit-euler-001" },
        timestamp: 11000,
    },
];