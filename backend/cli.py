"""
Onchor.ai — CLI.

UX terminal construite sur `click` + `rich` pour un rendu propre :
logo ASCII, panels de verdict, tableau des findings, spinners pendant l'audit.
"""

import asyncio
import json
import os
import sys
import tempfile
import zipfile
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

# rich-click: panels, colors — aligned with ui.py palette (brand / accent / rule).
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

_DEFAULT_LOCAL_API  = "http://localhost:8000"
_DEFAULT_PUBLIC_API = "https://open-agents-2026.onrender.com"
_DEFAULT_APP_URL    = "https://onchor-ai.vercel.app"
_API_URL_CACHE: str | None = None

CONFIG_DIR     = ".onchor"
CONFIG_LEGACY  = os.path.join(CONFIG_DIR, "config.json")
CONFIG_USER    = os.path.join(str(Path.home()), ".onchor-ai", "config.json")


def get_api_url() -> str:
    """Prefer explicit ONCHOR_API_URL; else local backend if reachable; else public Render."""
    global _API_URL_CACHE
    if _API_URL_CACHE is not None:
        return _API_URL_CACHE
    explicit = (os.getenv("ONCHOR_API_URL") or "").strip()
    if explicit:
        _API_URL_CACHE = explicit.rstrip("/")
        return _API_URL_CACHE
    local = _DEFAULT_LOCAL_API.rstrip("/")
    try:
        with httpx.Client(timeout=1.0) as client:
            r = client.get(f"{local}/")
            if r.status_code == 200:
                _API_URL_CACHE = local
                return _API_URL_CACHE
    except Exception:
        pass
    _API_URL_CACHE = _DEFAULT_PUBLIC_API.rstrip("/")
    return _API_URL_CACHE


def get_app_url() -> str:
    """URL du frontend (rapport /audit/[id]). Surcharge via ONCHOR_APP_URL."""
    explicit = (os.getenv("ONCHOR_APP_URL") or "").strip()
    if explicit:
        return explicit.rstrip("/")
    return _DEFAULT_APP_URL.rstrip("/")


