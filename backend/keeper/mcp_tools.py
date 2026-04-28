# backend/keeper/mcp_tools.py
import logging
from keeper.direct_api import anchor_contribution
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
    contributor_address: str | None = None,
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

    tx_hash = await anchor_contribution(ph, rh, contributor_address or "0x" + "0" * 40, amount_usdc=0.0)

    if tx_hash == "payment_failed":
        logger.error("payment_failed")
    elif tx_hash == "already_anchored":
        logger.info("already_anchored")
    else:
        logger.info(f"result: {tx_hash}")

    return tx_hash
