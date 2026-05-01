"""
Ancrage ``AnchorRegistry.anchor(bytes32 pHash, bytes32 rootHash0G)`` via KeeperHub Direct Execution.
Le réseau doit être celui où le contrat est déployé (souvent Ethereum Sepolia 11155111).
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Hash de transaction canonique pour EVM (32 octets hex, préfixe 0x).
_EVM_TX_HASH = re.compile(r"^0x[0-9a-fA-F]{64}$")


def is_evm_tx_hash(val: object) -> bool:
    """True if `val` looks like a valid EVM tx hash for Etherscan."""
    return isinstance(val, str) and bool(_EVM_TX_HASH.match(val.strip()))

KEEPERHUB_EXECUTE = "https://app.keeperhub.com/api/execute/contract-call"
KEEPERHUB_STATUS = "https://app.keeperhub.com/api/execute/{execution_id}"

# GET uniquement (onboarding / doctor) — évite POST /execute/contract-call comme simple « ping » clé sur chaque install.
KEEPERHUB_VALIDATE_READ_FALLBACK_URLS = [
    u.strip()
    for u in os.getenv(
        "KEEPERHUB_VALIDATION_URL_FALLBACKS",
        "https://app.keeperhub.com/api/workflows,https://app.keeperhub.com/api/me",
    ).split(",")
    if u.strip()
]


def _normalize_keeperhub_bearer_token(api_key: str) -> str:
    """
    Normalise la clé pour ``Authorization: Bearer …``.
    KeeperHub peut livrer des clés en ``kh-<secret>`` ou ``kh_<secret>`` ;
    ne pas préfixer deux fois (ex. ``kh_kh-…`` → 401).
    """
    tok = api_key.strip()
    if tok.lower().startswith("bearer "):
        tok = tok[7:].strip()
    low = tok.lower()
    if low.startswith("kh-") or low.startswith("kh_"):
        return tok
    return "kh_" + tok


def _authorization_headers(api_key: str) -> dict[str, str]:
    """KeeperHub : Bearer token (pas X-API-Key seul → souvent 401)."""
    tok = _normalize_keeperhub_bearer_token(api_key)
    return {"Authorization": f"Bearer {tok}"}


def _bytes32(hex_str: str) -> str:
    s = hex_str.strip().lower()
    if s.startswith("0x"):
        s = s[2:]
    if len(s) != 64 or any(c not in "0123456789abcdef" for c in s):
        raise ValueError(f"Invalid bytes32: {hex_str!r}")
    return "0x" + s


async def keeperhub_anchor_registry(ph: str, rh: str, *, timeout: float = 120.0) -> dict[str, Any]:
    """
    Appelle KeeperHub pour exécuter ``anchor(pattern_hash, root_hash)``.

    Retour inclut au minimum :
        skipped: True if KEEPERHUB_API_KEY or ANCHOR_REGISTRY_ADDRESS is missing
        success / tx_hash / execution_id / error
    """
    api_key = os.getenv("KEEPERHUB_API_KEY")
    registry = os.getenv("ANCHOR_REGISTRY_ADDRESS")
    net = os.getenv("KEEPERHUB_NETWORK") or os.getenv("ANCHOR_CHAIN_ID") or "11155111"

    if not api_key or not registry:
        return {
            "skipped": True,
            "success": False,
            "tx_hash": None,
            "execution_id": None,
            "error": None,
        }

    try:
        pattern_b32 = _bytes32(ph)
        root_b32 = _bytes32(rh)
    except ValueError as e:
        return {
            "skipped": False,
            "success": False,
            "tx_hash": None,
            "execution_id": None,
            "error": str(e),
        }

    try:
        async with httpx.AsyncClient(timeout=timeout) as http:
            resp = await http.post(
                KEEPERHUB_EXECUTE,
                headers=_authorization_headers(api_key),
                json={
                    "contractAddress": registry,
                    "network": net,
                    "functionName": "anchor",
                    "functionArgs": json.dumps([pattern_b32, root_b32]),
                    "wait": True,
                },
            )
        text = resp.text
        try:
            data = resp.json()
        except Exception:
            data = {}

        if resp.status_code >= 400:
            return {
                "skipped": False,
                "success": False,
                "tx_hash": None,
                "execution_id": None,
                "error": f"HTTP {resp.status_code}: {text[:800]}",
            }

        tid = data.get("transactionHash")
        if tid in ("", "pending", None):
            tid = tid or None

        exe = data.get("executionId")

        return {
            "skipped": False,
            "success": True,
            "tx_hash": tid,
            "execution_id": exe,
            "error": None,
            "raw": data,
        }
    except Exception as e:
        return {
            "skipped": False,
            "success": False,
            "tx_hash": None,
            "execution_id": None,
            "error": str(e),
        }


async def get_anchor_tx_from_chain(pattern_hash: str) -> str | None:
    """Fetch anchor() tx hash from Etherscan V2 API."""
    import os
    import httpx

    registry_address = os.getenv("ANCHOR_REGISTRY_ADDRESS")
    etherscan_key = os.getenv("ETHERSCAN_API_KEY")

    if not registry_address or not etherscan_key:
        return None

    ph = pattern_hash.strip().lstrip("0x").zfill(64).lower()

    try:
        async with httpx.AsyncClient(timeout=15.0) as http:
            resp = await http.get(
                "https://api.etherscan.io/v2/api",
                params={
                    "chainid": "11155111",
                    "module": "account",
                    "action": "txlist",
                    "address": registry_address,
                    "startblock": 0,
                    "endblock": 99999999,
                    "sort": "desc",
                    "apikey": etherscan_key,
                },
            )
        data = resp.json()

        if data.get("status") != "1":
            logger.debug(f"Etherscan V2: {data.get('message')}")
            return None

        for tx in data.get("result", []):
            if not isinstance(tx, dict):
                continue
            input_data = tx.get("input", "").lower()
            if not input_data.startswith("0xa21f3c6a"):
                continue
            if ph in input_data:
                tx_hash = tx["hash"]
                logger.info(f"  ✓ anchor tx found: {tx_hash}")
                return tx_hash

    except Exception as e:
        logger.debug(f"get_anchor_tx_from_chain: {e}")

    return None
