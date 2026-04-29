"""
Streaming NDJSON du pipeline d'audit.

Émet un event JSON par ligne au fil de l'exécution des 7 phases pour que le
CLI puisse afficher une progress bar dynamique + des logs intermédiaires.

Format des events (1 par ligne, NDJSON / application/x-ndjson) :

    {"phase": "resolve",     "status": "start",  "msg": "Resolving target..."}
    {"phase": "resolve",     "status": "done",   "files": 1, "upstream": null}
    {"phase": "inventory",   "status": "start",  "msg": "Parsing AST..."}
    {"phase": "inventory",   "status": "done",   "files_analyzed": 1, "duplicates": 0}
    {"phase": "investigate", "status": "pulse",  "msg": "…"}
    ...
    {"phase": "report",      "status": "done",   "result": {<full JSON>}, "verdict": "FINDINGS_FOUND", "risk_score": 8}
    {"phase": "pipeline",    "status": "done"}

Le dernier `{"phase": "report", "status": "done"}` contient le payload complet
dans `result` — strictement identique à ce que renvoient les routes non-stream
`/audit/local` et `/audit`. Aucune régression côté frontend / scripts.

Mode "paid" :
    Le caller émet en plus un event `{"phase": "payment", ...}` AVANT d'appeler
    `stream_audit_pipeline()` — voir server.py pour la séquence x402.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any, AsyncGenerator, Optional

from pipeline.phase_resolve import resolve_scope
from pipeline.phase1_inventory import run_inventory
from pipeline.phase2_slither import run_slither
from pipeline.phase3_triage import run_triage
from pipeline.phase4_agent import run_investigation
from pipeline.phase5_anchor import run_phase5_anchor
from pipeline.phase6_report import run_report

# Re-export pour back-compat — la source unique est `pipeline.phases`,
# qui n'a aucune dépendance lourde (pas de cognee / slither / anthropic).
from pipeline.phases import PIPELINE_PHASES  # noqa: F401


def _emit(event: dict[str, Any]) -> bytes:
    """Sérialise un event en NDJSON (1 ligne JSON + \\n, encodé UTF-8)."""
    return (json.dumps(event, default=str) + "\n").encode("utf-8")


def _pulse_interval_sec() -> float:
    """Délai entre events ``pulse`` NDJSON pendant les phases longues (keep-alive TCP / proxies)."""
    raw = os.getenv("STREAM_HEARTBEAT_SEC", "20")
    try:
        v = float(raw)
        return max(5.0, min(v, 120.0))
    except ValueError:
        return 20.0


async def _heartbeat_while(task: asyncio.Task, phase_id: str, base_msg: str) -> AsyncGenerator[bytes, None]:
    """Tant que ``task`` n'est pas terminée, émet périodiquement une ligne NDJSON ``status: pulse``."""
    interval = _pulse_interval_sec()
    pulses = 0
    while not task.done():
        done_set, _ = await asyncio.wait(
            {task},
            timeout=interval,
            return_when=asyncio.FIRST_COMPLETED,
        )
        if task in done_set:
            return
        pulses += 1
        yield _emit({
            "phase":  phase_id,
            "status": "pulse",
            "msg":    f"{base_msg} (#{pulses})…",
        })


