"""
Mémoire collective sur 0G KV Storage.
Manifest index + fetch patterns par mots-clés.
"""

import json
import os
import time
from pathlib import Path
from storage.zero_g_client import store_pattern, retrieve_pattern

MANIFEST_KEY = "onchor-manifest-v1"
CACHE_PATH = Path("~/.onchor-ai/manifest-cache.json").expanduser()
CACHE_TTL_SECONDS = 3600  # 1h

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
    """Extrait les mots-clés pertinents d'une query naturelle."""
    query_lower = query.lower()
    matched = []
    for category, keywords in KEYWORD_MAP.items():
        if any(kw in query_lower for kw in keywords):
            matched.extend(keywords)
    # Fallback : mots de la query directement
    if not matched:
        matched = query_lower.split()
    return matched


async def _get_or_fetch_manifest() -> list[dict]:
    if CACHE_PATH.exists():
        age = time.time() - CACHE_PATH.stat().st_mtime
        if age < CACHE_TTL_SECONDS:
            return json.loads(CACHE_PATH.read_text())

    # Essai 1 : clé nommée
    try:
        data = retrieve_pattern(MANIFEST_KEY)
        manifest = data.get("entries", [])
    except Exception:
        # Essai 2 : rootHash depuis .env (fallback si clé nommée indisponible)
        manifest_root = os.getenv("MANIFEST_ROOT_HASH")
        if not manifest_root:
            return []
        data = retrieve_pattern(manifest_root)
        manifest = data.get("entries", [])

    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(manifest))
    return manifest


async def query_collective_memory(query: str, top_k: int = 5) -> list[dict]:
    """
    Cherche dans la mémoire collective sur 0G.
    Retourne les top_k patterns les plus pertinents.
    """
    manifest = await _get_or_fetch_manifest()
    if not manifest:
        return []

    keywords = _extract_keywords(query)

    # Score chaque entrée du manifest
    scored = []
    for entry in manifest:
        desc = entry.get("abstract_description", "").lower()
        entry_type = entry.get("type", "").lower()
        score = sum(1 for kw in keywords if kw in desc or kw in entry_type)
        if score > 0:
            scored.append((score, entry))

    # Trier par score décroissant, prendre top_k
    scored.sort(key=lambda x: x[0], reverse=True)
    top_entries = [entry for _, entry in scored[:top_k]]

    # Fetch les patterns complets depuis 0G
    results = []
    for entry in top_entries:
        try:
            pattern = retrieve_pattern(entry["root_hash"])
            pattern["_source"] = "0G Collective"
            pattern["_score"] = scored[[e for _, e in scored].index(entry)][0] if entry in [e for _, e in scored] else 0
            results.append(pattern)
        except Exception as e:
            print(f"  [0G] Failed to fetch pattern {entry.get('root_hash', '')[:16]}: {e}")

    return results


def format_collective_results(results: list[dict]) -> str:
    """Formate les résultats pour l'agent Phase 4."""
    if not results:
        return "No collective memory hits."

    lines = []
    for r in results:
        lines.append(
            f"[0G Memory Hit] {r.get('abstract_description', '')}\n"
            f"  Type: {r.get('pattern_type', 'unknown')} | "
            f"Severity: {r.get('severity', '?')} | "
            f"Confidence: {r.get('confirmation_count', 1)} confirmations\n"
            f"  Fix: {r.get('fix_pattern', 'see description')}"
        )
    return "\n---\n".join(lines)