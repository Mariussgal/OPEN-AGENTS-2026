import sys
import os
import asyncio

# CRITICAL: This part must be AT THE TOP before importing your modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Now we can import your modules
from pipeline.phase5_anchor import run_phase5_anchor

async def test_just_anchor():
    # Mock finding
    mock_findings = [
        {
            "severity": "HIGH",
            "confidence": "CONFIRMED",
            "title": "Reentrancy in withdraw()",
            "reason": "External call before state update in EulerVault.",
            "file": "EulerVault.sol"
        }
    ]

    print("Isolated test of Phase 5...")
    results = await run_phase5_anchor(mock_findings)

    for r in results:
        if "tx_hash" in r:
            print(f"Success! Finding anchored on-chain.")
            print(f"Sepolia Hash: {r['tx_hash']}")
        else:
            print(f"Anchoring failed (check your logs).")

if __name__ == "__main__":
    asyncio.run(test_just_anchor())