def _installed_package_version() -> str:
    """Version du wheel PyPI installée (pas le champ ``version`` du config.json projet)."""
    try:
        from importlib.metadata import PackageNotFoundError, version

        return version("onchor-ai")
    except PackageNotFoundError:
        return "not installed (editable/dev?)"
    except Exception:
        return "?"


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
    Relative paths sent to the server would be resolved from the server CWD (often
    backend/), which breaks ``contracts/foo.sol``. For local files/directories,
    always pass an absolute path.
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
        "\nQuick examples:\n\n"
        "  onchor-ai doctor       validate keys and network APIs (without full onboarding)\n\n"
        "  onchor-ai audit .      audit a local Solidity folder or file\n\n"
        "  onchor-ai audit 0x…    audit a verified contract (Etherscan)\n\n"
        "  onchor-ai status       USDC balance, wallet, and local server mode\n\n"
        "On first run without ~/.onchor-ai/config.json, onboarding is shown.\n\n"
        "Temporary bypass: ONCHOR_SKIP_ONBOARDING=1\n\n"
        "Detailed options: onchor-ai audit -h or onchor-ai doctor -h\n"
    ),
)
@click.option("--no-banner", is_flag=True, help="Hide startup banner.")
@click.option(
    "--icon-size",
    type=click.Choice(["none", "small", "medium", "large"], case_sensitive=False),
    default="medium",
    show_default=True,
)
@click.option("--minimal", is_flag=True, help="Alias for --icon-size none.")
@click.pass_context
def cli(ctx: click.Context, no_banner: bool, icon_size: str, minimal: bool) -> None:
    """Onchor.ai — Solidity Security Copilot with collective memory.

    Audit contracts, testnet USDC payments (x402), KeeperHub anchoring, and 0G patterns.
    Use -h after each command to see detailed options.
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
        info("Run [accent]onchor-ai --help[/accent] to view available commands.")
        console.print(
            kv_panel(
                "Available commands",
                {
                    "onchor-ai init":         "Initialize local project config",
                    "onchor-ai audit <path>": "Audit a file, folder, or 0x address",
                    "onchor-ai status":       "Configuration and balance",
                    "onchor-ai doctor":       "Validate keys / RPC only (no onboarding)",
                },
            )
        )


@cli.command(
    "doctor",
    short_help="Validate keys and network connectivity (~/.onchor-ai or .env).",
)
def doctor_cmd() -> None:
    """Re-validate keys and connectivity (equivalent to step 7) without onboarding."""
    from onboarding import run_doctor_validation

    if not run_doctor_validation():
        raise click.Exit(code=1)


@cli.command(short_help="Initialize .onchor/ project folder (local config).")
def init() -> None:
    """Initialize Onchor.ai project configuration."""
    section("Initialization")
    if not os.path.exists(CONFIG_DIR):
        save_config({"version": "0.1.0", "mode": "local", "credit_usdc": 0.0})
        success(f"Project initialized — [accent]{CONFIG_DIR}/[/accent] created.")
    else:
        warn(f"[accent]{CONFIG_DIR}/[/accent] already exists — nothing to do.")


@cli.command(short_help="Show mode, version, and USDC balance from local server.")
def status() -> None:
    """Display configuration and current (real) balance."""
    section("Status")
    cfg = load_config()
    
    # Fetch real balance from server
    address = os.getenv("RECEIVER_ADDRESS")
    real_balance = 0.0
    if address:
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(f"{get_api_url()}/user/balance", params={"address": address})
                real_balance = resp.json().get("balance", 0.0)
        except Exception:
            real_balance = cfg.get("credit_usdc", 0.0) # Fallback

    console.print(
        kv_panel(
            "Onchor.ai Profile",
            {
                "CLI package": _installed_package_version(),
                "Config file": cfg.get("version", "?"),
                "Mode": cfg.get("mode", "?"),
                "USDC Balance (Real)": f"{real_balance:.2f} USDC",
                "Wallet Address": address or "Not configured",
                "API URL": get_api_url(),
            },
        )
    )


@cli.command(
    short_help="Audit file, folder, or 0x address (verified contract).",
    help=(
        "Run an audit on a file, folder, or 0x address. "
        "Modes: paid (USDC x402 on Base Sepolia), --local (no payment), or --dev."
    ),
)
@click.argument("path")
@click.option("--local", is_flag=True, help="Local mode — free, no payment.")
@click.option("--dev",   is_flag=True, help="Dev mode — full bypass.")
@click.option(
    "--no-stream",
    is_flag=True,
    help="Disable phase streaming (legacy single POST + spinner).",
)
def audit(path: str, local: bool, dev: bool, no_stream: bool) -> None:
    path = _normalize_audit_path(path)
    section(f"Audit · {path}")
    user_config = load_config()

    mode_label = "DEV" if dev else ("LOCAL" if local else "PAID")
    info(f"Mode: [accent]{mode_label}[/accent]")
    
    # Fetch real balance for display
    address = os.getenv("RECEIVER_ADDRESS")
    real_balance = 0.0
    if not (local or dev) and address:
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(f"{get_api_url()}/user/balance", params={"address": address})
                real_balance = resp.json().get("balance", 0.0)
                info(f"Available balance: [accent]{real_balance:.2f} USDC[/accent]")
        except Exception:
            # Fallback when server is unavailable
            real_balance = user_config.get("credit_usdc", 0.0)
            info(f"Available balance (cached): [accent]{real_balance:.2f} USDC[/accent]")

    try:
        data, payment_tx = asyncio.run(
            _run_audit_async(path, local=local, dev=dev, stream=not no_stream)
        )

        success("Audit completed.")
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
        warn("Audit cancelled.")
    except Exception as e:
        error(f"Error: {e}")


async def _upload_and_audit(path: str, *, local: bool, dev: bool, stream: bool = False) -> tuple[dict, str | None]:
    # Mode local/dev → route gratuite, pas de paiement
    if local or dev:
        route = "/audit/local/upload"
        if os.path.isfile(path):
            async with httpx.AsyncClient(timeout=600.0) as client:
                with open(path, "rb") as f:
                    resp = await client.post(
                        f"{get_api_url()}{route}",
                        files={"file": (os.path.basename(path), f, "text/plain")},
                    )
                resp.raise_for_status()
                return resp.json(), None
        if os.path.isdir(path):
            sol_files = list(Path(path).rglob("*.sol"))
            if not sol_files:
                raise click.ClickException(f"Aucun fichier .sol trouvé dans {path}")

            info(f"{len(sol_files)} fichiers .sol trouvés, compression...")
            with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp_zip:
                zip_path = tmp_zip.name
            try:
                with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                    for sol in sol_files:
                        zf.write(sol, sol.relative_to(path))
                async with httpx.AsyncClient(timeout=600.0) as client:
                    with open(zip_path, "rb") as f:
                        resp = await client.post(
                            f"{get_api_url()}{route}",
                            files={"file": (os.path.basename(path) + ".zip", f, "application/zip")},
                        )
                    resp.raise_for_status()
                    return resp.json(), None
            finally:
                os.unlink(zip_path)
        raise click.ClickException(f"Chemin invalide: {path}")

    # Mode paid → préparer x402 d'abord
    from payments.x402_client import prepare_x_payment

    if stream:
        from streaming_client import run_streaming_paid_upload

        x_payment, _, _ = await prepare_x_payment(get_api_url(), "upload-stream")
        try:
            return await run_streaming_paid_upload(get_api_url(), path, x_payment)
        except ValueError as e:
            raise click.ClickException(str(e)) from e

    x_payment, _, _ = await prepare_x_payment(get_api_url(), "upload")

    if os.path.isfile(path):
        async with httpx.AsyncClient(timeout=600.0) as client:
            with open(path, "rb") as f:
                resp = await client.post(
                    f"{get_api_url()}/audit/upload",
                    files={"file": (os.path.basename(path), f, "text/plain")},
                    headers={"X-PAYMENT": x_payment},
                )
            resp.raise_for_status()
            data = resp.json()
            payment_tx = data.get("report", {}).get("payment_tx")
            return data, payment_tx

    if os.path.isdir(path):
        sol_files = list(Path(path).rglob("*.sol"))
        if not sol_files:
            raise click.ClickException(f"Aucun fichier .sol trouvé dans {path}")

        info(f"{len(sol_files)} fichiers .sol trouvés, compression...")
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp_zip:
            zip_path = tmp_zip.name
        try:
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for sol in sol_files:
                    zf.write(sol, sol.relative_to(path))
            async with httpx.AsyncClient(timeout=600.0) as client:
                with open(zip_path, "rb") as f:
                    resp = await client.post(
                        f"{get_api_url()}/audit/upload",
                        files={"file": (os.path.basename(path) + ".zip", f, "application/zip")},
                        headers={"X-PAYMENT": x_payment},
                    )
                resp.raise_for_status()
                data = resp.json()
                payment_tx = data.get("report", {}).get("payment_tx")
                return data, payment_tx
        finally:
            os.unlink(zip_path)

    raise click.ClickException(f"Chemin invalide: {path}")


async def _run_audit_async(
    path: str,
    *,
    local: bool,
    dev: bool,
    stream: bool,
) -> tuple[dict[str, Any], str | None]:
    """Dispatch des 4 combinaisons : local/paid × stream/legacy."""
    # ← AJOUT : fichier local → upload vers Render
    if not path.startswith("0x") and (os.path.isfile(path) or os.path.isdir(path)):
        return await _upload_and_audit(path, local=local, dev=dev, stream=stream)

    if local or dev:
        if stream:
            from streaming_client import run_streaming_audit_local
            return await run_streaming_audit_local(get_api_url(), path)
        # Legacy — POST unique + spinner.
        with console.status("[brand]Analyse en cours…[/brand]", spinner="dots"):
            async with httpx.AsyncClient(timeout=600.0) as client:
                resp = await client.post(f"{get_api_url()}/audit/local", params={"path": path})
                resp.raise_for_status()
                return resp.json(), None

    # Mode paid.
    if stream:
        from payments.x402_client import prepare_x_payment
        from streaming_client import run_streaming_paid_audit
        x_payment, _price, _nb = await prepare_x_payment(get_api_url(), path)
        return await run_streaming_paid_audit(get_api_url(), path, x_payment)

    # Legacy paid — POST unique vers /audit.
    from payments.x402_client import run_paid_audit
    return await run_paid_audit(get_api_url(), path), None


# ─── Render Results ────────────────────────────────────────────────────────────

def _render_audit_result(data: dict[str, Any], payment_tx: str | None = None) -> None:
    """Render full output: verdict -> findings -> Phase 6 report -> raw JSON."""

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

    audit_web_id = data.get("id")
    if audit_web_id:
        web_url = f"{get_app_url()}/audit/{audit_web_id}"
        info(f"Rapport web: [accent]{web_url}[/accent]")

    # ── Summary rapide ────────────────────────────────────────────────────────
    if report.get("summary"):
        s = report["summary"]
        console.print(
            kv_panel(
                "Summary",
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

        # Per-finding details (fix_sketch + prior_audit_ref + onchain_proof)
        _render_finding_details(findings)
    else:
        # Fallback sur les findings Slither bruts
        raw_findings = investigation.get("findings") or data.get("slither", {}).get("findings") or []
        if raw_findings:
            section(f"Findings ({len(raw_findings)})")
            console.print(findings_table(raw_findings))
        else:
            info("No findings detected.")

    # ── Onchain proofs ────────────────────────────────────────────────────────
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
    section("Raw Report (JSON)")
    console.print_json(data=data)


def _enriched_findings_table(findings: list[dict]) -> Table:
    """Enriched table: sev / conf / title / file:line / prior_ref."""
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
    """Render details for HIGH/MEDIUM findings: fix_sketch + prior_audit_ref + onchain_proof."""
    notable = [f for f in findings if f.get("severity") in ("HIGH", "MEDIUM")]
    if not notable:
        return

    section("Critical Finding Details")
    for f in notable:
        sev       = f.get("severity", "INFO").upper()
        sev_style = SEVERITY_STYLES.get(sev, "muted")
        title     = f.get("title", "Unknown")
        fid       = f.get("id", "")

        lines: list[str] = []

        # Description
        if f.get("description"):
            lines.append(f"[label]Description:[/label] {f['description'][:200]}")

        # Fix sketch
        if f.get("fix_sketch"):
            lines.append("")
            lines.append("[label]Fix sketch:[/label]")
            for code_line in f["fix_sketch"].splitlines():
                lines.append(f"  [accent]{code_line}[/accent]")

        # Prior audit reference
        if f.get("prior_audit_ref"):
            lines.append("")
            lines.append(f"[label]Historical reference:[/label] [muted]{f['prior_audit_ref']}[/muted]")

        # Preuve KeeperHub / EVM
        if f.get("onchain_proof"):
            etherscan = f"https://sepolia.etherscan.io/tx/{f['onchain_proof']}"
            lines.append("")
            lines.append(f"[label]Onchain tx:[/label] [info]{etherscan}[/info]")
        elif f.get("keeperhub_execution_id"):
            lines.append("")
            lines.append(
                f"[label]KeeperHub anchor (execution reference, pending tx, or non-EVM format):[/label] "
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
    """True if tx is a non-zero EVM hash usable on Etherscan."""
    if not tx or not tx.startswith("0x"):
        return False
    if tx == "0x" + "0" * 64:
        return False
    return len(tx) == 66


def _render_onchain_section(onchain: dict, findings: list[dict], report: dict) -> None:
    section("Onchain Proofs")

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
            # Not mined yet — contract link + pattern_hash for manual check
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
        console.print(kv_panel("Onchain Proofs", items))


def _render_ens_badge(
    ens: dict,
    report_hash: str | None = None,
    report_verdict: str | None = None,
) -> None:
    section("ENS Certificate")

    ENS_SEPOLIA_BASE = "https://sepolia.app.ens.domains/"

    mint_ok = ens.get("certified") and ens.get("subname")
    verdict_ok = (report_verdict or "").upper() == "CERTIFIED"

    if mint_ok:
        subname = ens["subname"]
        verdict_display = report_verdict or "CERTIFIED"
        items = {
            "ENS Sepolia": f"{ENS_SEPOLIA_BASE}{subname}",
            "Parent domain": ens.get("parent", "certified.onchor-ai.eth"),
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
            "[warn]⚠  CERTIFIED — ENS certificate was not minted[/warn]\n\n"
            "[muted]The pipeline found no HIGH findings.\n"
            "ENS mint failed (Sepolia network or configuration).\n"
            "Run again with --dev to retry minting.[/muted]"
        )
        if report_hash:
            body = Text.from_markup(
                "[warn]⚠  CERTIFIED — ENS certificate was not minted[/warn]\n\n"
                f"[label]Report hash :[/label] [info]{report_hash}[/info]\n\n"
                "[muted]ENS mint failed — check ALCHEMY_API_KEY and PRIVATE_KEY "
                "in contracts/.env[/muted]"
            )
        console.print(Panel(
            body,
            title="[brand]ENS Certificate[/brand]",
            border_style="warn",
            padding=(1, 2),
        ))

    else:
        body = Text.from_markup(
            "[danger]✘  Not certified — HIGH findings detected[/danger]\n\n"
            "[muted]ENS certificates are issued only when no HIGH finding "
            "is detected.\nFix findings and rerun the audit.[/muted]"
        )
        console.print(Panel(
            body,
            title="[brand]ENS Certificate[/brand]",
            border_style="danger",
            padding=(1, 2),
        ))
        # No link — nothing was minted, a link would be misleading


# ─── Contribution opt-in ───────────────────────────────────────────────────────
def _handle_optional_contribution(findings: list[dict], user_config: dict[str, Any]) -> None:
    section("Collective Memory Contribution")
    info(
        f"[accent]{len(findings)}[/accent] vulnerability pattern(s) identified. "
        "Share these ANONYMIZED patterns with collective memory?"
    )
    info("Reward: [accent]0.05 USDC[/accent] per validated pattern (max 3).")

    if not click.confirm("Contribute?", default=False):
        warn("Contribution declined — your data remains strictly local.")
        return

    MAX_REWARDABLE = 3
    payable_count  = min(len(findings), MAX_REWARDABLE)
    reward         = payable_count * 0.05

    info(f"Sending reward ({reward:.2f} USDC) on Base Sepolia...")
    try:
        contributor_address = os.getenv("RECEIVER_ADDRESS")
        with httpx.Client(timeout=180.0) as client:
            reward_resp = client.post(
                f"{get_api_url()}/audit/reward",
                params={"contributor_address": contributor_address, "amount": reward},
                json=findings[:MAX_REWARDABLE],  # envoie les patterns dans le body
            )
            reward_resp.raise_for_status()
            reward_data = reward_resp.json()
            tx_hash = reward_data.get("tx")
            contributed = reward_data.get("contributed") or []

        user_config["credit_usdc"] += reward
        save_config(user_config)

        success(f"{payable_count} pattern(s) paid onchain.")
        
        real_balance = user_config["credit_usdc"]
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(f"{get_api_url()}/user/balance", params={"address": contributor_address})
                real_balance = resp.json().get("balance", real_balance)
        except Exception:
            pass

        console.print(
            kv_panel(
                "Reward",
                {
                    "Paid patterns": str(payable_count),
                    "TX hash":        tx_hash or "—",
                    "New balance":    f"{real_balance:.2f} USDC",
                },
            )
        )
        if contributed:
            console.print()
            section("0G Contribution Proofs")
            for i, c in enumerate(contributed[:MAX_REWARDABLE], 1):
                tx0g = (c.get("tx_hash") or c.get("tx") or "").strip()
                root = (c.get("root_hash") or c.get("pattern_hash") or "").strip()
                if tx0g:
                    tx_link = tx0g if tx0g.startswith("0x") else f"0x{tx0g}"
                    info(f"[{i}] 0G tx: [accent]https://chainscan-galileo.0g.ai/tx/{tx_link}[/accent]")
                if root:
                    info(f"[{i}] root: [muted]{root}[/muted]")
    except Exception as e:
        error(f"Payment error: {e}")


if __name__ == "__main__":
    cli()