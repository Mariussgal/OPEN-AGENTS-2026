"""
0G KV Storage client — remplace le manifest file upload.
Clé = pattern_hash (str), Valeur = JSON du pattern.
Clé spéciale "onchor-manifest-v1" = index de tous les patterns.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

_ZERO_G_DIR = Path(__file__).resolve().parents[2] / "0g"
_KV_SCRIPT = _ZERO_G_DIR / "0g_kv.js"
_CACHE_DIR = Path.home() / ".onchor-ai" / "kv_cache"
_CACHE_TTL = int(os.getenv("ONCHOR_KV_CACHE_TTL_SECONDS", "300"))  # 5 min
MANIFEST_KEY = "onchor-manifest-v1"


def _node_env() -> dict[str, str]:
    env = os.environ.copy()
    for k in ("OG_EVM_RPC", "OG_INDEXER_RPC", "OG_PRIVATE_KEY"):
        v = os.getenv(k)
        if v:
            env[k] = v
    return env


def _run_kv(args: list[str], timeout: int = 60) -> dict[str, Any]:
    if not _KV_SCRIPT.is_file():
        raise FileNotFoundError(f"0g_kv.js introuvable: {_KV_SCRIPT}")
    
    proc = subprocess.run(
        ["node", str(_KV_SCRIPT), *args],
        capture_output=True,
        timeout=timeout,
        env=_node_env(),
        cwd=str(_ZERO_G_DIR),
    )
    out = (proc.stdout or b"").decode("utf-8", errors="replace").strip()
    if not out:
        err = (proc.stderr or b"").decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"0G KV no output. stderr: {err[:200]}")
    
    line = out.splitlines()[-1]
    return json.loads(line)


def _cache_path(key: str) -> Path:
    safe = key.replace("/", "_").replace(":", "_")[:64]
    return _CACHE_DIR / f"{safe}.json"


def _read_cache(key: str) -> dict | None:
    p = _cache_path(key)
    if not p.is_file():
        return None
    age = time.time() - p.stat().st_mtime
    if age > _CACHE_TTL:
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def _write_cache(key: str, data: dict) -> None:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_path(key).write_text(json.dumps(data))


def kv_set(key: str, payload: dict[str, Any]) -> str:
    """
    Stocke un pattern dans 0G KV.
    Retourne le tx hash de la transaction.
    """
    value_str = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    out = _run_kv(["set", key, value_str], timeout=120)
    
    if not out.get("ok"):
        raise RuntimeError(out.get("error", "kv_set failed"))
    
    # Invalider le cache local pour cette clé
    p = _cache_path(key)
    if p.is_file():
        p.unlink()
    
    return out.get("tx", "")


def kv_get(key: str, use_cache: bool = True) -> dict[str, Any] | None:
    """
    Récupère un pattern depuis 0G KV.
    Retourne None si la clé n'existe pas.
    """
    if use_cache:
        cached = _read_cache(key)
        if cached is not None:
            return cached
    
    if key == "onchor-manifest-v1":
        out = _run_kv(["get-manifest"], timeout=30)
    else:
        out = _run_kv(["get", key], timeout=30)
    
    if not out.get("ok"):
        return None
    
    data = out.get("data")
    if data and use_cache:
        _write_cache(key, data)
    
    return data


def kv_set_pattern(pattern_hash: str, payload: dict[str, Any]) -> str:
    """Raccourci : store un pattern indexé par son hash."""
    return kv_set(pattern_hash, payload)


def kv_get_pattern(pattern_hash: str) -> dict[str, Any] | None:
    """Raccourci : fetch un pattern par son hash."""
    return kv_get(pattern_hash)