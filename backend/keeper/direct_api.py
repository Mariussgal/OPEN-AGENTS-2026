"""
Docs  : https://app.keeperhub.com
Auth  : X-API-Key header
"""

import asyncio
import logging
import os

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

KEEPERHUB_BASE_URL      = "https://app.keeperhub.com"
KEEPERHUB_API_KEY       = os.getenv("KEEPERHUB_API_KEY", "")
ANCHOR_REGISTRY_ADDRESS = os.getenv("ANCHOR_REGISTRY_ADDRESS", "0x4DC06573aa7b214645f649E4b9412Fe5aEd775F8")
NETWORK_CHAIN_ID        = "11155111"  # Ethereum Sepolia

POLL_INTERVAL_SEC  = 3
POLL_MAX_ATTEMPTS  = 20   # 60 secondes max

# ── Exceptions ────────────────────────────────────────────────────────────────

class KeeperHubError(Exception):
    """Generic KeeperHub error."""

class AnchorTimeoutError(KeeperHubError):
    """The transaction was not confirmed within the allotted time."""

class AnchorFailedError(KeeperHubError):
    """The transaction failed on the KeeperHub side."""

# ── Helpers ───────────────────────────────────────────────────────────────────

def _headers() -> dict:
    if not KEEPERHUB_API_KEY:
        raise KeeperHubError("KEEPERHUB_API_KEY missing from .env")
    return {
        "Authorization": f"Bearer {KEEPERHUB_API_KEY}",
        "Content-Type":  "application/json",
    }


def _normalize_hash(h: str) -> str:
    h = h.strip()
    return h if h.startswith("0x") else "0x" + h

# ── Core ──────────────────────────────────────────────────────────────────────

async def submit_anchor(pattern_hash: str, root_hash_0g: str) -> str:
    """
    Submits an anchor() call to AnchorRegistry.sol via the Direct Execution API.

    Returns:
        executionId (str) to pass to poll_execution()
    """
    pattern_hash = _normalize_hash(pattern_hash)
    root_hash_0g = _normalize_hash(root_hash_0g)

    payload = {
        "contractAddress": ANCHOR_REGISTRY_ADDRESS,
        "network":         NETWORK_CHAIN_ID,
        "functionName":    "anchor",
        "functionArgs":    f'["{pattern_hash}", "{root_hash_0g}"]',
    }

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{KEEPERHUB_BASE_URL}/api/execute/contract-call",
            headers=_headers(),
            json=payload,
        )

    if response.status_code == 401:
        raise KeeperHubError("Invalid API key (401)")
    if response.status_code == 422:
        raise KeeperHubError("Para Wallet not configured (422)")
    if response.status_code == 429:
        raise KeeperHubError("KeeperHub rate limit reached (429) — retry in 1 min")
    if not response.is_success:
        raise KeeperHubError(f"KeeperHub HTTP {response.status_code}: {response.text}")

    data = response.json()
    execution_id = data.get("executionId") or data.get("execution_id")
    if not execution_id:
        raise KeeperHubError(f"executionId missing from response: {data}")

    logger.debug(f"[KeeperHub] Anchor submitted — executionId: {execution_id}")
    return execution_id


async def poll_execution(execution_id: str) -> str:
    """
    Polls GET /api/execute/{id}/status until the transactionHash is obtained.

    Returns:
        transactionHash (str)
    """
    url = f"{KEEPERHUB_BASE_URL}/api/execute/{execution_id}/status"

    async with httpx.AsyncClient(timeout=15) as client:
        for attempt in range(1, POLL_MAX_ATTEMPTS + 1):
            resp = await client.get(url, headers=_headers())

            if not resp.is_success:
                logger.warning(f"[KeeperHub] Poll {attempt} — HTTP {resp.status_code}")
                await asyncio.sleep(POLL_INTERVAL_SEC)
                continue

            data   = resp.json()
            status = data.get("status", "").lower()
            logger.debug(f"[KeeperHub] Poll {attempt}/{POLL_MAX_ATTEMPTS} — {status}")

            if status == "completed":
                tx = data.get("transactionHash") or data.get("transaction_hash")
                if not tx:
                    raise KeeperHubError(f"Status completed but transactionHash missing: {data}")
                return tx

            if status == "failed":
                reason = data.get("error") or data.get("message") or "unknown reason"
                raise AnchorFailedError(f"Execution {execution_id} failed: {reason}")

            # pending | running → wait
            await asyncio.sleep(POLL_INTERVAL_SEC)

    raise AnchorTimeoutError(
        f"Execution {execution_id} not confirmed after "
        f"{POLL_MAX_ATTEMPTS * POLL_INTERVAL_SEC}s"
    )


async def is_already_anchored(pattern_hash: str) -> bool:
    """
    Calls isAnchored() as a read on AnchorRegistry.
    Avoids double-anchors in Phase 5.
    """
    pattern_hash = _normalize_hash(pattern_hash)

    payload = {
        "contractAddress": ANCHOR_REGISTRY_ADDRESS,
        "network":         NETWORK_CHAIN_ID,
        "functionName":    "isAnchored",
        "functionArgs":    f'["{pattern_hash}"]',
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{KEEPERHUB_BASE_URL}/api/execute/contract-call",
                headers=_headers(),
                json=payload,
            )
        if not resp.is_success:
            return False
        data = resp.json()
        result = data.get("result")
        if isinstance(result, bool):
            return result
        if isinstance(result, str):
            return result.lower() == "true"
    except Exception as e:
        logger.warning(f"[KeeperHub] isAnchored check failed: {e}")
    return False


async def anchor_contribution(pattern_hash: str, root_hash_0g: str) -> str:
    """
    Main function called by Phase 5.
    First checks if the pattern is already anchored, then submits and waits.

    Returns:
        Confirmed transactionHash (str)
    """
    logger.info(f"[Phase5] Anchor {pattern_hash[:12]}... via Direct Execution API")

    # Avoid duplicates (AnchorRegistry.sol reverts if already anchored)
    if await is_already_anchored(pattern_hash):
        logger.info(f"[Phase5] Pattern already anchored onchain — skip")
        return "already_anchored"

    execution_id = await submit_anchor(pattern_hash, root_hash_0g)
    tx_hash      = await poll_execution(execution_id)

    logger.info(f"[Phase5] Anchored — tx: {tx_hash}")
    return tx_hash  