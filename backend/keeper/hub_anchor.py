"""
Ancrage ``AnchorRegistry.anchor(bytes32 pHash, bytes32 rootHash0G)`` via KeeperHub Direct Execution.
Le réseau doit être celui où le contrat est déployé (souvent Ethereum Sepolia 11155111).
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx

# Hash de transaction canonique pour EVM (32 octets hex, préfixe 0x).
_EVM_TX_HASH = re.compile(r"^0x[0-9a-fA-F]{64}$")


def is_evm_tx_hash(val: object) -> bool:
    """True si ``val`` ressemble à un hash de transaction EVM exploitable pour Etherscan."""
    return isinstance(val, str) and bool(_EVM_TX_HASH.match(val.strip()))

KEEPERHUB_EXECUTE = "https://app.keeperhub.com/api/execute/contract-call"


def _authorization_headers(api_key: str) -> dict[str, str]:
    """
    KeeperHub attend ``Authorization: Bearer kh_<secret>``
    (``X-API-Key`` seul → 401).
    """
    tok = api_key.strip()
    if tok.lower().startswith("bearer "):
        tok = tok[7:].strip()
    if not tok.lower().startswith("kh_"):
        tok = "kh_" + tok
    return {"Authorization": f"Bearer {tok}"}


def _bytes32(hex_str: str) -> str:
    s = hex_str.strip().lower()
    if s.startswith("0x"):
        s = s[2:]
    if len(s) != 64 or any(c not in "0123456789abcdef" for c in s):
        raise ValueError(f"bytes32 invalide : {hex_str!r}")
    return "0x" + s


async def keeperhub_anchor_registry(ph: str, rh: str, *, timeout: float = 120.0) -> dict[str, Any]:
    """
    Appelle KeeperHub pour exécuter ``anchor(pattern_hash, root_hash)``.

    Retour inclut au minimum :
        skipped: True si KEEPERHUB_API_KEY ou ANCHOR_REGISTRY_ADDRESS absent
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
