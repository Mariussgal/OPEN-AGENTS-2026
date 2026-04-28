"""
Onchor.ai — CLI.

UX terminal construite sur `click` + `rich` pour un rendu propre :
logo ASCII, panels de verdict, tableau des findings, spinners pendant l'audit.
"""

import asyncio
import json
import os
from typing import Any

from dotenv import load_dotenv
load_dotenv()

import click
import httpx
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ui import (
    console,
    error,
    findings_table,
    info,
    kv_panel,
    section,
    show_banner,
    success,
    verdict_panel,
    warn,
    SEVERITY_STYLES,
)

API_URL     = "http://localhost:8000"
CONFIG_DIR  = ".onchor"
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")


# ─── Config helpers ────────────────────────────────────────────────────────────
def load_config() -> dict[str, Any]:
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as f:
            config = json.load(f)
            config.setdefault("credit_usdc", 0.0)
            return config
    return {"version": "0.1.0", "mode": "local", "credit_usdc": 0.0}


def save_config(config: dict[str, Any]) -> None:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


# ─── CLI ───────────────────────────────────────────────────────────────────────
@click.group(invoke_without_command=True)
@click.option("--no-banner", is_flag=True, help="Masque la bannière de démarrage.")
@click.option(
    "--icon-size",
    type=click.Choice(["none", "small", "medium", "large"], case_sensitive=False),
    default="medium",
    show_default=True,
)
@click.option("--minimal", is_flag=True, help="Alias de --icon-size none.")
@click.pass_context
def cli(ctx: click.Context, no_banner: bool, icon_size: str, minimal: bool) -> None:
    """Onchor.ai — Solidity Security Copilot with Persistent Collective Memory."""
    if not no_banner:
        size = "none" if minimal else icon_size.lower()
        show_banner(icon_size=size)

    if ctx.invoked_subcommand is None:
        console.print()
        info("Tape [accent]onchor-ai --help[/accent] pour voir les commandes disponibles.")
        console.print(
            kv_panel(
                "Commandes disponibles",
                {
                    "onchor-ai init":         "Initialise le projet",
                    "onchor-ai audit <path>": "Audit d'un fichier, dossier ou adresse 0x",
                    "onchor-ai status":       "Configuration et solde",
                },
            )
        )


@cli.command()
def init() -> None:
    """Initialise le dossier de configuration Onchor.ai."""
    section("Initialisation")
    if not os.path.exists(CONFIG_DIR):
        save_config({"version": "0.1.0", "mode": "local", "credit_usdc": 0.0})
        success(f"Projet initialisé — dossier [accent]{CONFIG_DIR}/[/accent] créé.")
    else:
        warn(f"Le dossier [accent]{CONFIG_DIR}/[/accent] existe déjà — rien à faire.")


@cli.command()
def status() -> None:
    """Affiche la configuration et le solde courant (réel)."""
    section("Status")
    cfg = load_config()
    
    # Récupération du solde réel via le serveur
    address = os.getenv("RECEIVER_ADDRESS")
    real_balance = 0.0
    if address:
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(f"{API_URL}/user/balance", params={"address": address})
                real_balance = resp.json().get("balance", 0.0)
        except Exception:
            real_balance = cfg.get("credit_usdc", 0.0) # Fallback

    console.print(
        kv_panel(
            "Profil Onchor.ai",
            {
                "Version": cfg.get("version", "?"),
                "Mode": cfg.get("mode", "?"),
                "Solde USDC (Réel)": f"{real_balance:.2f} USDC",
                "Adresse Wallet": address or "Non configurée",
                "API URL": API_URL,
            },
        )
    )


