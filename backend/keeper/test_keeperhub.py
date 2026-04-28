"""
Manual test of the two KeeperHub integrations.

Usage (from backend/):
    python -m keeper.test_keeperhub check    # isAnchored() only (no write)
    python -m keeper.test_keeperhub direct   # Direct Execution API (Phase 5)
    python -m keeper.test_keeperhub mcp      # Webhook anchor (Phase 4 tool 7)
    python -m keeper.test_keeperhub all      # all of the above
"""

import asyncio
import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

# Fictional test hashes — will be anchored on Sepolia the first time,
# then "already_anchored" on subsequent runs.
TEST_PATTERN_HASH = "0xdeadbeef00000000000000000000000000000000000000000000000000000001"
TEST_ROOT_HASH_0G = "0xcafebabe00000000000000000000000000000000000000000000000000000002"


async def test_check():
    print("\n─── isAnchored() check (read-only) ──────────────────────")
    from keeper.direct_api import is_already_anchored
    result = await is_already_anchored(TEST_PATTERN_HASH)
    print(f"  pattern {TEST_PATTERN_HASH[:12]}... already anchored: {result}")


async def test_direct_api():
    print("\n─── Direct Execution API (Phase 5) ──────────────────────")
    from keeper.direct_api import anchor_contribution

    print(f"  Submitting anchor via Direct Execution API...")
    tx = await anchor_contribution(TEST_PATTERN_HASH, TEST_ROOT_HASH_0G)

    if tx == "already_anchored":
        print(" Pattern already anchored onchain — nothing to do")
    else:
        print(f" tx_hash : {tx}")
        print(f" Etherscan : https://sepolia.etherscan.io/tx/{tx}")


async def test_mcp():
    """
    Tests anchor_finding_mcp().
    Uses webhook + poll, NOT the MCP SSE protocol
    (KeeperHub SSE returns 500 on /mcp initialize).
    """
    print("\n─── MCP Tools — webhook anchor (Phase 4 tool 7) ─────────")
    from keeper.mcp_tools import anchor_finding_mcp

    print(f"  Anchoring via KeeperHub webhook...")
    tx = await anchor_finding_mcp(TEST_PATTERN_HASH, TEST_ROOT_HASH_0G)

    print(f"  tx_hash  : {tx}")
    print(f"  Etherscan  : https://sepolia.etherscan.io/tx/{tx}")


async def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"

    if mode in ("check", "all"):
        try:
            await test_check()
        except Exception as e:
            print(f"  Check failed: {e}")

    if mode in ("direct", "all"):
        try:
            await test_direct_api()
        except Exception as e:
            print(f"  Direct API failed: {e}")

    if mode in ("mcp", "all"):
        try:
            await test_mcp()
        except Exception as e:
            print(f" MCP failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())