# backend/pipeline/phase6_report.py
"""
Phase 6 : Report

- Enrichit chaque finding avec fix_sketch (LLM) + prior_audit_ref (mémoire) + onchain_proof
- Génère un rapport JSON structuré : severity, file, line, description,
  prior_audit_ref, fix_sketch, onchain_proof
- Déclenche mint_cert() ENS si 0 findings HIGH
- Retourne le rapport complet pour le server + CLI
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from openai import OpenAI


def _default_contracts_dir() -> str:
    """
    Dossier Hardhat à la racine du dépôt (sibling de backend/).
    Si absent (paquet installé ailleurs), retombe sur ./contracts (CWD).
    """
    backend_pkg = Path(__file__).resolve().parent.parent
    candidate = backend_pkg.parent / "contracts"
    if candidate.is_dir():
        return str(candidate)
    return "./contracts"


# ─── LLM client ───────────────────────────────────────────────────────────────

def _get_llm_client() -> Optional[OpenAI]:
    """Build an OpenAI-compatible client from the Vercel AI Gateway credentials."""
    api_key  = os.getenv("EMBEDDING_API_KEY") or os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("EMBEDDING_ENDPOINT") or os.getenv("OPENAI_BASE_URL", "https://ai-gateway.vercel.sh/v1")
    if not api_key:
        return None   # Phase 6 will fall back to a stub fix_sketch
    return OpenAI(api_key=api_key, base_url=base_url)


# ─── Fix sketch ───────────────────────────────────────────────────────────────

_FIX_SYSTEM = (
    "You are an elite Solidity security engineer. "
    "Given a vulnerability finding, write a concise fix sketch: "
    "2–4 lines of pseudo-code or commented guidance. "
    "Be concrete — name the exact state update, modifier, or check that's missing. "
    "No preamble, no markdown headers. Output the fix sketch only."
)

async def _generate_fix_sketch(finding: dict, client: OpenAI) -> str:
    """Génère une correction courte via LLM pour HIGH/MEDIUM findings."""
    user_msg = (
        f"Title: {finding.get('title', '')}\n"
        f"Severity: {finding.get('severity', '')}\n"
        f"File: {finding.get('file', '')}"
        + (f":{finding.get('line')}" if finding.get('line') else "")
        + f"\nDescription: {(finding.get('description') or finding.get('reason') or '')[:400]}"
    )
    try:
        resp = await asyncio.to_thread(
            client.chat.completions.create,
            model="anthropic/claude-sonnet-4-5",
            messages=[
                {"role": "system", "content": _FIX_SYSTEM},
                {"role": "user",   "content": user_msg},
            ],
            temperature=0,
            max_tokens=250,
        )
        return resp.choices[0].message.content.strip()
    except Exception as exc:
        return f"// Manual review required — {finding.get('title', 'unknown')}: {exc}"


# ─── Prior audit reference ────────────────────────────────────────────────────

# Mapping léger : pattern keyword → référence historique connue
_PRIOR_REF_MAP: list[tuple[list[str], str]] = [
    (
        ["reentrancy", "reentrance", "reentrancy-eth", "reentrant"],
        "The DAO (2016) · Euler Finance (2023) — Rekt.news / Immunefi",
    ),
    (
        ["access-control", "authorization", "onlyowner", "ownership"],
        "Poly Network (2021) · Ronin Bridge (2022) — Immunefi Disclosures",
    ),
    (
        ["oracle", "price-manipulation", "price-oracle", "flashloan", "flash-loan"],
        "Mango Markets (2022) · Cream Finance (2021) · TWAP attacks — Rekt.news",
    ),
    (
        ["overflow", "underflow", "arithmetic", "integer"],
        "batchOverflow (2018) · Various ERC-20 exploits — Trail of Bits",
    ),
    (
        ["uninitialized", "proxy", "initialize"],
        "Wormhole Uninitialized Proxy (2022) — Immunefi Disclosure",
    ),
    (
        ["front-running", "frontrun", "mev", "sandwich"],
        "Classic MEV sandwich attacks — flashbots.net / EigenPhi research",
    ),
    (
        ["signature", "replay", "ecrecover", "malleability"],
        "Polygon Plasma Bridge (2021) — Immunefi Disclosure",
    ),
    (
        ["governance", "flash", "voting", "proposal"],
        "Beanstalk Governance (2022) · Compound Governance attack — Rekt.news",
    ),
    (
        ["delegatecall", "storage-collision", "proxy-storage"],
        "Parity Multisig (2017) — Consensys Audit Reports",
    ),
]


def _find_prior_audit_ref(finding: dict, known_findings: list[dict]) -> Optional[str]:
    """
    Cherche une référence historique :
    1. D'abord dans la mémoire Cognee (sources bootstrapées)
    2. Puis via le mapping statique
    """
    title_lower = (finding.get("title") or "").lower()
    check_lower = (finding.get("check") or finding.get("title") or "").lower()
    combined = f"{title_lower} {check_lower}"

    # 1. Mémoire Cognee
    for kf in known_findings:
        desc_lower = (kf.get("description") or "").lower()
        # Cherche un mot-clé commun entre le finding et le souvenir
        for kw in ["reentrancy", "access", "oracle", "overflow", "proxy", "flash"]:
            if kw in combined and kw in desc_lower:
                if "[source:" in desc_lower:
                    src = desc_lower.split("[source:")[1].split("]")[0].strip()
                    return src.title()
                return kf.get("type", "Historical Memory — Collective DB")

    # 2. Mapping statique
    for keywords, ref in _PRIOR_REF_MAP:
        if any(kw in combined for kw in keywords):
            return ref

    return None


# ─── ENS cert mint ────────────────────────────────────────────────────────────

def _mint_ens_cert(
    contract_address: str,
    verdict: str,
    high_count: int,
    medium_count: int,
    tx_proof: str,
    report_hash: str,
    audit_date: str,
    contracts_dir: str,
) -> Optional[str]:
    """
    Appelle ensManager.ts via subprocess pour minter le certificat ENS.
    Retourne le subname (ex: contract-abcd12.certified.onchor-ai.eth) ou None.
    """
    try:
        result = subprocess.run(
            [
                "npx", "ts-node", "scripts/ensManager.ts",
                "mintCert",
                contract_address,
                verdict,
                str(high_count),
                str(medium_count),
                tx_proof,
                report_hash,
                audit_date,
            ],
            cwd=contracts_dir,
            capture_output=True,
            text=True,
            timeout=90,
        )

        if result.returncode != 0:
            print(f" [Phase 6] ENS mintCert stderr: {result.stderr[:300]}")

        # Cherche la ligne ENS_SUBNAME=... dans stdout
        for line in result.stdout.splitlines():
            if line.startswith("ENS_SUBNAME="):
                return line.split("=", 1)[1].strip()

        # Pas de subname trouvé — log la sortie complète pour debug
        if result.stdout:
            print(f"  [Phase 6] ENS stdout (no subname): {result.stdout[:400]}")

        return None

    except subprocess.TimeoutExpired:
        print("  [Phase 6] ENS mint timed out (90s)")
        return None
    except FileNotFoundError:
        print(f"  [Phase 6] npx/ts-node not found in {contracts_dir} — skipping ENS")
        return None
    except Exception as exc:
        print(f"  [Phase 6] ENS mint error: {exc}")
        return None


# ─── Merge & deduplicate findings ─────────────────────────────────────────────

# Keywords used for semantic deduplication:
# if a Slither check and an agent finding share a keyword AND the same file,
# they describe the same vulnerability found by both tools → skip the Slither one.
_DEDUP_KEYWORDS = [
    "reentrancy", "access-control", "oracle", "overflow",
    "uninitialized", "delegatecall", "signature", "front-run",
]

def _merge_findings(
    investigation_findings: list[dict],
    slither_findings: list[dict],
) -> list[dict]:
    """
    Merges agent and Slither findings, deduplicating on two criteria:
      1. Exact/substring match of the Slither check name in agent titles.
      2. Shared keyword + same file (catches "reentrancy-eth" ↔ "Reentrancy in withdraw()").
    """
    merged  = list(investigation_findings)
    covered = {(f.get("title") or "").lower() for f in investigation_findings}

    for sf in slither_findings:
        check   = (sf.get("check") or "").lower()
        sf_file = (sf.get("file") or "").lower()

        # 1. Skip if the check name is already covered (substring match)
        if any(check in c or c in check for c in covered):
            continue

        # 2. Skip if a shared keyword + same file → same vuln detected differently
        already_covered = False
        for kw in _DEDUP_KEYWORDS:
            if kw in check:
                for inv_f in investigation_findings:
                    inv_title = (inv_f.get("title") or "").lower()
                    inv_file  = (inv_f.get("file") or "").lower()
                    if kw in inv_title and inv_file == sf_file:
                        already_covered = True
                        break
            if already_covered:
                break

        if already_covered:
            continue

        impact = (sf.get("impact") or "").upper()
        merged.append({
            "severity":    impact if impact in ("HIGH", "MEDIUM", "LOW") else "INFO",
            "confidence":  "LIKELY" if impact in ("HIGH", "MEDIUM") else "SUSPECTED",
            "title":       sf.get("check", "Unknown"),
            "file":        sf.get("file", "unknown"),
            "line":        None,
            "description": sf.get("description", ""),
            "reason":      sf.get("description", ""),
        })

    return merged


# ─── Main ─────────────────────────────────────────────────────────────────────

async def run_report(
    scope,
    slither_data: dict,
    inventory_data: dict,
    triage_data: dict,
    investigation_data: dict,
    target_address: Optional[str] = None,
    contracts_dir: Optional[str] = None,
) -> dict:
    """
    Phase 6 — Rapport final.

    1. Fusionne tous les findings
    2. Enrichit chaque finding : fix_sketch (LLM) + prior_audit_ref + onchain_proof
    3. Mint le certificat ENS si 0 findings HIGH
    4. Retourne le rapport JSON complet

    Args:
        scope             : ResolvedContract (Phase 0)
        slither_data      : sortie de run_slither()
        inventory_data    : sortie de run_inventory()
        triage_data       : sortie de run_triage()
        investigation_data: sortie de run_investigation() après Phase 5
        target_address    : adresse 0x si audit onchain
        contracts_dir     : chemin vers le dossier npm/hardhat contenant scripts/ensManager.ts
                            (défaut: ../contracts depuis backend, ou CONTRACTS_DIR)
    """
    print("📋 [Phase 6] Génération du rapport final...")
    _contracts_dir = contracts_dir or os.getenv("CONTRACTS_DIR") or _default_contracts_dir()
    client = _get_llm_client()

    # ── 1. Merge findings ──────────────────────────────────────────────────────
    raw_investigation = investigation_data.get("findings", [])
    raw_slither       = slither_data.get("findings", [])
    known_findings    = inventory_data.get("known_findings", [])

    all_findings = _merge_findings(raw_investigation, raw_slither)
    print(f"  ↳ {len(all_findings)} finding(s) après fusion (agent: {len(raw_investigation)}, slither-only: {len(all_findings) - len(raw_investigation)})")

    # ── 2. Enrichissement ─────────────────────────────────────────────────────
    enriched: list[dict] = []
    for i, finding in enumerate(all_findings):
        sev = (finding.get("severity") or "INFO").upper()

        # fix_sketch — seulement pour HIGH et MEDIUM (sinon trop long + rate limit)
        if sev in ("HIGH", "MEDIUM") and client:
            fix_sketch = await _generate_fix_sketch(finding, client)
            await asyncio.sleep(1.2)   # respecte le quota Vercel Gateway
        else:
            fix_sketch = (
                f"// {sev} severity — manual review recommended for "
                f"'{finding.get('title', 'this issue')}'"
            )

        prior_ref    = _find_prior_audit_ref(finding, known_findings)
        onchain_proof = finding.get("tx_hash") or finding.get("anchor_tx")

        enriched.append(
            {
                "id":              f"F-{i + 1:03d}",
                "severity":        sev,
                "confidence":      (finding.get("confidence") or "SUSPECTED").upper(),
                "title":           finding.get("title", "Unknown"),
                "file":            finding.get("file", "unknown"),
                "line":            finding.get("line"),
                "description":     finding.get("description") or finding.get("reason") or "",
                "fix_sketch":      fix_sketch,
                "prior_audit_ref": prior_ref,
                "onchain_proof":   onchain_proof,
                "pattern_hash":    finding.get("pattern_hash"),
            }
        )
        print(f"  [{i + 1}/{len(all_findings)}] {sev:6s} · {finding.get('title', '')[:50]}")

    # ── 3. Compteurs & verdict ─────────────────────────────────────────────────
    high_count   = sum(1 for f in enriched if f["severity"] == "HIGH")
    medium_count = sum(1 for f in enriched if f["severity"] == "MEDIUM")
    low_count    = sum(1 for f in enriched if f["severity"] == "LOW")
    anchored_count = sum(1 for f in enriched if f.get("onchain_proof"))

    final_verdict = "CERTIFIED" if high_count == 0 and medium_count == 0 else "FINDINGS_FOUND"

    # ── 4. Report hash ────────────────────────────────────────────────────────
    audit_date  = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    report_core = {
        "verdict":  final_verdict,
        "findings": enriched,
        "date":     audit_date,
    }
    report_hash = "0x" + hashlib.sha256(
        json.dumps(report_core, sort_keys=True).encode()
    ).hexdigest()

    # Premier tx_proof disponible (pour ENS text record)
    tx_proof = next(
        (f["onchain_proof"] for f in enriched if f.get("onchain_proof")),
        "0x" + "0" * 64,
    )

    # ── 5. ENS mint ───────────────────────────────────────────────────────────
    contract_addr = (
        target_address
        or (scope.address if scope else None)
        or "0x0000000000000000000000000000000000000000"
    )
    ens_subname = None
    ens_url     = None

    if high_count == 0:
        print(f"  ✓ Aucun finding HIGH — déclenchement du mint ENS...")
        ens_subname = _mint_ens_cert(
            contract_address=contract_addr,
            verdict=final_verdict,
            high_count=high_count,
            medium_count=medium_count,
            tx_proof=tx_proof,
            report_hash=report_hash,
            audit_date=audit_date,
            contracts_dir=_contracts_dir,
        )
        if ens_subname:
            ens_url = f"https://app.ens.domains/{ens_subname}"
            print(f"  ENS minté : {ens_subname}")
        else:
            print("  ENS mint échoué — rapport complet sans certificat")
    else:
        print(f"   {high_count} finding(s) HIGH — certificat ENS non émis")

    # ── 6. Rapport final ──────────────────────────────────────────────────────
    report = {
        "verdict":    final_verdict,
        "risk_score": triage_data.get("risk_score", 0),
        "audit_date": audit_date,
        "report_hash": report_hash,
        "target": {
            "address":  contract_addr,
            "files":    getattr(scope, "files", []) if scope else [],
            "upstream": scope.upstream.name if (scope and scope.upstream) else None,
        },
        "summary": {
            "total_findings":  len(enriched),
            "high_count":      high_count,
            "medium_count":    medium_count,
            "low_count":       low_count,
            "anchored_count":  anchored_count,
        },
        "findings": enriched,
        "memory": {
            "hits":    len(known_findings),
            "sources": list({kf.get("type", "unknown") for kf in known_findings}),
        },
        "onchain": {
            "anchor_registry": os.getenv("ANCHOR_REGISTRY_ADDRESS"),
            "network":         "Ethereum Sepolia",
            "etherscan_base":  "https://sepolia.etherscan.io/tx/",
            "tx_proof":        tx_proof,
        },
        "ens": {
            "subname":   ens_subname,
            "url":       ens_url,
            "certified": high_count == 0 and ens_subname is not None,
            "parent":    os.getenv("ENS_PARENT_CERT", "certified.onchor-ai.eth"),
        },
        "pipeline": {
            "slither_findings":    len(raw_slither),
            "investigation_turns": investigation_data.get("turns_used", 0),
            "model":               investigation_data.get("model", ""),
            "anchors_phase4":      len(investigation_data.get("anchored", [])),
        },
        "generated": datetime.now(timezone.utc).isoformat() + "Z",
    }

    print(
        f"\n [Phase 6] Rapport final — verdict: {final_verdict} | "
        f"HIGH: {high_count} · MED: {medium_count} · LOW: {low_count} | "
        f"anchors: {anchored_count}"
    )
    if ens_subname:
        print(f"    {ens_subname}")

    return report