@cli.command()
@click.argument("path")
@click.option("--local", is_flag=True, help="Mode local — gratuit, pas de paiement.")
@click.option("--dev",   is_flag=True, help="Mode dev — bypass total.")
@click.option(
    "--no-stream",
    is_flag=True,
    help="Désactive le streaming des phases (legacy, single POST + spinner).",
)
def audit(path: str, local: bool, dev: bool, no_stream: bool) -> None:
    """Lance un audit sur un fichier, un répertoire ou une adresse 0x."""
    section(f"Audit · {path}")
    user_config = load_config()

    mode_label = "DEV" if dev else ("LOCAL" if local else "PAID")
    info(f"Mode : [accent]{mode_label}[/accent]")
    
    # Récupération du solde réel pour l'affichage
    address = os.getenv("RECEIVER_ADDRESS")
    real_balance = 0.0
    if not (local or dev) and address:
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(f"{API_URL}/user/balance", params={"address": address})
                real_balance = resp.json().get("balance", 0.0)
                info(f"Solde disponible : [accent]{real_balance:.2f} USDC[/accent]")
        except Exception:
            # Fallback si le serveur est éteint
            real_balance = user_config.get("credit_usdc", 0.0)
            info(f"Solde disponible (cache) : [accent]{real_balance:.2f} USDC[/accent]")

    try:
        data = asyncio.run(_run_audit_async(path, local=local, dev=dev, stream=not no_stream))

        success("Audit terminé.")
        _render_audit_result(data)

        # Opt-in contribution
        investigation = data.get("investigation", {}) or {}
        findings = (
            investigation.get("findings")
            or data.get("slither", {}).get("findings", [])
            or []
        )
        if findings and not local and not dev:
            _handle_optional_contribution(findings, user_config)

    except click.Abort:
        warn("Audit annulé.")
    except Exception as e:
        error(f"Erreur : {e}")


async def _run_audit_async(
    path: str,
    *,
    local: bool,
    dev: bool,
    stream: bool,
) -> dict[str, Any]:
    """Dispatch des 4 combinaisons : local/paid × stream/legacy."""
    if local or dev:
        if stream:
            from streaming_client import run_streaming_audit_local
            return await run_streaming_audit_local(API_URL, path)
        # Legacy — POST unique + spinner.
        with console.status("[brand]Analyse en cours…[/brand]", spinner="dots"):
            async with httpx.AsyncClient(timeout=600.0) as client:
                resp = await client.post(f"{API_URL}/audit/local", params={"path": path})
                resp.raise_for_status()
                return resp.json()

    # Mode paid.
    if stream:
        from payments.x402_client import prepare_x_payment
        from streaming_client import run_streaming_paid_audit
        x_payment, _price, _nb = await prepare_x_payment(API_URL, path)
        return await run_streaming_paid_audit(API_URL, path, x_payment)

    # Legacy paid — POST unique vers /audit.
    from payments.x402_client import run_paid_audit
    return await run_paid_audit(API_URL, path)


# ─── Rendu du résultat ─────────────────────────────────────────────────────────

def _render_audit_result(data: dict[str, Any]) -> None:
    """Affiche le rendu complet : verdict → findings → rapport Phase 6 → JSON brut."""

    report        = data.get("report") or {}
    investigation = data.get("investigation") or {}
    triage        = data.get("triage") or {}

    # ── Verdict ───────────────────────────────────────────────────────────────
    verdict    = (
        report.get("verdict")
        or investigation.get("verdict")
        or triage.get("verdict")
        or data.get("verdict")
        or "UNKNOWN"
    )
    risk_score = report.get("risk_score") or triage.get("risk_score")
    if isinstance(risk_score, (int, float)):
        risk_score = float(risk_score)
    else:
        risk_score = None

    section("Verdict")
    console.print(verdict_panel(verdict, risk_score))

    # ── Summary rapide ────────────────────────────────────────────────────────
    if report.get("summary"):
        s = report["summary"]
        console.print(
            kv_panel(
                "Résumé",
                {
                    "Total findings":  str(s.get("total_findings", 0)),
                    "HIGH":            f"[danger]{s.get('high_count', 0)}[/danger]",
                    "MEDIUM":          f"[warn]{s.get('medium_count', 0)}[/warn]",
                    "LOW":             f"[info]{s.get('low_count', 0)}[/info]",
                    "Anchors onchain": str(s.get("anchored_count", 0)),
                    "Memory hits":     str(report.get("memory", {}).get("hits", 0)),
                },
            )
        )

    # ── Findings enrichis (Phase 6) ───────────────────────────────────────────
    enriched_findings = report.get("findings") or []
    if enriched_findings:
        section(f"Findings ({len(enriched_findings)})")
        console.print(_enriched_findings_table(enriched_findings))

        # Détail par finding (fix_sketch + prior_audit_ref + onchain_proof)
        _render_finding_details(enriched_findings)
    else:
        # Fallback sur les findings Slither bruts
        raw_findings = investigation.get("findings") or data.get("slither", {}).get("findings") or []
        if raw_findings:
            section(f"Findings ({len(raw_findings)})")
            console.print(findings_table(raw_findings))
        else:
            info("Aucun finding détecté.")

    # ── Preuves onchain ───────────────────────────────────────────────────────
    if report.get("onchain"):
        _render_onchain_section(report["onchain"], enriched_findings)

    # ── Badge ENS ─────────────────────────────────────────────────────────────
    if report.get("ens"):
        _render_ens_badge(report["ens"])

    # ── JSON brut ─────────────────────────────────────────────────────────────
    section("Rapport brut (JSON)")
    console.print_json(data=data)


