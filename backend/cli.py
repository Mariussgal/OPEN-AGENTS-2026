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
)

API_URL = "http://localhost:8000"
CONFIG_DIR = ".onchor"
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")


# ─── Config helpers ────────────────────────────────────────────────────────────
def load_config() -> dict[str, Any]:
    """Charge la configuration et le solde de l'utilisateur."""
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as f:
            config = json.load(f)
            config.setdefault("credit_usdc", 0.0)
            return config
    return {"version": "0.1.0", "mode": "local", "credit_usdc": 0.0}


def save_config(config: dict[str, Any]) -> None:
    """Sauvegarde la configuration et le nouveau solde."""
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
    help="Taille du logo iconique (Onchor seal).",
)
@click.option("--minimal", is_flag=True, help="Alias de --icon-size none (banner sans icône).")
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
                    "onchor-ai init": "Initialise le projet (crée .onchor/config.json)",
                    "onchor-ai audit <path>": "Audit d'un fichier, dossier ou adresse 0x",
                    "onchor-ai status": "Affiche la configuration et le solde",
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
@click.option("--dev", is_flag=True, help="Mode dev — bypass total (x402, anchor, paid memory).")
def audit(path: str, local: bool, dev: bool) -> None:
    """Lance un audit sur un fichier, un répertoire ou une adresse 0x."""
    section(f"Audit · {path}")
    user_config = load_config()

    mode_label = "DEV" if dev else ("LOCAL" if local else "PAID")
    info(f"Mode : [accent]{mode_label}[/accent]")
    
    # Récupération du solde réel pour l'affichage
    address = os.getenv("RECEIVER_ADDRESS")
    if not (local or dev) and address:
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(f"{API_URL}/user/balance", params={"address": address})
                real_balance = resp.json().get("balance", 0.0)
                info(f"Solde disponible : [accent]{real_balance:.2f} USDC[/accent]")
        except Exception:
            pass

    try:
        if local or dev:
            with console.status("[brand]Analyse en cours…[/brand]", spinner="dots"):
                with httpx.Client(timeout=120.0) as client:
                    resp = client.post(f"{API_URL}/audit/local", params={"path": path})
                    resp.raise_for_status()
                    data = resp.json()
        else:
            # Mode PAID : le client x402 demande une confirmation interactive
            # → pas de spinner Rich (il mangerait le prompt). Le client trace
            # déjà sa progression via click.secho.
            from payments.x402_client import run_paid_audit
            data = asyncio.run(run_paid_audit(API_URL, path))

        success("Audit terminé.")
        _render_audit_result(data)

        # ── Opt-in contribution (paid uniquement) ──────────────────────────────
        investigation = data.get("investigation", {}) or {}
        findings = investigation.get("findings") or data.get("slither", {}).get("findings", []) or []

        if findings and not local and not dev:
            _handle_optional_contribution(findings, user_config)

    except click.Abort:
        warn("Audit annulé.")
    except Exception as e:
        error(f"Erreur : {e}")


# ─── Rendu du résultat ─────────────────────────────────────────────────────────
def _render_audit_result(data: dict[str, Any]) -> None:
    """Affiche un rendu structuré du résultat (verdict + findings + JSON brut)."""
    investigation = data.get("investigation") or {}
    triage = data.get("triage") or {}

    verdict = (
        investigation.get("verdict")
        or triage.get("verdict")
        or data.get("verdict")
        or "UNKNOWN"
    )
    risk_score = triage.get("risk_score") or data.get("risk_score")
    if isinstance(risk_score, (int, float)):
        risk_score = float(risk_score)
    else:
        risk_score = None

    section("Verdict")
    console.print(verdict_panel(verdict, risk_score))

    findings = (
        investigation.get("findings")
        or data.get("slither", {}).get("findings")
        or []
    )
    if findings:
        section(f"Findings ({len(findings)})")
        console.print(findings_table(findings))
    else:
        info("Aucun finding détecté.")

    section("Rapport brut (JSON)")
    console.print_json(data=data)


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
    payable_count = min(len(findings), MAX_REWARDABLE)
    reward = payable_count * 0.05

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
        console.print(
            kv_panel(
                "Récompense",
                {
                    "Patterns payés": str(payable_count),
                    "TX hash": tx_hash or "—",
                    "Nouveau solde": f"{user_config['credit_usdc']:.2f} USDC",
                },
            )
        )
    except Exception as e:
        error(f"Erreur lors du paiement : {e}")


if __name__ == "__main__":
    cli()
