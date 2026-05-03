"""
Client streaming pour le CLI Onchor.ai.

Consomme les routes NDJSON `/audit/local/stream` et `/audit/stream` du backend
et affiche une progress bar Rich dynamique avec :
- A purple progress bar that turns teal at 100%.
- Un label par phase courante (Phase 0..6).
- Une ligne `> message` muted entre chaque phase pour comprendre ce qui se
  happening on the server side.
- L'event `payment` (mode paid uniquement) est rendu au-dessus de la progress
  bar before starting the pipeline.

Le payload final (l'event `{"phase": "report", "status": "done", "result": ...}`)
is returned to the caller so it can render verdict / findings /
le JSON brut comme avant — strict equivalent des routes non-stream.
"""

from __future__ import annotations

import json
import os
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Optional

import httpx
from rich.progress import (
    BarColumn,
    Progress,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)

# IMPORTANT — import from `pipeline.phases` (lightweight module, zero
# heavy dependency) and ESPECIALLY not from `pipeline.streaming`, which would load
# Cognee, Slither, Anthropic, etc. at CLI startup and pollute
# the terminal with initialization logs from those libs.
from pipeline.phases import PIPELINE_PHASES
from ui import console, info


# ─── Phase formatting ────────────────────────────────────────────────────────

# Map phase id -> (index, label) to compute progress.
_PHASE_INDEX = {pid: i for i, (pid, _) in enumerate(PIPELINE_PHASES)}
_PHASE_LABEL = {pid: label for pid, label in PIPELINE_PHASES}


def _summary_for_done(event: dict[str, Any]) -> str:
    """Build a short teal summary after phase `done` event."""
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
    files: Optional[dict[str, Any]] = None,
    show_payment: bool = False,
) -> tuple[dict[str, Any], str | None]:
    """Open an NDJSON stream on `url` and render the progress bar.

    Args:
        client: httpx AsyncClient (long timeout recommended, e.g. 600s).
        method: usually "POST".
        url: Full streaming route URL.
        params: Query string params.
        headers: Headers (X-PAYMENT for paid mode).
        files: Multipart body (e.g. file upload) — mutually exclusive with params by caller convention.
        show_payment: If True, show `phase: payment` events above
            the progress bar (paid mode only, after x402 settlement).

    Returns:
        Tuple ``(result, payment_tx)``: ``result`` is the final payload extracted from
        event ``{"phase": "report", "status": "done"}``; ``payment_tx`` is the
        x402 settlement hash from ``{"phase": "payment", "status": "done"}`` when present.

    Raises RuntimeError if the stream ends without payload.
    """
    full_result: dict[str, Any] | None = None
    payment_tx: str | None = None
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
        transient=False,  # keep progress bar visible when finished
    )

    with progress:
        task_id = progress.add_task("Initializing pipeline…", total=total_phases)

        req_kw: dict[str, Any] = {}
        if params is not None:
            req_kw["params"] = params
        if headers is not None:
            req_kw["headers"] = headers
        if files is not None:
            req_kw["files"] = files
        async with client.stream(method, url, **req_kw) as resp:
            # If server returned 4xx/5xx before streaming, read body
            # and raise an explicit exception.
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
                    # Malformed line (proxy timeout, etc.) — skip.
                    continue

                phase = event.get("phase")
                status = event.get("status")

                # -- "payment" event (paid mode only) --
                if phase == "payment":
                    if status == "done":
                        tx_cap = event.get("tx_hash")
                        if tx_cap:
                            payment_tx = str(tx_cap).strip()
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

                # -- "pipeline done" event (final sentinel) --
                if phase == "pipeline" and status == "done":
                    progress.update(task_id, completed=total_phases,
                                    description="Pipeline complete")
                    continue

                # -- "phase X" events --
                if phase not in _PHASE_INDEX:
                    continue

                idx = _PHASE_INDEX[phase]
                label = _PHASE_LABEL[phase]

                if status == "start":
                    progress.update(task_id, description=label, completed=idx)
                    msg = event.get("msg")
                    if msg:
                        console.print(f"  [muted]> {msg}[/muted]")

                elif status == "pulse":
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
        raise RuntimeError("Stream ended without final report payload.")
    return full_result, payment_tx


# ─── High-level helpers (used from cli.py) ────────────────────────────────────

async def run_streaming_audit_local(api_url: str, path: str) -> tuple[dict[str, Any], str | None]:
    """Run a --local audit in streaming mode and return final payload + payment tx if present."""
    info("Pipeline started — see progress below.")
    # Long reads (Phase 4 agent) without cutting connection: high read, reasonable connect.
    tout = httpx.Timeout(connect=60.0, read=7200.0, write=60.0, pool=7200.0)
    async with httpx.AsyncClient(timeout=tout) as client:
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
) -> tuple[dict[str, Any], str | None]:
    """Run a paid audit in streaming mode and return final payload + payment tx if present.

    X-PAYMENT header is already built by caller (see x402_client.py).
    """
    info("Pipeline started — see progress below.")
    tout = httpx.Timeout(connect=60.0, read=7200.0, write=60.0, pool=7200.0)
    async with httpx.AsyncClient(timeout=tout) as client:
        return await consume_audit_stream(
            client,
            "POST",
            f"{api_url}/audit/stream",
            params={"path": path},
            headers={"X-PAYMENT": x_payment_header},
            show_payment=True,
        )


async def run_streaming_paid_upload(
    api_url: str,
    path: str,
    x_payment_header: str,
) -> tuple[dict[str, Any], str | None]:
    """Paid audit of local file/folder via NDJSON (/audit/upload/stream)."""
    info("Pipeline started — see progress below.")
    tout = httpx.Timeout(connect=60.0, read=7200.0, write=60.0, pool=7200.0)
    url = f"{api_url}/audit/upload/stream"
    headers = {"X-PAYMENT": x_payment_header}

    async with httpx.AsyncClient(timeout=tout) as client:
        if os.path.isfile(path):
            with open(path, "rb") as f:
                return await consume_audit_stream(
                    client,
                    "POST",
                    url,
                    files={"file": (os.path.basename(path), f, "text/plain")},
                    headers=headers,
                    show_payment=True,
                )

        if os.path.isdir(path):
            sol_files = list(Path(path).rglob("*.sol"))
            if not sol_files:
                raise ValueError(f"No .sol file found in {path}")

            info(f"{len(sol_files)} .sol files found, compressing...")
            with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp_zip:
                zip_path = tmp_zip.name
            try:
                with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                    for sol in sol_files:
                        zf.write(sol, sol.relative_to(path))
                with open(zip_path, "rb") as f:
                    return await consume_audit_stream(
                        client,
                        "POST",
                        url,
                        files={"file": (os.path.basename(path) + ".zip", f, "application/zip")},
                        headers=headers,
                        show_payment=True,
                    )
            finally:
                os.unlink(zip_path)

    raise ValueError(f"Chemin invalide: {path}")