def _enriched_findings_table(findings: list[dict]) -> Table:
    """Tableau enrichi : sev / conf / titre / fichier:ligne / prior_ref."""
    table = Table(
        show_header=True,
        header_style="label",
        border_style="rule",
        expand=True,
    )
    table.add_column("ID",   width=6,  style="muted")
    table.add_column("Sev",  width=8)
    table.add_column("Conf", width=11, style="muted")
    table.add_column("Title",             overflow="fold")
    table.add_column("File:Line",         overflow="fold", style="info")
    table.add_column("⛓ Anchored", width=10, justify="center")

    for f in findings:
        sev       = (f.get("severity") or "INFO").upper()
        sev_style = SEVERITY_STYLES.get(sev, "muted")
        conf      = (f.get("confidence") or "").upper()
        location  = f.get("file", "—")
        if f.get("line"):
            location += f":{f['line']}"
        anchored  = "✔" if f.get("onchain_proof") else "—"
        anchor_style = "ok" if f.get("onchain_proof") else "muted"

        table.add_row(
            f.get("id", "—"),
            f"[{sev_style}]{sev}[/{sev_style}]",
            conf,
            f.get("title", "—"),
            location,
            f"[{anchor_style}]{anchored}[/{anchor_style}]",
        )
    return table


def _render_finding_details(findings: list[dict]) -> None:
    """Affiche le détail de chaque HIGH/MEDIUM : fix_sketch + prior_audit_ref + onchain_proof."""
    notable = [f for f in findings if f.get("severity") in ("HIGH", "MEDIUM")]
    if not notable:
        return

    section("Détails des findings critiques")
    for f in notable:
        sev       = f.get("severity", "INFO").upper()
        sev_style = SEVERITY_STYLES.get(sev, "muted")
        title     = f.get("title", "Unknown")
        fid       = f.get("id", "")

        lines: list[str] = []

        # Description
        if f.get("description"):
            lines.append(f"[label]Description :[/label] {f['description'][:200]}")

        # Fix sketch
        if f.get("fix_sketch"):
            lines.append("")
            lines.append("[label]Fix sketch :[/label]")
            for code_line in f["fix_sketch"].splitlines():
                lines.append(f"  [accent]{code_line}[/accent]")

        # Prior audit reference
        if f.get("prior_audit_ref"):
            lines.append("")
            lines.append(f"[label]Ref. historique :[/label] [muted]{f['prior_audit_ref']}[/muted]")

        # Onchain proof
        if f.get("onchain_proof"):
            etherscan = f"https://sepolia.etherscan.io/tx/{f['onchain_proof']}"
            lines.append("")
            lines.append(f"[label]Preuve onchain :[/label] [info]{etherscan}[/info]")

        body = Text.from_markup("\n".join(lines))
        console.print(
            Panel(
                body,
                title=f"[{sev_style}]{fid} · {title}[/{sev_style}]",
                border_style=sev_style,
                padding=(0, 1),
            )
        )


