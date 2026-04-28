"""
The KeeperHub webhook uses a secret distinct from the REST API key.
We reuse direct_api.py (Direct Execution API) which already works —
identical interface for the agent, identical on-chain result.
"""

import logging
from keeper.direct_api import anchor_contribution, is_already_anchored

logger = logging.getLogger(__name__)


async def anchor_finding_mcp(pattern_hash: str, root_hash_0g: str) -> str:
    """
    Anchors a finding on-chain during the agent's reasoning.

    Args:
        pattern_hash  : SHA-256 of the normalized snippet (0x...)
        root_hash_0g  : 0G Storage Merkle root (0x...)

    Returns:
        Confirmed transactionHash, or "already_anchored"
    """
    if not pattern_hash.startswith("0x"):
        pattern_hash = "0x" + pattern_hash
    if not root_hash_0g.startswith("0x"):
        root_hash_0g = "0x" + root_hash_0g

    logger.info(f"[Agent tool 7] anchor_finding_mcp — {pattern_hash[:12]}...")

    tx_hash = await anchor_contribution(pattern_hash, root_hash_0g)

    if tx_hash == "already_anchored":
        logger.info("[Agent tool 7] Pattern already anchored — skip")
    else:
        logger.info(f"[Agent tool 7] Finding anchored — tx: {tx_hash}")

    return tx_hash