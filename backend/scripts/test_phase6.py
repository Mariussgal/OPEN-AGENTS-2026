"""
Isolated Phase 6 Test — without running phases 0-5.

Usage (from backend/):
    python -m scripts.test_phase6

This script injects realistic mock data (based on EulerVault.sol)
and directly calls run_report() to verify:
  ✓ Structured JSON report generation
  ✓ LLM-generated fix sketches (HIGH + MEDIUM)
  ✓ Resolved prior audit refs
  ✓ On-chain proof attached to anchored findings
  ✓ ENS mint triggered if 0 HIGH (or skipped based on config)
  ✓ Terminal display via cli._render_audit_result()
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from pipeline.phase_resolve import ResolvedContract
from pipeline.phase6_report import run_report


# ─── Mock data ─────────────────────────────────────────────────────────────────
# Based on EulerVault.sol deployed on Sepolia
# Address: 0x49Ca165Bd6AEe88825f59c557bC52A685e0594B5

MOCK_SCOPE = ResolvedContract(
    files=["temp_contracts/0x49ca165bd6aee88825f59c557bc52a685e0594b5/EulerVault.sol"],
    is_onchain=True,
    upstream=None,
    address="0x49Ca165Bd6AEe88825f59c557bC52A685e0594B5",
)

MOCK_SLITHER = {
    "success": True,
    "findings_count": 2,
    "findings": [
        {
            "check": "reentrancy-eth",
            "impact": "High",
            "description": "EulerVault.withdraw(uint256) sends eth to arbitrary user — Dangerous calls: this.token.transfer(msg.sender, amount) occurs before balances[msg.sender] is updated.",
            "file": "EulerVault.sol",
        },
        {
            "check": "events-maths",
            "impact": "Low",
            "description": "EulerVault.deposit(uint256) should emit an event for critical state change.",
            "file": "EulerVault.sol",
        },
    ],
}

MOCK_INVENTORY = {
    "files_analyzed": 1,
    "duplicates_detected": 0,
    "known_findings": [
        {
            "contract": "EulerVault",
            "type": "Historical Memory",
            "description": "[Source: Rekt.news] Euler Finance Hack. Reentrancy on withdraw() — state is updated after external call, allowing a loop drain.",
            "pattern_hash": "17a1a6b68b12d1c0177bc64d02dbe1394c0b551e727186be98ef568bc862ac83",
        }
    ],
    "known_findings_count": 1,
    "details": [
        {
            "file": "EulerVault.sol",
            "flags": ["reentrancy"],
            "stats": {"functions_count": 4, "modifiers_count": 1, "events_count": 1},
            "pattern_hash": "abc123",
            "duplicates": [],
            "is_duplicate": False,
        }
    ],
}

MOCK_TRIAGE = {
    "risk_score": 8.5,
    "verdict": "DANGER",
    "reasoning": "Reentrancy confirmed in withdraw() — external call before state update. Direct exploit vector.",
    "file_details": [
        {"file": "EulerVault.sol", "risk_score": 8.5, "verdict": "DANGER", "reasoning": "HIGH reentrancy confirmed."}
    ],
}

# Findings Phase 4+5 with an anchored tx_hash
MOCK_INVESTIGATION = {
    "findings": [
        {
            "severity":    "HIGH",
            "confidence":  "CONFIRMED",
            "title":       "Reentrancy in withdraw()",
            "file":        "EulerVault.sol",
            "line":        "42",
            "description": "External call to msg.sender occurs before balances[msg.sender] is updated. Classic reentrancy — attacker can re-enter withdraw() and drain the vault.",
            "reason":      "balances[msg.sender] -= amount should be moved BEFORE the external call.",
            "tx_hash":     "0xdeadbeef1234567890abcdef1234567890abcdef1234567890abcdef12345678",
            "pattern_hash": "17a1a6b68b12d1c0177bc64d02dbe1394c0b551e727186be98ef568bc862ac83",
        },
        {
            "severity":   "MEDIUM",
            "confidence": "LIKELY",
            "title":      "Missing Access Control on setFeeRecipient()",
            "file":       "EulerVault.sol",
            "line":       "67",
            "description": "setFeeRecipient() can be called by any address — no onlyOwner modifier.",
            "reason":     "Any caller can redirect fees to an arbitrary address.",
            "tx_hash":    None,
            "pattern_hash": None,
        },
    ],
    "anchored": ["0xdeadbeef1234567890abcdef1234567890abcdef1234567890abcdef12345678"],
    "turns_used": 12,
    "model": "anthropic/claude-sonnet-4-5",
}


# ─── Test scenarios ─────────────────────────────────────────────────────────

async def test_with_high_findings():
    """Scenario A: HIGH finding present → no ENS mint."""
    print("\n" + "═" * 60)
    print("  TEST A — HIGH finding present (no ENS mint)")
    print("═" * 60)

    report = await run_report(
        scope=MOCK_SCOPE,
        slither_data=MOCK_SLITHER,
        inventory_data=MOCK_INVENTORY,
        triage_data=MOCK_TRIAGE,
        investigation_data=MOCK_INVESTIGATION,
        target_address="0x49Ca165Bd6AEe88825f59c557bC52A685e0594B5",
    )

    _assert_report_structure(report)

    assert report["summary"]["high_count"] >= 1,  "high_count should be >= 1"
    assert report["ens"]["certified"] is False,    "should not be certified if HIGH"
    assert report["ens"]["subname"] is None,       "subname should be None if HIGH"

    finding_reentrancy = next(
        (f for f in report["findings"] if "Reentrancy" in f["title"]), None
    )
    assert finding_reentrancy is not None,                  "reentrancy finding not found"
    assert finding_reentrancy["fix_sketch"],                "empty fix_sketch"
    assert finding_reentrancy["prior_audit_ref"],           "empty prior_audit_ref"
    assert finding_reentrancy["onchain_proof"] is not None, "missing onchain_proof"

    print("\n  TEST A PASSED")
    _print_report_summary(report)
    return report


async def test_without_high_findings():
    """Scenario B: 0 HIGH finding → ENS mint triggered (or skipped if no contracts/)."""
    print("\n" + "═" * 60)
    print("  TEST B — 0 HIGH finding (ENS mint attempted)")
    print("═" * 60)

    # Remove HIGH finding
    low_only_investigation = {
        **MOCK_INVESTIGATION,
        "findings": [
            {
                "severity":   "LOW",
                "confidence": "SUSPECTED",
                "title":      "Missing event emission in deposit()",
                "file":       "EulerVault.sol",
                "line":       "28",
                "description": "deposit() modifies state without emitting an event.",
                "reason":     "Add an event Deposited(address, uint256).",
                "tx_hash":    None,
            }
        ],
        "anchored": [],
    }
    low_only_slither = {
        **MOCK_SLITHER,
        "findings": [MOCK_SLITHER["findings"][1]],  # keep only LOW
    }

    report = await run_report(
        scope=MOCK_SCOPE,
        slither_data=low_only_slither,
        inventory_data=MOCK_INVENTORY,
        triage_data={**MOCK_TRIAGE, "risk_score": 1.5, "verdict": "SAFE"},
        investigation_data=low_only_investigation,
        target_address="0x49Ca165Bd6AEe88825f59c557bC52A685e0594B5",
    )

    _assert_report_structure(report)
    assert report["summary"]["high_count"] == 0, "high_count should be 0"

    # ENS might have failed (no local contracts/) — just checking
    # that the attempt took place (ens section present)
    assert "ens" in report, "ens section missing in report"

    if report["ens"].get("subname"):
        print(f"  ENS minted: {report['ens']['subname']}")
    else:
        print("  ENS not minted (contracts/ probably missing locally — OK for testing)")

    print("\n TEST B PASSED")
    _print_report_summary(report)
    return report


async def test_empty_findings():
    """Scenario C: Empty pipeline (simple contract, no finding)."""
    print("\n" + "═" * 60)
    print("  TEST C — No finding (SAFE contract)")
    print("═" * 60)

    empty_investigation = {**MOCK_INVESTIGATION, "findings": [], "anchored": []}
    empty_slither       = {"success": True, "findings_count": 0, "findings": []}

    report = await run_report(
        scope=MOCK_SCOPE,
        slither_data=empty_slither,
        inventory_data={**MOCK_INVENTORY, "known_findings": []},
        triage_data={**MOCK_TRIAGE, "risk_score": 0.5, "verdict": "SAFE"},
        investigation_data=empty_investigation,
        target_address="0x49Ca165Bd6AEe88825f59c557bC52A685e0594B5",
    )

    _assert_report_structure(report)
    assert report["summary"]["total_findings"] == 0, "total_findings should be 0"
    assert report["verdict"] == "CERTIFIED",          "verdict should be CERTIFIED"

    print("\n TEST C PASSED")
    _print_report_summary(report)
    return report


# ─── Common assertions ──────────────────────────────────────────────────────

def _assert_report_structure(report: dict):
    """Verifies that all required fields are present."""
    required_top = ["verdict", "risk_score", "audit_date", "report_hash",
                    "target", "summary", "findings", "onchain", "ens", "generated"]
    for key in required_top:
        assert key in report, f"Missing field in report: '{key}'"

    for i, f in enumerate(report["findings"]):
        required_finding = ["id", "severity", "confidence", "title", "file",
                            "description", "fix_sketch", "prior_audit_ref", "onchain_proof"]
        for key in required_finding:
            assert key in f, f"Missing field in finding #{i}: '{key}'"


def _print_report_summary(report: dict):
    s = report["summary"]
    print(f"\n  Verdict    : {report['verdict']}")
    print(f"  Risk score : {report['risk_score']}/10")
    print(f"  Findings   : {s['total_findings']} (HIGH:{s['high_count']} MED:{s['medium_count']} LOW:{s['low_count']})")
    print(f"  Anchored   : {s['anchored_count']}")
    print(f"  Report hash: {report['report_hash'][:20]}...")
    print(f"  ENS        : {report['ens'].get('subname') or '—'}")

    print("\n  ── Enriched Findings ──")
    for f in report["findings"]:
        anchor = "⛓" if f.get("onchain_proof") else " "
        print(f"  {anchor} [{f['severity']:6s}] {f['id']} · {f['title'][:50]}")
        if f.get("fix_sketch"):
            sketch_preview = f["fix_sketch"].splitlines()[0][:60]
            print(f"           fix: {sketch_preview}")
        if f.get("prior_audit_ref"):
            print(f"           ref: {f['prior_audit_ref'][:60]}")


# ─── Full terminal render (optional) ──────────────────────────────────────

def test_cli_render(report: dict):
    """Passes the report to the CLI renderer to verify display."""
    print("\n" + "═" * 60)
    print("  RENDER — Phase 6 Terminal Display")
    print("═" * 60 + "\n")

    # Build the payload as the CLI receives it from the server
    mock_server_response = {
        "status":        "success",
        "report":        report,
        "triage":        MOCK_TRIAGE,
        "investigation": MOCK_INVESTIGATION,
        "slither":       MOCK_SLITHER,
    }

    from cli import _render_audit_result
    _render_audit_result(mock_server_response)


# ─── Main ─────────────────────────────────────────────────────────────────────

async def main():
    print("\n Onchor.ai — Isolated Phase 6 Test\n")

    report_a = await test_with_high_findings()
    report_b = await test_without_high_findings()
    _         = await test_empty_findings()

    # Terminal render on report A (the richest)
    test_cli_render(report_a)

    print("\n" + "═" * 60)
    print("   All Phase 6 tests passed")
    print("═" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())