def _render_onchain_section(onchain: dict, findings: list[dict]) -> None:
    """Affiche le résumé onchain : registry + tx proof + liens Etherscan."""
    section("Preuves onchain (Ethereum Sepolia)")

    etherscan_base = onchain.get("etherscan_base", "https://sepolia.etherscan.io/tx/")
    tx_proof       = onchain.get("tx_proof", "")

    items: dict[str, str] = {
        "Anchor Registry": onchain.get("anchor_registry", "—"),
        "Network":         onchain.get("network", "—"),
    }

    if tx_proof and tx_proof != "0x" + "0" * 64:
        items["TX Proof"] = f"{etherscan_base}{tx_proof}"

    # Lister tous les tx_hash des findings anchored
    anchored = [f for f in findings if f.get("onchain_proof")]
    for i, f in enumerate(anchored[:5], 1):
        items[f"Anchor #{i} ({f.get('id', '')})"] = f"{etherscan_base}{f['onchain_proof']}"
    if len(anchored) > 5:
        items["…"] = f"et {len(anchored) - 5} autre(s) — voir JSON complet"

    if items:
        console.print(kv_panel("Preuves onchain", items))


def _render_ens_badge(ens: dict) -> None:
    """Affiche le badge ENS — CERTIFIED en vert ou NOT CERTIFIED en rouge."""
    section("Certificat ENS")

    if ens.get("certified") and ens.get("subname"):
        badge_style = "ok"
        badge_icon  = "🏅"
        badge_text  = f"CERTIFIED — {ens['subname']}"
    elif ens.get("subname"):
        badge_style = "warn"
        badge_icon  = "⚠"
        badge_text  = f"Findings trouvés — {ens['subname']}"
    else:
        badge_style = "danger"
        badge_icon  = "✘"
        badge_text  = "Non certifié — findings HIGH détectés"

    body = Text.from_markup(f"[{badge_style}]{badge_icon}  {badge_text}[/{badge_style}]")

    items: dict[str, str] = {}
    if ens.get("url"):
        items["ENS URL"] = ens["url"]
    if ens.get("parent"):
        items["Domaine parent"] = ens["parent"]
    if items:
        items_text = "\n".join(f"[label]{k} :[/label] [info]{v}[/info]" for k, v in items.items())
        full_body  = Text.from_markup(f"[{badge_style}]{badge_icon}  {badge_text}[/{badge_style}]\n\n{items_text}")
    else:
        full_body = body

    console.print(
        Panel(
            full_body,
            title="[brand]ENS Certificate[/brand]",
            border_style=badge_style,
            padding=(1, 2),
        )
    )


# ─── Contribution opt-in ───────────────────────────────────────────────────────
def _handle_optional_contribution(findings: list[dict], user_config: dict[str, Any]) -> None:
    section("Contribution mémoire collective")
    info(
        f"[accent]{len(findings)}[/accent] vulnérabilité(s) identifiée(s). "
        "Partager ces patterns ANONYMES à la mémoire collective ?"
    )
    info("Récompense : [accent]0.05 USDC[/accent] par pattern validé (max 3).")

    if not click.confirm("Contribuer ?", default=False):
        warn("Contribution refusée — vos données restent strictement locales.")
        return

    MAX_REWARDABLE = 3
    payable_count  = min(len(findings), MAX_REWARDABLE)
    reward         = payable_count * 0.05

    info(f"Envoi de la récompense ({reward:.2f} USDC) sur Base Sepolia…")
    try:
        contributor_address = os.getenv("RECEIVER_ADDRESS")
        with httpx.Client(timeout=30.0) as client:
            reward_resp = client.post(
                f"{API_URL}/audit/reward",
                params={"contributor_address": contributor_address, "amount": reward},
            )
            reward_resp.raise_for_status()
            tx_hash = reward_resp.json().get("tx")

        user_config["credit_usdc"] += reward
        save_config(user_config)

        success(f"{payable_count} pattern(s) payé(s) on-chain.")
        
        real_balance = user_config["credit_usdc"]
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(f"{API_URL}/user/balance", params={"address": contributor_address})
                real_balance = resp.json().get("balance", real_balance)
        except Exception:
            pass

        console.print(
            kv_panel(
                "Récompense",
                {
                    "Patterns payés": str(payable_count),
                    "TX hash":        tx_hash or "—",
                    "Nouveau solde":  f"{real_balance:.2f} USDC",
                },
            )
        )
    except Exception as e:
        error(f"Erreur lors du paiement : {e}")


if __name__ == "__main__":
    cli()