async def stream_audit_pipeline(
    path: str,
    *,
    target_address: Optional[str] = None,
) -> AsyncGenerator[bytes, None]:
    """Exécute le pipeline 6-phases en émettant un event NDJSON par étape.

    Args:
        path: Chemin local ou adresse 0x.
        target_address: Adresse onchain (pour le report final). Auto-détecté
            si `path` commence par "0x".

    Yields:
        Bytes — une ligne NDJSON par event.
    """

    # ── Phase 0 — Resolve ────────────────────────────────────────────────────
    yield _emit({"phase": "resolve", "status": "start",
                 "msg": "Resolving target — file detection / fork analysis..."})
    scope = await resolve_scope(path)
    yield _emit({
        "phase":    "resolve",
        "status":   "done",
        "files":    len(scope.files),
        "upstream": scope.upstream.name if scope.upstream else None,
        "onchain":  scope.is_onchain,
    })

    # Le `target` passé à slither / report dépend de scope (onchain ou pas).
    target = path
    if scope.is_onchain and scope.files:
        target = os.path.dirname(scope.files[0])

    # ── Phase 1 — Inventory ──────────────────────────────────────────────────
    yield _emit({"phase": "inventory", "status": "start",
                 "msg": "Structural parse · flagging delegatecall / unchecked / assembly..."})
    inventory_data = await run_inventory(scope)
    yield _emit({
        "phase":          "inventory",
        "status":         "done",
        "files_analyzed": inventory_data.get("files_analyzed", 0),
        "duplicates":     inventory_data.get("duplicates_detected", 0),
        "known_findings": inventory_data.get("known_findings_count", 0),
    })

    # ── Phase 2 — Slither ────────────────────────────────────────────────────
    yield _emit({"phase": "slither", "status": "start",
                 "msg": "Running 89 detectors..."})
    slither_task = asyncio.create_task(run_slither(target))
    async for hb in _heartbeat_while(slither_task, "slither", "Slither still running"):
        yield hb
    slither_data = await slither_task
    yield _emit({
        "phase":    "slither",
        "status":   "done",
        "findings": slither_data.get("findings_count", len(slither_data.get("findings", []))),
        "success":  slither_data.get("success", False),
    })

    # ── Phase 3 — Triage ─────────────────────────────────────────────────────
    yield _emit({"phase": "triage", "status": "start",
                 "msg": "Cost-gate triage..."})
    triage_data = await run_triage(slither_data, inventory_data)
    yield _emit({
        "phase":      "triage",
        "status":     "done",
        "risk_score": triage_data.get("risk_score"),
        "verdict":    triage_data.get("verdict"),
    })

    # ── Phase 4 — Investigate (adversarial agent) ────────────────────────────
    yield _emit({"phase": "investigate", "status": "start",
                 "msg": "Spawning adversarial agent (7 tools)..."})
    inv_task = asyncio.create_task(
        run_investigation(scope, slither_data, inventory_data, triage_data)
    )
    async for hb in _heartbeat_while(inv_task, "investigate", "Adversarial agent still running"):
        yield hb
    investigation_data = await inv_task
    yield _emit({
        "phase":          "investigate",
        "status":         "done",
        "findings_count": len(investigation_data.get("findings", [])),
        "turns_used":     investigation_data.get("turns_used"),
        "model":          investigation_data.get("model"),
    })

    # ── Phase 5 — Anchor (KeeperHub) ─────────────────────────────────────────
    yield _emit({"phase": "anchor", "status": "start",
                 "msg": "Anchoring confirmed findings on Sepolia..."})
    anchor_task = asyncio.create_task(
        run_phase5_anchor(investigation_data.get("findings", []))
    )
    async for hb in _heartbeat_while(anchor_task, "anchor", "Onchain anchoring in progress"):
        yield hb
    anchored_findings = await anchor_task
    investigation_data["findings"] = anchored_findings
    # Phase 5 remplit tx_hash ou execution_id (onchain_proof vient après Phase 6).
    anchored_count = sum(
        1
        for f in anchored_findings
        if f.get("onchain_proof") or f.get("tx_hash") or f.get("execution_id")
    )
    yield _emit({
        "phase":         "anchor",
        "status":        "done",
        "anchored":      anchored_count,
        "total":         len(anchored_findings),
    })

    # ── Phase 6 — Report ─────────────────────────────────────────────────────
    yield _emit({"phase": "report", "status": "start",
                 "msg": "Building enriched report + ENS certificate check..."})
    report_task = asyncio.create_task(
        run_report(
            scope=scope,
            slither_data=slither_data,
            inventory_data=inventory_data,
            triage_data=triage_data,
            investigation_data=investigation_data,
            target_address=target_address or (path if path.startswith("0x") else None),
        )
    )
    async for hb in _heartbeat_while(report_task, "report", "Building report"):
        yield hb
    report = await report_task

    # ── Payload final — strict equivalent des routes non-stream ──────────────
    full_result: dict[str, Any] = {
        "status":        "success",
        "scope": {
            "files_found": len(scope.files),
            "is_onchain":  scope.is_onchain,
            "upstream":    scope.upstream.name if scope.upstream else None,
        },
        "inventory":     inventory_data,
        "slither":       slither_data,
        "triage":        triage_data,
        "investigation": investigation_data,
        "report":        report,
    }

    yield _emit({
        "phase":      "report",
        "status":     "done",
        "verdict":    report.get("verdict"),
        "risk_score": report.get("risk_score"),
        "summary":    report.get("summary", {}),
        "result":     full_result,
    })

    # ── Pipeline complete ────────────────────────────────────────────────────
    yield _emit({"phase": "pipeline", "status": "done"})
