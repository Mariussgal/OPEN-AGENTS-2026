# backend/keeper/mcp_tools.py
import logging
from keeper.hub_anchor import keeperhub_anchor_registry
from storage.zero_g_client import (
    normalize_pattern_hash,
    pattern_storage_payload,
    store_pattern,
)

logger = logging.getLogger(__name__)


async def anchor_finding_mcp(
    pattern_hash: str,
    root_hash_0g: str | None = None,
    *,
    title: str = "",
    reason: str = "",
    severity: str = "",
    confidence: str = "",
    file: str = "",
    line: str | int | None = None,
    contributor_address: str | None = None,  # reserved for future rewards
) -> str:
    ph = normalize_pattern_hash(pattern_hash)

    rh_raw = (root_hash_0g or "").strip()
    if rh_raw:
        rh = rh_raw if rh_raw.startswith("0x") else ("0x" + rh_raw if len(rh_raw) == 64 else rh_raw)
    else:
        payload = pattern_storage_payload(
            ph,
            title=title,
            reason=reason,
            severity=severity or None,
            confidence=confidence or None,
            file=file or None,
            line=line,
        )
        try:
            rh = store_pattern(payload)
        except Exception as e:
            logger.exception("[anchor_finding_mcp] store_pattern")
            return f"0G storage error: {e}"

    logger.info(f"[anchor_finding_mcp] pattern={ph[:16]}... root={rh[:16]}...")

    kh = await keeperhub_anchor_registry(ph, rh)

    if kh.get("skipped"):
        return "0G OK — KeeperHub skipped (set KEEPERHUB_API_KEY + ANCHOR_REGISTRY_ADDRESS for chain)"

    if kh.get("error"):
        return f"KeeperHub error: {kh['error']}"

    tx = kh.get("tx_hash")
    exe = kh.get("execution_id")
    return f"Anchored — tx: {tx or 'pending'} | executionId: {exe}"
