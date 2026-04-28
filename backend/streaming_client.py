"""
Client streaming pour le CLI Onchor.ai.

Consomme les routes NDJSON `/audit/local/stream` et `/audit/stream` du backend
et affiche une progress bar Rich dynamique avec :
- Une barre de progression violette qui passe en teal à 100 %.
- Un label par phase courante (Phase 0..6).
- Une ligne `> message` muted entre chaque phase pour comprendre ce qui se
  passe côté serveur.
- L'event `payment` (mode paid uniquement) est rendu au-dessus de la progress
  bar avant de démarrer le pipeline.

Le payload final (l'event `{"phase": "report", "status": "done", "result": ...}`)
est retourné à l'appelant pour qu'il puisse rendre le verdict / les findings /
le JSON brut comme avant — strict equivalent des routes non-stream.
"""

from __future__ import annotations

import json
from typing import Any, Optional

import httpx
from rich.progress import (
    BarColumn,
    Progress,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)

# IMPORTANT — on importe depuis `pipeline.phases` (module léger, zéro
# dépendance lourde) et SURTOUT pas depuis `pipeline.streaming` qui chargerait
# Cognee, Slither, Anthropic, etc. au démarrage du CLI et polluerait le
# terminal avec les logs d'init de ces libs.
from pipeline.phases import PIPELINE_PHASES
from ui import console, info


# ─── Phase formatting ────────────────────────────────────────────────────────

# Map phase id → (index, label) pour calculer la progression.
_PHASE_INDEX = {pid: i for i, (pid, _) in enumerate(PIPELINE_PHASES)}
_PHASE_LABEL = {pid: label for pid, label in PIPELINE_PHASES}


def _summary_for_done(event: dict[str, Any]) -> str:
    """Construit un petit résumé teal après le `done` d'une phase."""
    phase = event.get("phase")

    if phase == "resolve":
        files = event.get("files", 0)
        upstream = event.get("upstream")
        bits = [f"{files} file(s)"]
        if upstream:
            bits.append(f"upstream: {upstream}")
        else:
            bits.append("no upstream fork")
        return "  ·  ".join(bits)

    if phase == "inventory":
        flags = event.get("known_findings", 0)
        dups = event.get("duplicates", 0)
        return f"{event.get('files_analyzed', 0)} file(s)  ·  {flags} known finding(s)  ·  {dups} dup(s)"

    if phase == "slither":
        return f"{event.get('findings', 0)} finding(s) · slither {'OK' if event.get('success') else 'failed'}"

    if phase == "triage":
        score = event.get("risk_score")
        verdict = event.get("verdict")
        if score is None:
            return f"verdict: {verdict}"
        return f"risk score: {score} / 10  ·  {verdict}"

    if phase == "investigate":
        n = event.get("findings_count", 0)
        turns = event.get("turns_used")
        model = event.get("model", "")
        bits = [f"{n} finding(s)"]
        if turns is not None:
            bits.append(f"{turns} turn(s)")
        if model:
            bits.append(model.split("/")[-1])
        return "  ·  ".join(bits)

    if phase == "anchor":
        return f"{event.get('anchored', 0)} / {event.get('total', 0)} anchored onchain"

    if phase == "report":
        verdict = event.get("verdict")
        score = event.get("risk_score")
        if verdict and score is not None:
            return f"verdict: {verdict}  ·  risk score: {score} / 10"
        if verdict:
            return f"verdict: {verdict}"
        return "report ready"

    return ""


# ─── Streaming consumer ──────────────────────────────────────────────────────

