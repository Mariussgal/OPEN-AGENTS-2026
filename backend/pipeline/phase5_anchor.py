import os
import hashlib
import logging
from typing import List, Dict
from keeper.direct_api import anchor_contribution, poll_execution
from storage.zero_g_client import store_pattern, pattern_storage_payload

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Phase5-Anchor")


async def run_phase5_anchor(findings: List[Dict]) -> List[Dict]:
    """
    Ancrage on-chain pour findings CONFIRMED / LIKELY ; rootHash 0G depuis store_pattern.
    """
    logger.info(f"🛡️ [Phase 5] Checking anchoring for {len(findings)} findings...")

    anchored_results = []

    for finding in findings:
        if finding.get("confidence") not in ["CONFIRMED", "LIKELY"]:
            continue

        if finding.get("tx_hash"):
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
            logger.error(f"  0G store_pattern failed — skip anchor: {e}")
            anchored_results.append(finding)
            continue

        try:
            placeholder_addr = os.getenv("RECEIVER_ADDRESS", "0x" + "0" * 40)
            exec_id = await anchor_contribution(pattern_hash, root_hash_0g, placeholder_addr, amount_usdc=0.0)

            if exec_id:
                logger.info(f"  → Execution ID: {exec_id}. Waiting...")
                tx_hash = await poll_execution(exec_id)

                if tx_hash:
                    finding["tx_hash"] = tx_hash
                    logger.info(f"  Success — tx: {tx_hash}")
                else:
                    logger.warning(f"  Timeout polling {exec_id}")
            else:
                logger.error(f"  Anchor call failed for {finding['title']}")

        except Exception as e:
            logger.error(f"   Anchor error : {e}")

        anchored_results.append(finding)

    return anchored_results
