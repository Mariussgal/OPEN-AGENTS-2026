"""
Onchor.ai — CLI.

UX terminal construite sur `click` + `rich` pour un rendu propre :
logo ASCII, panels de verdict, tableau des findings, spinners pendant l'audit.
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parent
_KEEPER_HOME_ENV = Path.home() / ".onchor-ai" / ".env"
_PROJECT_USER_ENV = Path.cwd() / ".env.user"
_BACKEND_USER_ENV = _REPO_ROOT / ".env.user"

load_dotenv(_REPO_ROOT / ".env")
load_dotenv(_KEEPER_HOME_ENV, override=True)
load_dotenv(_BACKEND_USER_ENV, override=True)
load_dotenv(_PROJECT_USER_ENV, override=True)
load_dotenv()

# rich-click : panels, couleurs — aligné sur la palette ui.py (brand / accent / rule).
from rich_click import rich_click as _rch

_rch.COLOR_SYSTEM = "auto"
_rch.USE_CLICK_SHORT_HELP = True
_rch.SHOW_USAGE = True
_rch.COMMANDS_PANEL_TITLE = "Commandes disponibles"
_rch.OPTIONS_PANEL_TITLE = "Options"
_rch.STYLE_COMMAND = "bold #00E0B8"
_rch.STYLE_OPTION = "cyan"
_rch.STYLE_OPTION_HELP = "dim"
_rch.STYLE_USAGE = "dim bold"
_rch.STYLE_HELPTEXT = "white"
_rch.STYLE_EPILOG_TEXT = "dim"
_rch.STYLE_COMMANDS_PANEL_BORDER = "#3A3358"
_rch.STYLE_OPTIONS_PANEL_BORDER = "#3A3358"
_rch.STYLE_COMMANDS_TABLE_BORDER_STYLE = "#3A3358"
_rch.MAX_WIDTH = 120

import rich_click as click
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

API_URL        = "http://localhost:8000"
CONFIG_DIR     = ".onchor"
CONFIG_LEGACY  = os.path.join(CONFIG_DIR, "config.json")
CONFIG_USER    = os.path.join(str(Path.home()), ".onchor-ai", "config.json")


def _should_run_onboarding() -> bool:
    if os.getenv("ONCHOR_SKIP_ONBOARDING", "").strip().lower() in ("1", "true", "yes"):
        return False
    av = sys.argv[1:]
    if len(av) >= 1 and av[0] == "doctor":
        return False
    if len(av) >= 1 and av[0] == "status":
        return False
    if "--help" in av or "-h" in av:
        return False
    try:
        from onboarding import needs_first_run_onboarding

        return needs_first_run_onboarding()
    except Exception:
        return False


def _config_read_paths() -> list[str]:
    return [CONFIG_USER, CONFIG_LEGACY]


def _pick_config_write_path() -> str:
    if os.path.isfile(CONFIG_USER):
        return CONFIG_USER
    if os.path.isfile(CONFIG_LEGACY):
        return CONFIG_LEGACY
    return CONFIG_USER


def _normalize_audit_path(path: str) -> str:
    """
    Chemins relatifs envoyés au serveur seraient résolus depuis le CWD du serveur (souvent
    backend/) — ce qui fausse ``contracts/foo.sol``. Pour les fichiers/répertoires locaux,
    on passe un chemin absolu.
    """
    p = path.strip()
    if p.startswith("0x"):
        return p
    return os.path.abspath(os.path.expanduser(p))


# ─── Config helpers ────────────────────────────────────────────────────────────
def load_config() -> dict[str, Any]:
    for path in _config_read_paths():
        if os.path.exists(path):
            with open(path, "r") as f:
                config = json.load(f)
                config.setdefault("credit_usdc", 0.0)
                return config
    return {"version": "0.1.0", "mode": "local", "credit_usdc": 0.0}


def save_config(config: dict[str, Any]) -> None:
    path = _pick_config_write_path()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(config, f, indent=2)


# ─── CLI ───────────────────────────────────────────────────────────────────────
@click.group(
    invoke_without_command=True,
    context_settings={"help_option_names": ["-h", "--help"]},
    epilog=(
        "\nExemples rapides :\n\n"
        "  onchor-ai doctor       valider les clés et les APIs réseau (sans tout l’assistant)\n\n"
        "  onchor-ai audit .      audit d’un dossier ou fichier Solidity local\n\n"
        "  onchor-ai audit 0x…    audit d’un contrat vérifié (Etherscan)\n\n"
        "  onchor-ai status       solde USDC, wallet et mode serveur local\n\n"
        "Au premier lancement sans ~/.onchor-ai/config.json : l’assistant s’affiche.\n\n"
        "Contourner ponctuellement : ONCHOR_SKIP_ONBOARDING=1\n\n"
        "Options détaillées : onchor-ai audit -h ou onchor-ai doctor -h\n"
    ),
)
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
    """Onchor.ai — Solidity Security Copilot avec mémoire collective.

    Audit contracts, paiements USDC testnet (x402), ancrages KeeperHub, patterns 0G.
    Détail et options propres à chaque commande : utilise -h après le nom de la commande.
    """
    if _should_run_onboarding():
        from onboarding import run_onboarding_wizard

        run_onboarding_wizard()
        load_dotenv(_REPO_ROOT / ".env")
        load_dotenv(_KEEPER_HOME_ENV, override=True)
        load_dotenv(_BACKEND_USER_ENV, override=True)
        load_dotenv(_PROJECT_USER_ENV, override=True)
        load_dotenv(override=True)

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
                    "onchor-ai doctor":      "Valide uniquement les clés / RPC (sans assistant)",
                },
            )
        )


@cli.command(
    "doctor",
    short_help="Vérifier clés & connexions réseau (~/.onchor-ai ou .env).",
)
def doctor_cmd() -> None:
    """Re-valide connexions et clés (équivalent étape 7) sans assistant ni nouveau portefeuille."""
    from onboarding import run_doctor_validation

    if not run_doctor_validation():
        raise click.Exit(code=1)


@cli.command(short_help="Initialiser le dossier projet .onchor/ (config locale).")
def init() -> None:
    """Initialise le dossier de configuration Onchor.ai."""
    section("Initialisation")
    if not os.path.exists(CONFIG_DIR):
        save_config({"version": "0.1.0", "mode": "local", "credit_usdc": 0.0})
        success(f"Projet initialisé — dossier [accent]{CONFIG_DIR}/[/accent] créé.")
    else:
        warn(f"Le dossier [accent]{CONFIG_DIR}/[/accent] existe déjà — rien à faire.")


@cli.command(short_help="Afficher mode, version, solde USDC côté serveur local.")
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


@cli.command(
    short_help="Auditer fichier, dossier ou adresse 0x (contrat vérifié).",
    help=(
        "Lance un audit sur un fichier, un répertoire ou une adresse 0x. "
        "Modes : payant (USDC x402 sur Base Sepolia), --local (sans paiement) ou --dev."
    ),
)
@click.argument("path")
@click.option("--local", is_flag=True, help="Mode local — gratuit, pas de paiement.")
@click.option("--dev",   is_flag=True, help="Mode dev — bypass total.")
@click.option(
    "--no-stream",
    is_flag=True,
    help="Désactive le streaming des phases (legacy, single POST + spinner).",
)
def audit(path: str, local: bool, dev: bool, no_stream: bool) -> None:
    path = _normalize_audit_path(path)
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
        data, payment_tx = asyncio.run(
            _run_audit_async(path, local=local, dev=dev, stream=not no_stream)
        )

        success("Audit terminé.")
        _render_audit_result(data, payment_tx)

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
) -> tuple[dict[str, Any], str | None]:
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
                return resp.json(), None

    # Mode paid.
    if stream:
        from payments.x402_client import prepare_x_payment
        from streaming_client import run_streaming_paid_audit
        x_payment, _price, _nb = await prepare_x_payment(API_URL, path)
        return await run_streaming_paid_audit(API_URL, path, x_payment)

    # Legacy paid — POST unique vers /audit.
    from payments.x402_client import run_paid_audit
    return await run_paid_audit(API_URL, path), None


# ─── Rendu du résultat ─────────────────────────────────────────────────────────

def _render_audit_result(data: dict[str, Any], payment_tx: str | None = None) -> None:
    """Affiche le rendu complet : verdict → findings → rapport Phase 6 → JSON brut."""

    report        = data.get("report") or {}
    investigation = data.get("investigation") or {}
    triage        = data.get("triage") or {}
    findings      = report.get("findings") or []
    onchain       = report.get("onchain") or {}

    if payment_tx:
        report["payment_tx"] = payment_tx

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
    if findings:
        section(f"Findings ({len(findings)})")
        console.print(_enriched_findings_table(findings))

        # Détail par finding (fix_sketch + prior_audit_ref + onchain_proof)
        _render_finding_details(findings)
    else:
        # Fallback sur les findings Slither bruts
        raw_findings = investigation.get("findings") or data.get("slither", {}).get("findings") or []
        if raw_findings:
            section(f"Findings ({len(raw_findings)})")
            console.print(findings_table(raw_findings))
        else:
            info("Aucun finding détecté.")

    # ── Preuves onchain ───────────────────────────────────────────────────────
    if onchain:
        _render_onchain_section(onchain, findings, report)

    # ── Badge ENS ─────────────────────────────────────────────────────────────
    if report.get("ens"):
        _render_ens_badge(
            report.get("ens") or {},
            report.get("report_hash"),
            report_verdict=report.get("verdict"),
        )

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
        anchored_ok = bool(f.get("onchain_proof") or f.get("keeperhub_execution_id"))
        anchored  = "✔" if anchored_ok else "—"
        anchor_style = "ok" if anchored_ok else "muted"

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

        # Preuve KeeperHub / EVM
        if f.get("onchain_proof"):
            etherscan = f"https://sepolia.etherscan.io/tx/{f['onchain_proof']}"
            lines.append("")
            lines.append(f"[label]Tx onchain :[/label] [info]{etherscan}[/info]")
        elif f.get("keeperhub_execution_id"):
            lines.append("")
            lines.append(
                f"[label]Ancrage KeeperHub (réf. exécution, tx en cours ou hors format EVM) :[/label] "
                f"[muted]{f['keeperhub_execution_id']}[/muted]"
            )

        body = Text.from_markup("\n".join(lines))
        console.print(
            Panel(
                body,
                title=f"[{sev_style}]{fid} · {title}[/{sev_style}]",
                border_style=sev_style,
                padding=(0, 1),
            )
        )


def is_valid_proof(tx: str) -> bool:
    """True si tx est un hash EVM non-nul exploitable pour Etherscan."""
    if not tx or not tx.startswith("0x"):
        return False
    if tx == "0x" + "0" * 64:
        return False
    return len(tx) == 66


def _render_onchain_section(onchain: dict, findings: list[dict], report: dict) -> None:
    section("Preuves onchain")

    etherscan_tx      = "https://sepolia.etherscan.io/tx/"
    etherscan_address = "https://sepolia.etherscan.io/address/"
    basescan_tx       = "https://sepolia.basescan.org/tx/"

    items: dict[str, str] = {
        "Anchor Registry":   f"{etherscan_address}{onchain.get('anchor_registry', '')}",
        "Network (anchor)":  "Ethereum Sepolia",
        "Network (payment)": "Base Sepolia",
    }

    anchored = [
        f for f in findings
        if f.get("onchain_proof") or f.get("keeperhub_execution_id")
    ]
    for i, f in enumerate(anchored[:5], 1):
        fid  = f.get("id", "")
        ph   = f.get("pattern_hash", "")
        root = f.get("root_hash", "")

        # Anchor tx — vrai lien Etherscan si disponible
        if f.get("onchain_proof") and is_valid_proof(f["onchain_proof"]):
            items[f"Anchor #{i} ({fid})"] = (
                f"{etherscan_tx}{f['onchain_proof']}"
            )
        else:
            # Pas encore miné — lien contrat + pattern_hash pour vérif manuelle
            items[f"Anchor #{i} ({fid})"] = (
                f"{etherscan_address}{onchain.get('anchor_registry', '')}#readContract"
            )
            if ph:
                items[f"  pattern_hash ({fid})"] = ph

        # 0G rootHash
        if root and is_valid_proof(root):
            items[f"0G root #{i} ({fid})"] = root
            items[f"  → verify ({fid})"] = f"node 0g/0g_download.js {root}"

    # ENS mint tx
    ens = report.get("ens") or {}
    if ens.get("mint_tx") and is_valid_proof(ens["mint_tx"]):
        items["ENS mint tx"] = f"{etherscan_tx}{ens['mint_tx']}"

    # Payment USDC
    payment_tx = report.get("payment_tx")
    if payment_tx and is_valid_proof(payment_tx):
        items["Payment USDC"] = f"{basescan_tx}{payment_tx}"

    if items:
        console.print(kv_panel("Preuves onchain", items))


def _render_ens_badge(
    ens: dict,
    report_hash: str | None = None,
    report_verdict: str | None = None,
) -> None:
    section("Certificat ENS")

    ENS_SEPOLIA_BASE = "https://sepolia.app.ens.domains/"

    mint_ok = ens.get("certified") and ens.get("subname")
    verdict_ok = (report_verdict or "").upper() == "CERTIFIED"

    if mint_ok:
        subname = ens["subname"]
        verdict_display = report_verdict or "CERTIFIED"
        items = {
            "ENS Sepolia": f"{ENS_SEPOLIA_BASE}{subname}",
            "Domaine parent": ens.get("parent", "certified.onchor-ai.eth"),
        }
        if report_hash:
            items["Report hash"] = report_hash

        body = Text.from_markup(
            f"[ok]🏅  {verdict_display} — {subname}[/ok]\n\n"
            + "\n".join(
                f"[label]{k} :[/label] [info]{v}[/info]"
                for k, v in items.items()
            )
        )
        console.print(Panel(
            body,
            title="[brand]ENS Certificate[/brand]",
            border_style="ok",
            padding=(1, 2),
        ))

    elif verdict_ok and not mint_ok:
        body = Text.from_markup(
            "[warn]⚠  CERTIFIED — certificat ENS non émis[/warn]\n\n"
            "[muted]Le pipeline n'a détecté aucun finding HIGH.\n"
            "Le mint ENS a échoué (réseau Sepolia ou configuration).\n"
            "Relancez avec --dev pour re-tenter le mint.[/muted]"
        )
        if report_hash:
            body = Text.from_markup(
                "[warn]⚠  CERTIFIED — certificat ENS non émis[/warn]\n\n"
                f"[label]Report hash :[/label] [info]{report_hash}[/info]\n\n"
                "[muted]Mint ENS échoué — vérifiez ALCHEMY_API_KEY et PRIVATE_KEY "
                "dans contracts/.env[/muted]"
            )
        console.print(Panel(
            body,
            title="[brand]ENS Certificate[/brand]",
            border_style="warn",
            padding=(1, 2),
        ))

    else:
        body = Text.from_markup(
            "[danger]✘  Non certifié — findings HIGH détectés[/danger]\n\n"
            "[muted]Le certificat ENS est émis uniquement lorsqu'aucun finding "
            "HIGH n'est détecté.\nCorrigez les findings et relancez l'audit.[/muted]"
        )
        console.print(Panel(
            body,
            title="[brand]ENS Certificate[/brand]",
            border_style="danger",
            padding=(1, 2),
        ))
        # Pas de lien — rien n'a été minté, un lien serait trompeur


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