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
    """Description générique, sans adresses ni noms de projet."""
    title = finding.get("title", "unknown vulnerability")
    reason = (finding.get("reason") or finding.get("description") or "")[:120]
    return f"{title}: {reason}".strip()


def _update_manifest_root_hash_in_env(new_root: str):
    """Met à jour MANIFEST_ROOT_HASH dans .env et dans os.environ."""
    import os
    from pathlib import Path
    os.environ["MANIFEST_ROOT_HASH"] = new_root
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()
        found = False
        for i, line in enumerate(lines):
            if line.startswith("MANIFEST_ROOT_HASH="):
                lines[i] = f"MANIFEST_ROOT_HASH={new_root}"
                found = True
                break
        if not found:
            lines.append(f"MANIFEST_ROOT_HASH={new_root}")
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[0G] MANIFEST_ROOT_HASH updated → {new_root[:20]}...")


async def contribute_patterns(findings: list[dict]) -> list[dict]:
    """
    Upload les patterns HIGH/MEDIUM sur 0G et met à jour le manifest collectif.
    Retourne les entrées ajoutées.
    """
    from storage.zero_g_client import store_pattern_with_proof
    from pipeline.utils import compute_pattern_hash

    contributed = []

    for finding in findings:
        sev = (finding.get("severity") or "").upper()
        if sev not in ("HIGH", "MEDIUM"):
            continue
        title = (finding.get("title") or "").strip()
        if not title:
            continue

        reason = (finding.get("reason") or finding.get("description") or "")
        ph = compute_pattern_hash(title[:60], reason)
        keywords = _extract_keywords(_anonymize_description(finding))

        payload = {
            "schema": "onchor-ai/pattern/v1",
            "pattern_hash": ph,
            "pattern_type": _map_vuln_type(finding),
            "abstract_description": _anonymize_description(finding),
            "fix_pattern": (finding.get("fix_sketch") or "")[:200],
            "severity": sev,
            "confidence": finding.get("confidence", "CONFIRMED"),
            "confirmation_count": 1,
            "keywords": keywords,
            "source": "onchor-ai collective contribution",
        }

        try:
            stored = store_pattern_with_proof(payload)
            root_hash = stored["root_hash"]
            tx_hash = stored.get("tx_hash", "")
            entry = {
                "pattern_hash": ph,
                "root_hash": root_hash,
                "tx_hash": tx_hash,
                "type": payload["pattern_type"],
                "severity": sev,
                "abstract_description": payload["abstract_description"],
                "keywords": keywords,
            }
            contributed.append(entry)
            print(f"[0G] Pattern uploaded: {title[:40]} → {root_hash[:20]}...")
        except Exception as e:
            print(f"[0G] Failed to upload pattern '{title[:40]}': {e}")

    if not contributed:
        return []

    # Fetch manifest actuel
    try:
        current_entries = await _get_or_fetch_manifest()
    except Exception:
        current_entries = []

    # Dédup par pattern_hash
    existing_hashes = {e.get("pattern_hash") for e in current_entries}
    fresh = [e for e in contributed if e.get("pattern_hash") not in existing_hashes]

    if not fresh:
        print("[0G] Tous les patterns existent déjà dans le manifest.")
        return []

    updated_entries = current_entries + fresh

    # Re-upload manifest
    try:
        from storage.zero_g_client import store_pattern as sp
        new_manifest_root = sp({
            "schema": "onchor-ai/manifest/v1",
            "key": MANIFEST_KEY,
            "entries": updated_entries,
        })
        print(f"[0G] Manifest re-uploadé — {len(updated_entries)} patterns")

        # Mettre à jour .env + os.environ
        _update_manifest_root_hash_in_env(new_manifest_root)

        # Invalider le cache local
        if CACHE_PATH.exists():
            CACHE_PATH.unlink()

        # Pré-peupler le nouveau cache
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps(updated_entries), encoding="utf-8")

    except Exception as e:
        print(f"[0G] Manifest update failed: {e}")

    return fresh