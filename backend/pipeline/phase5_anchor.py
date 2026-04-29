import os
import hashlib
import logging
from typing import List, Dict
from keeper.hub_anchor import is_evm_tx_hash, keeperhub_anchor_registry
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
                tx = kh.get("tx_hash")
                exe = kh.get("execution_id")
                tid = tx if isinstance(tx, str) else (str(tx) if tx not in (None, "") else None)
                if tid and str(tid).lower() in ("pending", "none"):
                    tid = None
                if tid and is_evm_tx_hash(tid):
                    finding["tx_hash"] = tid.strip().lower()
                elif tid:
                    logger.warning(
                        "  KeeperHub a renvoyé un transactionHash non-EVM (%r) — id d'exécution uniquement.",
                        tid,
                    )
                if exe:
                    finding["execution_id"] = str(exe)
                ah = finding.get("tx_hash") or finding.get("execution_id")
                logger.info(f"  → KeeperHub OK — preuve chaîne/id: {ah}")

        except Exception as e:
            logger.error(f"   KeeperHub error : {e}")
            finding["keeperhub_error"] = str(e)

        anchored_results.append(finding)

    return anchored_results