async def consume_audit_stream(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    params: Optional[dict[str, Any]] = None,
    headers: Optional[dict[str, str]] = None,
    show_payment: bool = False,
) -> dict[str, Any]:
    """Ouvre un stream NDJSON sur `url` et affiche la progress bar.

    Args:
        client: AsyncClient httpx (timeout long recommandé, p.ex. 600s).
        method: "POST" en pratique.
        url: URL complète de la route streaming.
        params: Query string params.
        headers: Headers (X-PAYMENT pour le mode paid).
        show_payment: Si True, affiche les events `phase: payment` au-dessus
            de la progress bar (uniquement le mode paid après le settle x402).

    Returns:
        Le `result` final extrait de l'event `{"phase": "report", "status": "done"}`.
        Lève RuntimeError si le stream se termine sans payload.
    """
    full_result: dict[str, Any] | None = None
    total_phases = len(PIPELINE_PHASES)

    progress = Progress(
        TextColumn("  [brand]{task.description}[/brand]"),
        BarColumn(
            bar_width=30,
            complete_style="brand",
            finished_style="ok",
            pulse_style="brand.dim",
        ),
        TaskProgressColumn(),
        TextColumn("[muted]·[/muted]"),
        TimeElapsedColumn(),
        console=console,
        transient=False,  # garde la barre visible une fois finie
    )

    with progress:
        task_id = progress.add_task("Initializing pipeline…", total=total_phases)

        async with client.stream(method, url, params=params, headers=headers) as resp:
            # Si le serveur a répondu en 4xx/5xx avant de streamer, lit le body
            # complet et lève une exception explicite.
            if resp.status_code >= 400:
                body = (await resp.aread()).decode("utf-8", errors="replace")
                raise httpx.HTTPStatusError(
                    f"{resp.status_code} — {body[:400]}",
                    request=resp.request,
                    response=resp,
                )

            async for line in resp.aiter_lines():
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    # Ligne cassée (timeout proxy, etc.) — skip.
                    continue

                phase = event.get("phase")
                status = event.get("status")

                # ── Event "payment" (mode paid uniquement) ───────────────────
                if phase == "payment":
                    if not show_payment:
                        continue
                    if status == "start":
                        msg = event.get("msg", "Settling payment…")
                        progress.update(task_id, description=f"x402 · {msg}")
                    elif status == "done":
                        tx = event.get("tx_hash", "")
                        amount = event.get("amount_usd")
                        amount_str = f"{amount:.2f} USDC" if amount else "USDC"
                        console.print(
                            f"  [ok]✓[/ok]  Payment settled  ·  [accent]{amount_str}[/accent]  "
                            f"·  [muted]tx: {tx[:14]}…[/muted]"
                        )
                    elif status == "fail":
                        err = event.get("error", "unknown")
                        console.print(f"  [danger]✘  Payment failed: {err}[/danger]")
                        raise RuntimeError(f"Payment failed: {err}")
                    continue

                # ── Event "pipeline done" (sentinelle finale) ────────────────
                if phase == "pipeline" and status == "done":
                    progress.update(task_id, completed=total_phases,
                                    description="Pipeline complete")
                    continue

                # ── Events "phase X" ─────────────────────────────────────────
                if phase not in _PHASE_INDEX:
                    continue

                idx = _PHASE_INDEX[phase]
                label = _PHASE_LABEL[phase]

                if status == "start":
                    progress.update(task_id, description=label, completed=idx)
                    msg = event.get("msg")
                    if msg:
                        console.print(f"  [muted]> {msg}[/muted]")

                elif status == "done":
                    progress.update(task_id, completed=idx + 1)
                    summary = _summary_for_done(event)
                    if summary:
                        console.print(f"  [accent]✓[/accent]  {label}  [muted]·  {summary}[/muted]")
                    if phase == "report":
                        full_result = event.get("result")

    if full_result is None:
        raise RuntimeError("Stream terminé sans payload de rapport final.")
    return full_result


# ─── Helpers de plus haut niveau (utilisés depuis cli.py) ────────────────────

async def run_streaming_audit_local(api_url: str, path: str) -> dict[str, Any]:
    """Lance un audit --local en streaming et retourne le payload final."""
    info("Pipeline démarré — voir progression ci-dessous.")
    async with httpx.AsyncClient(timeout=600.0) as client:
        return await consume_audit_stream(
            client,
            "POST",
            f"{api_url}/audit/local/stream",
            params={"path": path},
        )


async def run_streaming_paid_audit(
    api_url: str,
    path: str,
    x_payment_header: str,
) -> dict[str, Any]:
    """Lance un audit paid en streaming et retourne le payload final.

    Le header X-PAYMENT a déjà été construit côté caller (cf. x402_client.py).
    """
    info("Pipeline démarré — voir progression ci-dessous.")
    async with httpx.AsyncClient(timeout=600.0) as client:
        return await consume_audit_stream(
            client,
            "POST",
            f"{api_url}/audit/stream",
            params={"path": path},
            headers={"X-PAYMENT": x_payment_header},
            show_payment=True,
        )
