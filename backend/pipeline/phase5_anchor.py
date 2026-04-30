import asyncio
import os
import hashlib
import logging
from typing import List, Dict
from keeper.hub_anchor import (
    is_evm_tx_hash,
    get_anchor_tx_from_chain,
    keeperhub_anchor_registry,
)
from storage.zero_g_client import store_pattern, pattern_storage_payload

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Phase5-Anchor")


async def run_phase5_anchor(findings: List[Dict]) -> List[Dict]:
    """
    Ancrage : upload JSON sur 0G (rootHash réel), puis KeeperHub → AnchorRegistry si configuré.
    """
    logger.info(f"🛡️ [Phase 5] Checking anchoring for {len(findings)} findings...")

    anchored_results = []

    for finding in findings:
        if finding.get("confidence") not in ["CONFIRMED", "LIKELY"]:
            continue

        if finding.get("tx_hash") or finding.get("execution_id"):
            logger.info(f"Already anchored : {finding['title']}")
            anchored_results.append(finding)
            continue

        content_to_hash = f"{finding['title']}-{finding['reason']}"
        digest = hashlib.sha256(content_to_hash.encode()).hexdigest()
        pattern_hash = "0x" + digest

        logger.info(f"Anchoring : {finding['title']}...")

        try:
            payload = pattern_storage_payload(
                pattern_hash,
                title=finding.get("title", ""),
                reason=finding.get("reason", ""),
                severity=finding.get("severity"),
                confidence=finding.get("confidence"),
                file=finding.get("file"),
                line=finding.get("line"),
            )
            root_hash_0g = store_pattern(payload)
            finding["root_hash"] = root_hash_0g
            finding["pattern_hash"] = pattern_hash
            logger.info(f"  → 0G rootHash: {root_hash_0g}")
        except Exception as e:
            logger.error(f"  0G store_pattern failed — skip: {e}")
            anchored_results.append(finding)
            continue

        try:
            kh = await keeperhub_anchor_registry(pattern_hash, root_hash_0g)

            if kh.get("skipped"):
                logger.warning(
                    "  KeeperHub non configuré — JSON sur 0G uniquement "
                    "(fixe KEEPERHUB_API_KEY + ANCHOR_REGISTRY_ADDRESS)."
                )
            elif kh.get("error"):
                logger.error("  KeeperHub: %s", kh["error"])
                finding["keeperhub_error"] = kh["error"]
            elif kh.get("success"):
                exe = kh.get("execution_id")
                if exe:
                    finding["execution_id"] = str(exe)

                import asyncio
                logger.info(f"  ⏳ Attente confirmation Sepolia (~20s)...")
                await asyncio.sleep(20)
                tx = await get_anchor_tx_from_chain(pattern_hash)
                if tx:
                    finding["tx_hash"] = tx
                    logger.info(f"  ✓ tx onchain : {tx}")
                else:
                    await asyncio.sleep(20)
                    tx = await get_anchor_tx_from_chain(pattern_hash)
                    if tx:
                        finding["tx_hash"] = tx
                        logger.info(f"  ✓ tx onchain (retry) : {tx}")
                    else:
                        logger.warning(f"  ⚠ tx non encore minée — executionId conservé")

                proof = finding.get("tx_hash") or finding.get("execution_id")
                logger.info(f"  → KeeperHub OK — preuve: {proof}")

        except Exception as e:
            logger.error(f"   KeeperHub error : {e}")
            finding["keeperhub_error"] = str(e)

        anchored_results.append(finding)

    return anchored_results
