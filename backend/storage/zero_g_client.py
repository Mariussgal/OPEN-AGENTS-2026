"""
0G Storage : JSON ↔ rootHash (`0g/0g_upload.js`, `0g/0g_download.js`).

``OG_STORAGE_MODE`` :
  - ``live`` (défaut) — upload/download réels (Galileo / testnet 0G).
  - ``merkle`` — Merkle root uniquement (pas de données récupérables sur le réseau).
  - ``mock`` — stockage dans ``backend/storage/.zero_g_mock/`` (sans réseau).
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Literal

def _resolve_zero_g_dir() -> Path:
    """
    Trouve le dossier 0g/ (scripts Node) en remontant depuis ce fichier.
    Nécessaire si le déploiement utilise la racine du repo (backend + 0g).
    Si seul backend/ est déployé sur Render, 0g/ sera absent — erreur explicite.
    """
    p = Path(__file__).resolve().parent
    for _ in range(8):
        cand = p / "0g" / "0g_download.js"
        if cand.is_file():
            return p / "0g"
        if p.parent == p:
            break
        p = p.parent
    raise FileNotFoundError(
        "Dossier 0g/ introuvable (0g_download.js). "
        "Déploie la racine du monorepo (pas seulement backend/), "
        "ou copie 0g/ à côté du backend. "
        "Puis: cd 0g && npm install"
    )


_ZERO_G_DIR = _resolve_zero_g_dir()
_UPLOAD_JS = _ZERO_G_DIR / "0g_upload.js"
_DOWNLOAD_JS = _ZERO_G_DIR / "0g_download.js"
_STORAGE_DIR = Path(__file__).resolve().parent
_MOCK_ROOT = _STORAGE_DIR / ".zero_g_mock"

SCHEMA_PATTERN_V1 = "onchor-ai/pattern/v1"
StorageMode = Literal["live", "merkle", "mock"]


def _storage_mode() -> StorageMode:
    raw = (os.getenv("OG_STORAGE_MODE") or "live").strip().lower()
    if raw in ("live", "merkle", "mock"):
        return raw  # type: ignore[return-value]
    raise ValueError(f"Invalid OG_STORAGE_MODE: {raw!r}")


def normalize_pattern_hash(pattern_hash: str) -> str:
    ph = (pattern_hash or "").strip()
    if ph.startswith("0x"):
        return ph
    if len(ph) == 64 and all(c in "0123456789abcdefABCDEF" for c in ph):
        return "0x" + ph
    return ph


def pattern_storage_payload(
    pattern_hash: str,
    *,
    title: str = "",
    reason: str = "",
    severity: str | None = None,
    confidence: str | None = None,
    file: str | None = None,
    line: str | int | None = None,
) -> dict[str, Any]:
    return {
        "schema": SCHEMA_PATTERN_V1,
        "pattern_hash": normalize_pattern_hash(pattern_hash),
        "title": title,
        "reason": reason,
        "severity": severity,
        "confidence": confidence,
        "file": file,
        "line": str(line) if line is not None else None,
    }


def _normalize_root_hash(root_hash: str) -> str:
    rh = root_hash.strip()
    if rh.startswith("0x"):
        return rh
    if len(rh) == 64 and all(c in "0123456789abcdefABCDEF" for c in rh):
        return "0x" + rh
    return rh


def _mock_file(root_hash: str) -> Path:
    rh = _normalize_root_hash(root_hash)
    hx = rh[2:] if rh.startswith("0x") else rh
    return _MOCK_ROOT / f"{hx}.json"


def _node_env() -> dict[str, str]:
    env = os.environ.copy()
    for k in ("OG_EVM_RPC", "OG_INDEXER_RPC", "OG_PRIVATE_KEY", "OG_STORAGE_MODE"):
        v = os.getenv(k)
        if v:
            env[k] = v
    return env


def _run_node(script: Path, args: list[str], stdin: str | None = None, timeout: int = 300) -> dict[str, Any]:
    if not script.is_file():
        raise FileNotFoundError(f"Script 0G introuvable: {script} — lance \"npm install\" dans {_ZERO_G_DIR}")
    proc = subprocess.run(
        ["node", str(script), *args],
        input=stdin.encode("utf-8") if stdin is not None else None,
        capture_output=True,
        timeout=timeout,
        env=_node_env(),
        cwd=str(_ZERO_G_DIR),
    )
    err_txt = (proc.stderr or b"").decode("utf-8", errors="replace").strip()
    out_txt = (proc.stdout or b"").decode("utf-8", errors="replace").strip()
    if proc.returncode != 0:
        raise RuntimeError(f"0g node exit {proc.returncode}: {err_txt or out_txt or 'no output'}")
    if not out_txt:
        raise RuntimeError(f"stdout vide. stderr: {err_txt}")
    line = out_txt.splitlines()[-1]
    return json.loads(line)


def merkle_root_json(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    out = _run_node(_UPLOAD_JS, ["--merkle-only"], stdin=raw, timeout=60)
    if not out.get("ok"):
        raise RuntimeError(out.get("error", "merkle failed"))
    rh = out.get("rootHash")
    if not rh:
        raise RuntimeError("no rootHash")
    return str(rh)


def store_pattern(payload: dict[str, Any]) -> str:
    mode = _storage_mode()
    if mode == "merkle":
        return merkle_root_json(payload)
    if mode == "mock":
        rh = merkle_root_json(payload)
        _MOCK_ROOT.mkdir(parents=True, exist_ok=True)
        _mock_file(rh).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return rh

    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    out = _run_node(_UPLOAD_JS, [], stdin=raw, timeout=600)
    if not out.get("ok"):
        raise RuntimeError(out.get("error", "upload failed"))
    rh = out.get("rootHash")
    if not rh:
        raise RuntimeError("no rootHash")
    return str(rh)


def store_pattern_with_proof(payload: dict[str, Any]) -> dict[str, str]:
    """
    Stocke un payload et retourne le rootHash + txHash (si disponible).
    """
    mode = _storage_mode()
    if mode == "merkle":
        rh = merkle_root_json(payload)
        return {"root_hash": str(rh), "tx_hash": ""}
    if mode == "mock":
        rh = merkle_root_json(payload)
        _MOCK_ROOT.mkdir(parents=True, exist_ok=True)
        _mock_file(rh).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return {"root_hash": str(rh), "tx_hash": ""}

    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    out = _run_node(_UPLOAD_JS, [], stdin=raw, timeout=600)
    if not out.get("ok"):
        raise RuntimeError(out.get("error", "upload failed"))
    rh = out.get("rootHash")
    if not rh:
        raise RuntimeError("no rootHash")
    tx = out.get("txHash") or ""
    return {"root_hash": str(rh), "tx_hash": str(tx)}


def retrieve_pattern(root_hash: str) -> dict[str, Any]:
    rh = _normalize_root_hash(root_hash)
    mode = _storage_mode()
    if mode == "merkle":
        raise RuntimeError("OG_STORAGE_MODE=merkle : pas de retrieve réseau ni mock")
    if mode == "mock":
        p = _mock_file(rh)
        if not p.is_file():
            raise FileNotFoundError(f"mock: no file for {rh}")
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise RuntimeError("mock: JSON racine doit être un objet")
        return data

    out = _run_node(_DOWNLOAD_JS, [rh], timeout=300)
    if not out.get("ok"):
        raise RuntimeError(out.get("error", "download failed"))
    data = out.get("data")
    if not isinstance(data, dict):
        raise RuntimeError("invalid downloaded payload")
    return data


MANIFEST_KEY_PREFIX = "onchor-manifest"


def store_manifest(manifest_data: dict) -> str:
    """
    Stocke le manifest avec une clé nommée stable.
    Retourne le rootHash 0G.
    """
    payload = {
        **manifest_data,
        "key": MANIFEST_KEY_PREFIX + "-v1",
    }
    return store_pattern(payload)
