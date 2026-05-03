"""
Collective memory on 0G KV Storage.
Plus de MANIFEST_ROOT_HASH — le manifest est lu directement depuis 0G.
"""
import json
import os
import time
from pathlib import Path

from storage.zero_g_kv_client import kv_get, kv_set, kv_set_pattern, MANIFEST_KEY
from pipeline.utils import compute_pattern_hash

KEYWORD_MAP = {
    "reentrancy": ["reentrancy", "reentrance", "reentrant", "external call", "withdraw"],
    "access_control": ["access control", "onlyowner", "ownership", "authorization", "admin"],
    "oracle": ["oracle", "price manipulation", "twap", "flashloan", "flash loan"],
    "overflow": ["overflow", "underflow", "arithmetic", "integer"],
    "proxy": ["proxy", "uninitialized", "delegatecall", "storage collision"],
    "governance": ["governance", "voting", "proposal", "flash loan"],
    "signature": ["signature", "replay", "ecrecover", "malleability"],
}


def _extract_keywords(query: str) -> list[str]:
    query_lower = query.lower()
    matched = []
    for category, keywords in KEYWORD_MAP.items():
        if any(kw in query_lower for kw in keywords):
            matched.extend(keywords)
    if not matched:
        matched = query_lower.split()
    return matched


def _map_vuln_type(finding: dict) -> str:
    title = (finding.get("title") or "").lower()
    if any(k in title for k in ["reentr", "reentrance"]):
        return "reentrancy"
    if any(k in title for k in ["access", "owner", "auth"]):
        return "access_control"
    if any(k in title for k in ["oracle", "price", "flash"]):
        return "oracle"
    if any(k in title for k in ["overflow", "underflow"]):
        return "overflow"
    if any(k in title for k in ["proxy", "delegatecall"]):
        return "proxy"
    if any(k in title for k in ["signature", "replay"]):
        return "signature"
    return "unknown"


def _anonymize_description(finding: dict) -> str:
    title = finding.get("title", "unknown vulnerability")
    reason = (finding.get("reason") or finding.get("description") or "")[:120]
    return f"{title}: {reason}".strip()


# Alias for server.py which calls _get_or_fetch_manifest
async def _get_or_fetch_manifest() -> list[dict]:
    return await _get_manifest()


async def _get_manifest() -> list[dict]:
    """Read manifest from 0G KV — always up to date, no env var needed."""
    data = kv_get(MANIFEST_KEY, use_cache=True)
    if not data:
        return []
    return data.get("entries", [])


async def _update_manifest(new_entries: list[dict]) -> None:
    """Update manifest in 0G KV."""
    kv_set(MANIFEST_KEY, {
        "schema": "onchor-ai/manifest/v1",
        "key": MANIFEST_KEY,
        "entries": new_entries,
        "updated_at": time.time(),
    })
    # Invalidate local cache
    cache = Path.home() / ".onchor-ai" / "kv_cache" / "onchor-manifest-v1.json"
    if cache.is_file():
        cache.unlink()


async def query_collective_memory(query: str, top_k: int = 5) -> list[dict]:
    """Search collective memory on 0G."""
    manifest = await _get_manifest()
    if not manifest:
        return []

    keywords = _extract_keywords(query)

    scored = []
    for entry in manifest:
        desc = entry.get("abstract_description", "").lower()
        entry_type = entry.get("type", "").lower()
        score = sum(1 for kw in keywords if kw in desc or kw in entry_type)
        if score > 0:
            scored.append((score, entry))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [entry for _, entry in scored[:top_k]]


def format_collective_results(results: list[dict]) -> str:
    if not results:
        return "No collective memory hits."
    lines = []
    for r in results:
        lines.append(
            f"[0G Memory Hit] {r.get('abstract_description', '')}\n"
            f"  Type: {r.get('type', 'unknown')} | "
            f"Severity: {r.get('severity', '?')} | "
            f"Confirmations: {r.get('confirmation_count', 1)}\n"
            f"  Fix: {r.get('fix_pattern', 'see description')}"
        )
    return "\n---\n".join(lines)


async def contribute_patterns(findings: list[dict]) -> list[dict]:
    contributed = []
    current_entries = await _get_manifest()
    existing_hashes = {e.get("pattern_hash") for e in current_entries}

    for finding in findings:
        sev = (finding.get("severity") or "").upper()
        if sev not in ("HIGH", "MEDIUM"):
            continue

        title = (finding.get("title") or "").strip()
        if not title:
            continue

        reason = (finding.get("reason") or finding.get("description") or "")
        ph = compute_pattern_hash(title[:60], reason)

        if ph in existing_hashes:
            continue

        payload = {
            "schema": "onchor-ai/pattern/v1",
            "pattern_hash": ph,
            "pattern_type": _map_vuln_type(finding),
            "abstract_description": _anonymize_description(finding),
            "fix_pattern": (finding.get("fix_sketch") or "")[:200],
            "severity": sev,
            "confidence": finding.get("confidence", "CONFIRMED"),
            "confirmation_count": 1,
            "keywords": _extract_keywords(_anonymize_description(finding)),
        }

        try:
            tx = kv_set_pattern(ph, payload)
            entry = {
                "pattern_hash": ph,
                "tx": tx,
                "type": payload["pattern_type"],
                "severity": sev,
                "abstract_description": payload["abstract_description"],
                "keywords": payload["keywords"],
            }
            contributed.append(entry)
            existing_hashes.add(ph)
            print(f"[0G KV] Pattern stored: {ph[:16]}... tx: {tx[:16]}...")
        except Exception as e:
            print(f"[0G KV] Failed: {e}")

    if contributed:
        updated = current_entries + contributed
        await _update_manifest(updated)
        print(f"[0G KV] Manifest updated — {len(updated)} patterns total")

    return contributed