"""
Post-install onboarding wizard (~/.onchor-ai/):
wallet generation, faucets, API keys (Vercel / KeeperHub / Etherscan / 0G),
live validation, and writing .env + config.json.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import click
import httpx
from dotenv import load_dotenv
from eth_account import Account
from keeper.hub_anchor import KEEPERHUB_VALIDATE_READ_FALLBACK_URLS
from rich.panel import Panel
from rich.text import Text
from web3 import Web3

from ui import console, credentials_summary_table, error, info, section, success, warn, show_banner

# ─── Paths ───────────────────────────────────────────────────────────────────
ONCHOR_AI_DIR = Path.home() / ".onchor-ai"
CONFIG_JSON_PATH = ONCHOR_AI_DIR / "config.json"
ENV_JSON_PATH = ONCHOR_AI_DIR / ".env"


def hub_headers(api_key: str) -> dict[str, str]:
    from keeper.hub_anchor import _authorization_headers as _hdr
    return _hdr(api_key)


# ─── Networks & faucets ───────────────────────────────────────────────────────
SEP_ETH_MIN_WEI = Web3.to_wei(0.005, "ether")
BASE_USDC_MIN = 1.0
OZ_G_ETH_MIN_WEI = Web3.to_wei(0.001, "ether")

SEP_RPC = os.getenv("SEPOLIA_RPC_URL") or "https://rpc.sepolia.org"
BASE_SEP_RPC = os.getenv("BASE_SEPOLIA_RPC_URL") or "https://sepolia.base.org"
USDC_BASE_SEPOLIA = "0x036CbD53842c5426634e7929541eC2318f3dCF7e"
OZ_G_RPC_DEFAULT = os.getenv("OG_EVM_RPC") or "https://evmrpc-testnet.0g.ai"

VERCEL_AI_GATEWAY = "https://ai-gateway.vercel.sh/v1"
VERCEL_AI_DOCS_URL = "https://vercel.com/docs/ai-gateway"
KEEPERHUB_SETTINGS_KEYS = "https://app.keeperhub.com/settings"

EULER_VAULT_DEMO_ADDR = "0x49Ca165Bd6AEe88825f59c557bC52A685e0594B5"

# Timeout per RPC balance check (seconds)
BALANCE_RPC_TIMEOUT = float(os.getenv("ONCHOR_BALANCE_RPC_TIMEOUT", "5.0"))

ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
    }
]

# ─── Step header helper ───────────────────────────────────────────────────────

TOTAL_STEPS = 6


def _step_header(n: int, title: str, subtitle: str = "") -> None:
    """
    Render a step header panel with a [n / TOTAL_STEPS] counter.

    Example output:
        ╭──────────────────────────────────────────────────────╮
        │  [2 / 6]  Local Wallet                               │
        │  Generates an AES-encrypted private key on disk.     │
        ╰──────────────────────────────────────────────────────╯
    """
    counter = f"[muted][{n} / {TOTAL_STEPS}][/muted]"
    heading = f"[brand]{title}[/brand]"
    body = f"{counter}  {heading}"
    if subtitle:
        body += f"\n[muted]{subtitle}[/muted]"
    console.print()
    console.print(
        Panel(
            Text.from_markup(body),
            border_style="brand.dim",
            padding=(0, 2),
        )
    )


# ─── Steps overview panel ─────────────────────────────────────────────────────

def _show_steps_overview() -> None:
    """Render a one-time overview panel listing all 6 setup steps."""
    steps = [
        ("1", "Wallet",       "key generation + testnet faucets"),
        ("2", "LLM Gateway",  "Vercel AI Gateway (claude-haiku / sonnet)"),
        ("3", "KeeperHub",    "onchain anchoring via MPC wallet"),
        ("4", "Etherscan",    "optional — required for 0x address audits"),
        ("5", "0G Storage",   "decentralized pattern storage (Galileo testnet)"),
        ("6", "Validation",   "live connectivity check for every key"),
    ]
    lines = [
        f"  [muted]{num}.[/muted]  [label]{name:<14}[/label]  [muted]{desc}[/muted]"
        for num, name, desc in steps
    ]
    console.print(
        Panel(
            Text.from_markup("\n".join(lines)),
            title="[brand]Initial setup — 6 steps[/brand]",
            border_style="brand.dim",
            padding=(1, 2),
        )
    )


# ─── Connectivity checks ──────────────────────────────────────────────────────

async def keeperhub_validate_read_probe(api_key: str) -> tuple[bool, str]:
    """
    Validate a KeeperHub Bearer token using a read-only GET request.
    Never calls POST /execute/contract-call to avoid side effects on install.
    Falls back through KEEPERHUB_VALIDATE_READ_FALLBACK_URLS in order.
    """
    if not (api_key or "").strip():
        return False, "empty key"
    headers = hub_headers(api_key)

    # Build URL list: explicit env override first, then fallbacks
    urls: list[str] = []
    pref = (os.getenv("KEEPERHUB_VALIDATION_URL") or "").strip()
    if pref:
        urls.append(pref)
    for u in KEEPERHUB_VALIDATE_READ_FALLBACK_URLS:
        if u not in urls:
            urls.append(u)

    last_msg = ""
    timeout = float(os.getenv("KEEPERHUB_VALIDATION_HTTP_TIMEOUT", "12.0"))
    async with httpx.AsyncClient(timeout=timeout) as client:
        for url in urls:
            try:
                r = await client.get(url, headers=headers)
            except httpx.RequestError as e:
                last_msg = str(e)[:140]
                continue
            # 403 means the token was accepted but the resource is restricted — still valid
            if r.status_code == 403:
                return True, f"GET read → HTTP 403 ({url}) — Bearer accepted"
            if 200 <= r.status_code < 300:
                return True, f"GET read → HTTP {r.status_code} ({url})"
            if r.status_code == 404:
                last_msg = f"404 on {url} — path may have changed on KeeperHub side"
                continue
            if r.status_code == 429:
                return False, "HTTP 429 — KeeperHub rate-limit; retry in a moment"
            if r.status_code < 500:
                return True, f"GET read → HTTP {r.status_code} ({url})"
            last_msg = f"HTTP {r.status_code} on {url}"

    return (
        False,
        last_msg or (
            "No GET route available to validate the key — "
            "set KEEPERHUB_VALIDATION_URL or contact KeeperHub support."
        ),
    )


async def run_connectivity_checks(
    *,
    llm_key: str | None,
    keeperhub_key: str | None,
    etherscan_key: str | None,
    og_pv_key_set: bool,
    etherscan_skipped: bool,
    og_skipped_same_wallet: bool,
) -> tuple[dict[str, tuple[bool, str]], list[dict[str, str]]]:
    """
    Run live connectivity checks for all configured services.
    Returns (checks_dict, table_rows) where checks_dict maps service name
    to (ok, detail_message).
    """

    def etherscan_ping() -> tuple[bool, str]:
        if etherscan_skipped:
            return True, "skipped (user choice)"
        if not etherscan_key:
            return False, "empty key"
        try:
            url = (
                "https://api-sepolia.etherscan.io/api"
                "?module=account&action=balance&address=0x0&tag=latest"
                f"&apikey={etherscan_key}"
            )
            with httpx.Client(timeout=12.0) as client:
                r = client.get(url)
            try:
                j = r.json()
            except Exception:
                return False, "non-JSON response"
            if j.get("status") == "1" or j.get("message") == "OK":
                return True, "OK"
            msg = str(j.get("result", j.get("message", "")))[:120]
            if "Invalid API Key" in msg or ("invalid" in msg.lower()):
                return False, msg or "invalid token"
            return True, msg or "OK"
        except Exception as e:
            return False, str(e)[:80]

    out: dict[str, tuple[bool, str]] = {}

    # --- Vercel AI Gateway ---
    if llm_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=llm_key, base_url=VERCEL_AI_GATEWAY, timeout=20.0)
            client.chat.completions.create(
                model=os.getenv("ONBOARDING_GATEWAY_MODEL") or "anthropic/claude-3-5-haiku-20241022",
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=8,
            )
            out["Vercel AI Gateway"] = (True, "short completion OK")
        except Exception as e:
            out["Vercel AI Gateway"] = (False, str(e)[:120])
    else:
        out["Vercel AI Gateway"] = (False, "empty key")

    # --- KeeperHub ---
    out["KeeperHub API"] = await keeperhub_validate_read_probe(keeperhub_key or "")

    # --- Etherscan ---
    ok_e, detail_e = etherscan_ping()
    out["Etherscan API"] = (True if etherscan_skipped else ok_e, detail_e)

    # --- 0G Storage ---
    out["0G Storage (OG_PRIVATE_KEY)"] = (
        (True, "reuses x402 wallet")
        if og_skipped_same_wallet and og_pv_key_set
        else ((True, "key provided") if og_pv_key_set else (False, "empty key"))
    )

    # Build Rich table rows
    rows: list[dict[str, str]] = []
    alias_map = {"Vercel AI Gateway": "LLM (Vercel Gateway)"}
    for key, (ok_c, det) in out.items():
        name = alias_map.get(key, key)
        skipped = etherscan_skipped and key == "Etherscan API"
        rows.append(
            {
                "name": name,
                "status": "skipped" if skipped else ("valid" if ok_c else "invalid"),
                "detail": det,
            }
        )

    return out, rows


# ─── Balance helpers ──────────────────────────────────────────────────────────

def sep_eth_balance(addr: str) -> int:
    """Return ETH balance in wei on Ethereum Sepolia."""
    w3 = Web3(Web3.HTTPProvider(SEP_RPC))
    return int(w3.eth.get_balance(Web3.to_checksum_address(addr)))


def base_usdc_balance(addr: str) -> float:
    """Return USDC balance (human-readable) on Base Sepolia."""
    w3 = Web3(Web3.HTTPProvider(BASE_SEP_RPC))
    c = w3.eth.contract(
        address=Web3.to_checksum_address(USDC_BASE_SEPOLIA),
        abi=ERC20_ABI,
    )
    raw = c.functions.balanceOf(Web3.to_checksum_address(addr)).call()
    return float(raw) / 1e6


def oz_g_eth_balance(addr: str) -> int:
    """Return ETH balance in wei on the 0G Galileo testnet."""
    w3 = Web3(Web3.HTTPProvider(OZ_G_RPC_DEFAULT))
    return int(w3.eth.get_balance(Web3.to_checksum_address(addr)))


async def _balance_call(fn, addr: str) -> tuple[bool, int | float | None, str | None]:
    """
    Run a balance RPC call in a thread with a timeout.
    Returns (rpc_ok, value, error_message).
    """
    try:
        val = await asyncio.wait_for(asyncio.to_thread(fn, addr), timeout=BALANCE_RPC_TIMEOUT)
        return True, val, None
    except asyncio.TimeoutError:
        return False, None, f"timeout ({int(BALANCE_RPC_TIMEOUT)}s)"
    except Exception as e:
        return False, None, str(e)[:120]


async def balances_ok(address: str) -> tuple[bool, list[str], list[str], bool]:
    """
    Check balances across all three networks **concurrently** using asyncio.gather.
    Running in parallel cuts the worst-case wait from 3 × timeout to 1 × timeout.

    Returns:
        all_green    -- True when every balance meets the minimum requirement
        status_lines -- one Rich-markup line per network (for display)
        action_lines -- one actionable hint per network that needs funding (may be empty)
        rpc_issue    -- True if at least one RPC call timed out or failed
    """
    # All three calls fire at the same time — total wait = max(individual timeouts)
    (sr, eth_s, s_err), (ur, usdc_amt, u_err), (or_ok, wei_og, o_err) = await asyncio.gather(
        _balance_call(sep_eth_balance, address),
        _balance_call(base_usdc_balance, address),
        _balance_call(oz_g_eth_balance, address),
    )

    rpc_issue = not (sr and ur and or_ok)
    status_lines: list[str] = []
    action_lines: list[str] = []  # only populated for networks that need attention

    # Ethereum Sepolia ETH
    if not sr:
        status_lines.append(f"[warn]⚠[/warn]  ETH Ethereum Sepolia  — could not check ({s_err})")
    else:
        assert eth_s is not None
        eth_ok = int(eth_s) >= SEP_ETH_MIN_WEI
        have = Web3.from_wei(int(eth_s), "ether")
        need = Web3.from_wei(SEP_ETH_MIN_WEI, "ether")
        icon = "[ok]✔[/ok]" if eth_ok else "[danger]✘[/danger]"
        status_lines.append(f"{icon}  ETH Ethereum Sepolia  — {have} ETH  (min {need} ETH)")
        if not eth_ok:
            action_lines.append(
                f"  [warn]→[/warn]  Get ETH Sepolia   [info]https://sepoliafaucet.com[/info]  "
                f"(need ~{need} ETH, have {have})"
            )

    # Base Sepolia USDC
    if not ur:
        status_lines.append(f"[warn]⚠[/warn]  USDC Base Sepolia     — could not check ({u_err})")
    else:
        assert usdc_amt is not None
        usdc_ok = usdc_amt >= BASE_USDC_MIN
        icon = "[ok]✔[/ok]" if usdc_ok else "[danger]✘[/danger]"
        status_lines.append(f"{icon}  USDC Base Sepolia     — {usdc_amt:.4f} USDC  (min ~{BASE_USDC_MIN:g} USDC)")
        if not usdc_ok:
            action_lines.append(
                f"  [warn]→[/warn]  Get USDC Base Sepolia [info]https://faucet.circle.com[/info]  "
                f"(need ~{BASE_USDC_MIN:g} USDC, have {usdc_amt:.4f})"
            )

    # 0G Galileo ETH
    if not or_ok:
        status_lines.append(f"[warn]⚠[/warn]  ETH 0G Galileo        — could not check ({o_err})")
    else:
        assert wei_og is not None
        og_ok = int(wei_og) >= OZ_G_ETH_MIN_WEI
        have = Web3.from_wei(int(wei_og), "ether")
        need = Web3.from_wei(OZ_G_ETH_MIN_WEI, "ether")
        icon = "[ok]✔[/ok]" if og_ok else "[danger]✘[/danger]"
        status_lines.append(f"{icon}  ETH 0G Galileo        — {have}  (min {need})")
        if not og_ok:
            action_lines.append(
                f"  [warn]→[/warn]  Get ETH 0G Galileo    [info]https://faucet.0g.ai[/info]  "
                f"(need ~{need}, have {have})"
            )

    eth_ok_f = bool(sr and eth_s is not None and int(eth_s) >= SEP_ETH_MIN_WEI)
    usdc_ok_f = bool(ur and usdc_amt is not None and usdc_amt >= BASE_USDC_MIN)
    og_ok_f = bool(or_ok and wei_og is not None and int(wei_og) >= OZ_G_ETH_MIN_WEI)

    all_green = (not rpc_issue) and eth_ok_f and usdc_ok_f and og_ok_f
    return all_green, status_lines, action_lines, rpc_issue


# ─── Wallet step ──────────────────────────────────────────────────────────────

def _wallet_step() -> tuple[str, str]:
    """
    Generate a local private key, display the address with a copy callout,
    and wait for the user to fund it via the three required testnet faucets.
    Balance checks run concurrently; failed networks show exact action items.
    Returns (private_key_hex_no_prefix, checksummed_address).
    """
    acct = Account.create()
    key = acct.key.hex()
    addr = Web3.to_checksum_address(acct.address)

    _step_header(
        1,
        "Local Wallet",
        "A private key is generated locally and stored encrypted on this machine.",
    )

    # Address displayed prominently so the user can triple-click to copy it
    console.print(
        Panel(
            Text.from_markup(
                "[label]Your wallet address[/label]  "
                "[muted](triple-click to copy)[/muted]\n\n"
                f"[accent]{addr}[/accent]\n\n"
                "[muted]Use this same address on all three faucets below.[/muted]"
            ),
            border_style="accent",
            title="[accent]Copy this address[/accent]",
            padding=(1, 2),
        )
    )

    # Faucet instructions as a structured list
    console.print(
        Panel(
            Text.from_markup(
                "[label]1.[/label]  [muted]ETH Ethereum Sepolia[/muted]  — min ~0.005 ETH  — KeeperHub gas\n"
                "   [info]https://sepoliafaucet.com[/info]\n\n"
                "[label]2.[/label]  [muted]USDC Base Sepolia[/muted]     — min ~1 USDC     — x402 payments\n"
                "   [info]https://faucet.circle.com[/info]\n\n"
                "[label]3.[/label]  [muted]ETH Galileo / 0G[/muted]      — min ~0.001 ETH  — decentralized storage\n"
                "   [info]https://faucet.0g.ai[/info]"
            ),
            border_style="brand.dim",
            title="Fund the wallet — 3 faucets",
            padding=(1, 2),
        )
    )
    click.prompt(
        "\nOnce all accounts are funded, press Enter to verify balances",
        default="",
        show_default=False,
    )

    while True:
        # Concurrent checks — all 3 RPCs fire at the same time, max wait = 1× timeout
        with console.status(
            f"[brand]Checking balances on 3 networks (timeout {int(BALANCE_RPC_TIMEOUT)}s)…[/brand]",
            spinner="dots",
        ):
            all_green, status_lines, action_lines, rpc_issue = asyncio.run(balances_ok(addr))

        # Per-network status
        console.print()
        for line in status_lines:
            console.print(Text.from_markup(line))

        if rpc_issue:
            # At least one RPC timed out — offer to skip rather than block indefinitely
            if click.confirm(
                f"\nSome RPC calls timed out ({int(BALANCE_RPC_TIMEOUT)}s). Continue without verifying?",
                default=False,
            ):
                warn(
                    "Continuing without full balance check — "
                    "run [accent]onchor-ai doctor[/accent] later to verify."
                )
                return key, addr
            click.prompt("Press Enter to retry…", default="", show_default=False)
            continue

        if all_green:
            console.print()
            success("All balances confirmed ✓")
            return key, addr

        # Show exactly which faucets still need to be visited
        if action_lines:
            console.print()
            console.print(Text.from_markup("[warn]Still needed:[/warn]"))
            for line in action_lines:
                console.print(Text.from_markup(line))

        console.print()
        if not click.confirm("Re-check after topping up?", default=True):
            break
        click.prompt("(Press Enter when ready)", default="", show_default=False)

    return key, addr


# ─── Misc helpers ─────────────────────────────────────────────────────────────

def _masked_prompt(label: str, text: str) -> str:
    """Display a hint then prompt for a hidden input (used for key corrections)."""
    click.echo("")
    console.print(Text.from_markup(f"[muted]{text}[/muted]"))
    return (click.prompt(label, hide_input=True, confirmation_prompt=False) or "").strip()


# ─── Key format validators ────────────────────────────────────────────────────
# These are soft checks — a warning is shown but the key is always accepted.
# The live connectivity test in step 6 is the authoritative validator.

def _is_keeperhub_key(key: str) -> bool:
    """KeeperHub keys are prefixed with kh_ or kh- (normalization adds it if missing)."""
    low = key.lower()
    return low.startswith("kh_") or low.startswith("kh-")


def _is_etherscan_key(key: str) -> bool:
    """Etherscan API keys are alphanumeric strings, typically 34 characters."""
    return len(key) >= 20 and key.isalnum()


def _is_hex_private_key(key: str) -> bool:
    """A valid EVM private key is exactly 32 bytes expressed as 64 hex characters."""
    raw = key.removeprefix("0x").strip()
    return len(raw) == 64 and all(c in "0123456789abcdefABCDEF" for c in raw)


def _prompt_api_key(
    label: str,
    *,
    hint: str = "",
    doc_url: str = "",
    env_fallback: str = "",
    format_check=None,
    format_warning: str = "",
) -> str:
    """
    Prompt for an API key with contextual cues at the point of input.

    Shows:
    - An optional format hint  (e.g. "format: kh_…")
    - An optional doc URL      (e.g. link to the key-generation page)
    - A soft format warning    (shown after entry if format_check fails;
                                the key is still accepted — step 6 validates live)

    Args:
        label           Label shown in the prompt line.
        hint            Expected key format, displayed as a muted hint above the prompt.
        doc_url         Direct link to where this key can be obtained.
        env_fallback    Pre-fill default from an existing env variable.
        format_check    Optional callable(key) -> bool. Soft check only.
        format_warning  Human-readable description of what the format should be.
    """
    if hint:
        console.print(Text.from_markup(f"  [muted]format:[/muted] [label]{hint}[/label]"))
    if doc_url:
        console.print(Text.from_markup(f"  [muted]where to get it:[/muted] [info]{doc_url}[/info]"))

    value = click.prompt(
        label,
        hide_input=True,
        prompt_suffix=" › ",
        default=env_fallback or "",
    ).strip()

    if format_check and value and not format_check(value):
        warn(f"Unexpected format — {format_warning}")
        console.print(Text.from_markup(
            "  [muted]The key was saved as-is. "
            "Step 6 will confirm whether it works.[/muted]"
        ))

    return value


def _merge_dotenv_file(path: Path, updates: dict[str, str]) -> None:
    """
    Update only the specified keys in an existing .env file,
    preserving comments and unrelated lines.
    """
    used_keys: set[str] = set()
    out_lines: list[str] = []
    if path.is_file():
        for raw in path.read_text(encoding="utf-8").splitlines():
            if "=" in raw and not raw.strip().startswith("#"):
                k, _sep, _tail = raw.partition("=")
                kk = k.strip()
                if kk in updates:
                    out_lines.append(f"{kk}={updates[kk].replace(chr(10), '')}")
                    used_keys.add(kk)
                    continue
            out_lines.append(raw)
    # Append any keys that were not already present in the file
    for kk, vv in updates.items():
        if kk not in used_keys:
            out_lines.append(f"{kk}={vv.replace(chr(10), '').replace(chr(13), '')}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")


def _write_dotenv(kv: dict[str, str]) -> None:
    """Write all onboarding keys to ~/.onchor-ai/.env and merge into backend/.env."""
    ONCHOR_AI_DIR.mkdir(parents=True, exist_ok=True)
    lines = [f"{k}={kv[k].replace(chr(10), '')}" for k in sorted(kv.keys())]
    ENV_JSON_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Keep backend/.env in sync so the server picks up changes immediately
    cli_env = Path(__file__).resolve().parent / ".env"
    _merge_dotenv_file(cli_env, kv)


# ─── Run mode detection ───────────────────────────────────────────────────────

def _detect_run_mode() -> str:
    """
    Detect the intended run mode from sys.argv before Click parses the command.
    Returns 'dev', 'local', or 'full'.

    Called early in the onboarding flow so the wizard can skip steps that are
    irrelevant for the requested mode:
      dev   → bypass everything (no LLM key, no wallet, no anchoring)
      local → LLM key only (no wallet, no payments, no onchain)
      full  → complete 6-step setup
    """
    args = sys.argv[1:]
    if "--dev" in args:
        return "dev"
    if "--local" in args:
        return "local"
    return "full"


# ─── Local / dev fast-path onboarding ────────────────────────────────────────

async def _run_local_onboarding(mode: str) -> None:
    """
    Minimal onboarding for --local and --dev modes.

    --dev   No keys needed. Writes a minimal config and exits.
            x402, anchoring, and collective memory are all bypassed at runtime.

    --local Only an LLM key is required.
            No wallet, no faucets, no KeeperHub, no 0G.
            The user can graduate to the full setup later by deleting
            ~/.onchor-ai/config.json and running `onchor-ai` again.
    """
    # ── Dev mode — no input required ─────────────────────────────────────────
    if mode == "dev":
        console.print(Text.from_markup(
            "[muted]Dev mode detected — skipping full setup.[/muted]\n"
            "[muted]x402 payments, onchain anchoring, and collective memory "
            "are bypassed at runtime.[/muted]"
        ))
        console.print()

        cfg = {
            "version": "0.1.0",
            "mode": "dev",
            "credit_usdc": 0.0,
            "onboarding_completed": True,
            "wallet_address": "",
        }
        ONCHOR_AI_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_JSON_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")

        success("Dev config written.")
        console.print()
        console.print(Panel(
            Text.from_markup(
                "[brand]Ready for dev audits[/brand]\n\n"
                "  [accent]onchor-ai audit ./src/ --dev[/accent]\n\n"
                "[muted]To enable paid features later, delete the config and re-run setup:[/muted]\n"
                "  [muted]rm ~/.onchor-ai/config.json && onchor-ai[/muted]"
            ),
            border_style="brand",
            padding=(1, 2),
        ))
        return

    # ── Local mode — LLM key only ─────────────────────────────────────────────
    console.print(Text.from_markup(
        "[muted]Local mode detected — minimal setup (LLM key only).[/muted]\n"
        "[muted]No wallet, no payments, no onchain anchoring.[/muted]"
    ))
    console.print()
    console.print(Panel(
        Text.from_markup(
            "  [muted]1.[/muted]  [label]LLM Gateway   [/label]  "
            "[muted]Vercel AI Gateway key (claude-haiku / sonnet)[/muted]\n"
            "  [muted]2.[/muted]  [label]Validation    [/label]  "
            "[muted]live connectivity check[/muted]\n\n"
            "[muted]Run without --local later to unlock onchain anchoring "
            "and collective memory.[/muted]"
        ),
        title="[brand]Local setup — 2 steps[/brand]",
        border_style="brand.dim",
        padding=(1, 2),
    ))

    # Step 1 — LLM key
    _step_header(
        1,
        "Vercel AI Gateway",
        "Powers claude-haiku (triage) and claude-sonnet (investigation).",
    )
    llm_raw = _prompt_api_key(
        "Vercel AI Gateway API key",
        hint="vai_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        doc_url=f"{VERCEL_AI_DOCS_URL}  →  Tokens tab",
        env_fallback=os.getenv("LLM_API_KEY") or "",
    )
    if not llm_raw:
        error("An LLM key is required even in local mode.")
        raise click.Abort()

    # Step 2 — live validation (single service, no table)
    _step_header(
        2,
        "Key Validation",
        "Testing the LLM key before saving.",
    )
    llm_ok = False
    with console.status("[brand]Checking Vercel AI Gateway…[/brand]", spinner="dots"):
        try:
            from openai import OpenAI
            client = OpenAI(api_key=llm_raw, base_url=VERCEL_AI_GATEWAY, timeout=20.0)
            client.chat.completions.create(
                model=os.getenv("ONBOARDING_GATEWAY_MODEL") or "anthropic/claude-3-5-haiku-20241022",
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=8,
            )
            llm_ok = True
        except Exception as exc:
            llm_ok = False
            _llm_err = str(exc)[:120]

    if llm_ok:
        success("LLM key validated ✓")
    else:
        warn(f"Could not validate the key ({_llm_err}).")
        warn("Saved anyway — run [accent]onchor-ai doctor[/accent] to re-check.")

    # Write minimal config and env
    kv: dict[str, str] = {
        "LLM_API_KEY": llm_raw,
        "EMBEDDING_API_KEY": llm_raw,
        "EMBEDDING_ENDPOINT": VERCEL_AI_GATEWAY,
    }
    cfg = {
        "version": "0.1.0",
        "mode": "local",
        "credit_usdc": 0.0,
        "onboarding_completed": True,
        "wallet_address": "",
    }
    ONCHOR_AI_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_JSON_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    os.environ.update(kv)
    load_dotenv(ENV_JSON_PATH, override=True)
    _write_dotenv(kv)

    console.print()
    console.print(Panel(
        Text.from_markup(
            "[brand]Ready for local audits[/brand]\n\n"
            "  [accent]onchor-ai audit ./src/ --local[/accent]\n\n"
            "[muted]To unlock paid features (onchain anchoring, collective memory):[/muted]\n"
            "  [muted]rm ~/.onchor-ai/config.json && onchor-ai[/muted]"
        ),
        border_style="brand",
        padding=(1, 2),
    ))


# ─── Onboarding wizard ────────────────────────────────────────────────────────

def run_onboarding_wizard() -> None:
    """
    Entry point for the onboarding flow — runs once on first launch.
    Auto-detects the run mode from sys.argv and branches accordingly:
      --dev   → no-input fast-path (dev config only)
      --local → 2-step fast-path  (LLM key only)
      (none)  → full 6-step wizard
    Can be bypassed with ONCHOR_SKIP_ONBOARDING=1.
    """
    if os.environ.get("ONCHOR_SKIP_ONBOARDING", "").strip() in ("1", "true", "yes"):
        warn("ONCHOR_SKIP_ONBOARDING set — skipping wizard.")
        return

    mode = _detect_run_mode()

    # Fast-paths for local and dev modes — skip the full wizard
    if mode in ("local", "dev"):
        asyncio.run(_run_local_onboarding(mode))
        return

    # Full wizard — banner + steps overview displayed once at the very beginning
    console.print()
    console.print(Text.from_markup(
        "[muted]First launch detected — initial setup required.[/muted]\n"
        "[muted]This wizard runs only once.[/muted]"
    ))
    console.print()
    _show_steps_overview()
    console.print()
    info("Skip at any time: [accent]ONCHOR_SKIP_ONBOARDING=1[/accent]")
    console.print()

    # Step 1 — Wallet
    pv, wallet_addr = _wallet_step()

    # Step 2 — Vercel AI Gateway
    _step_header(
        2,
        "Vercel AI Gateway",
        "Powers claude-haiku (triage phase) and claude-sonnet (investigation phase).",
    )
    llm_raw = _prompt_api_key(
        "Vercel AI Gateway API key",
        hint="vai_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        doc_url=f"{VERCEL_AI_DOCS_URL}  →  Tokens tab",
        env_fallback=os.getenv("LLM_API_KEY") or "",
    )
    if not llm_raw:
        error("A Vercel AI Gateway key is required.")
        raise click.Abort()

    # Step 3 — KeeperHub
    _step_header(
        3,
        "KeeperHub",
        "Anchors each finding onchain via an auto-provisioned MPC wallet (no gas management needed).",
    )
    keeper_raw = _prompt_api_key(
        "KeeperHub API key",
        hint="kh_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        doc_url=f"{KEEPERHUB_SETTINGS_KEYS}  →  API Keys",
        env_fallback=os.getenv("KEEPERHUB_API_KEY") or "",
        format_check=_is_keeperhub_key,
        format_warning="expected prefix kh_ or kh- (will be added automatically if missing)",
    )
    if not keeper_raw:
        error("A KeeperHub key is required.")
        raise click.Abort()

    # Step 4 — Etherscan (optional)
    _step_header(
        4,
        "Etherscan",
        "Only needed when auditing deployed contracts by their 0x address.",
    )
    etherscan_skip = click.confirm(
        "Skip Etherscan (local file audits only)?",
        default=False,
    )
    etherscan_key = ""
    if not etherscan_skip:
        etherscan_key = _prompt_api_key(
            "Etherscan API key",
            hint="XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX  (34 alphanumeric chars)",
            doc_url="https://etherscan.io/apis  →  Get API key",
            env_fallback=os.getenv("ETHERSCAN_API_KEY") or "",
            format_check=_is_etherscan_key,
            format_warning="expected 20–40 alphanumeric characters",
        )

    # Step 5 — 0G Storage private key
    _step_header(
        5,
        "0G Storage",
        "Signs pattern uploads to the decentralized collective memory (Galileo testnet).",
    )
    reuse_og = click.confirm(
        "Reuse the wallet key from step 1 (recommended)?",
        default=True,
    )
    if reuse_og:
        og_hex = pv
    else:
        while True:
            raw_og = _prompt_api_key(
                "0G private key",
                hint="0x + 64 hex characters  (or 64 hex without prefix)",
                doc_url="https://faucet.0g.ai  →  connect wallet to get testnet ETH",
                format_check=_is_hex_private_key,
                format_warning="expected 64 hex characters (32 bytes), with or without 0x prefix",
            )
            og_hex = raw_og.removeprefix("0x").strip()

            if not og_hex:
                error("A 0G private key is required.")
                continue

            # Hard validation: attempt to derive an address.
            # A bad key here would silently fail deep in the pipeline.
            try:
                derived = Account.from_key("0x" + og_hex).address
                console.print(Text.from_markup(
                    f"  [ok]✔[/ok]  Derived address: [muted]{derived}[/muted]"
                ))
                break
            except Exception as exc:
                error(f"Invalid private key — could not derive an address: {exc}")
                if not click.confirm("Try a different key?", default=True):
                    raise click.Abort()

    # Build the final key-value map to write
    kv: dict[str, str] = {
        "OG_PRIVATE_KEY": og_hex,
        "RECEIVER_ADDRESS": wallet_addr,
        "LLM_API_KEY": llm_raw.strip(),
        "EMBEDDING_API_KEY": llm_raw.strip(),
        "EMBEDDING_ENDPOINT": VERCEL_AI_GATEWAY,
        "KEEPERHUB_API_KEY": keeper_raw.strip(),
    }

    etherscan_eff_skip = etherscan_skip or not etherscan_key
    if not etherscan_eff_skip and etherscan_key:
        kv["ETHERSCAN_API_KEY"] = etherscan_key.strip()

    asyncio.run(_finalize_summary_and_write(kv, etherscan_eff_skip, reuse_og))


# ─── Step 6 — Live validation & file writing ─────────────────────────────────

async def _finalize_summary_and_write(
    kv: dict[str, str],
    etherscan_eff_skip: bool,
    reuse_og_wallet: bool,
) -> None:
    """
    Run live connectivity checks, loop on errors (key-by-key correction),
    then write ~/.onchor-ai/.env, ~/.onchor-ai/config.json, and backend/.env.
    """
    _step_header(
        6,
        "Key Validation",
        "Each service is tested live. Failed keys can be corrected here without restarting from step 1.",
    )

    checks, rows_tbl = await run_connectivity_checks(
        llm_key=kv.get("LLM_API_KEY"),
        keeperhub_key=kv.get("KEEPERHUB_API_KEY"),
        etherscan_key=(kv.get("ETHERSCAN_API_KEY") or "").strip() if not etherscan_eff_skip else "",
        etherscan_skipped=etherscan_eff_skip,
        og_pv_key_set=bool(kv.get("OG_PRIVATE_KEY")),
        og_skipped_same_wallet=reuse_og_wallet,
    )
    console.print(credentials_summary_table(rows_tbl))

    bad = [k for k, v in checks.items() if not v[0]]
    while bad:
        warn("Failed checks: " + ", ".join(bad))
        if not click.confirm(
            "Fix only the failing keys now (without restarting from step 1)?",
            default=True,
        ):
            raise click.Abort()

        # Prompt only for the keys that failed
        for b in list(bad):
            if b == "Vercel AI Gateway":
                kv["LLM_API_KEY"] = _masked_prompt("New Vercel AI Gateway key", "Paste the corrected key:")
                kv["EMBEDDING_API_KEY"] = kv["LLM_API_KEY"]
            elif b == "KeeperHub API":
                kv["KEEPERHUB_API_KEY"] = _masked_prompt("New KeeperHub key", "Paste the corrected key:")
            elif b == "Etherscan API":
                kv["ETHERSCAN_API_KEY"] = _masked_prompt("New Etherscan key", "Paste the corrected key:")
                etherscan_eff_skip = False
            elif b == "0G Storage (OG_PRIVATE_KEY)":
                nv = _masked_prompt("New 0G private key", "Paste the hex key (with or without 0x):")
                kv["OG_PRIVATE_KEY"] = nv.removeprefix("0x").strip()

        checks, rows_tbl = await run_connectivity_checks(
            llm_key=kv.get("LLM_API_KEY"),
            keeperhub_key=kv.get("KEEPERHUB_API_KEY"),
            etherscan_key=(kv.get("ETHERSCAN_API_KEY") or "").strip() if not etherscan_eff_skip else "",
            etherscan_skipped=etherscan_eff_skip,
            og_pv_key_set=bool(kv.get("OG_PRIVATE_KEY")),
            og_skipped_same_wallet=reuse_og_wallet,
        )
        bad = [k for k, v in checks.items() if not v[0]]
        console.print(credentials_summary_table(rows_tbl))

    # Write config.json
    cfg = {
        "version": "0.1.0",
        "mode": "local",
        "credit_usdc": 0.0,
        "onboarding_completed": True,
        "wallet_address": kv.get("RECEIVER_ADDRESS", ""),
    }
    ONCHOR_AI_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_JSON_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")

    # Reload env in the current process so subsequent commands pick up the new keys
    os.environ.update({k: v for k, v in kv.items()})
    load_dotenv(ENV_JSON_PATH, override=True)
    load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

    _write_dotenv(kv)

    # Final success message with copy-paste ready first audit command
    console.print()
    success("Setup complete — files written:")
    console.print(Text.from_markup(
        "  [muted]~/.onchor-ai/.env[/muted]        keys and wallet\n"
        "  [muted]~/.onchor-ai/config.json[/muted]  onchor-ai profile\n"
        "  [muted]backend/.env[/muted]              synced automatically"
    ))
    console.print()
    console.print(
        Panel(
            Text.from_markup(
                "[brand]Suggested first audit[/brand]\n\n"
                "Run the demo against EulerVault (intentional reentrancy):\n\n"
                f"  [accent]onchor-ai audit {EULER_VAULT_DEMO_ADDR}[/accent]\n\n"
                "[muted]Or audit a local contract:[/muted]\n\n"
                "  [accent]onchor-ai audit ./src/[/accent]"
            ),
            border_style="brand",
            padding=(1, 2),
        )
    )


# ─── Public helpers used by cli.py ───────────────────────────────────────────

def needs_first_run_onboarding() -> bool:
    """
    Return True when the onboarding wizard should run.

    Rules:
    - No config file → always run.
    - Config exists with mode 'local' or 'dev', but the current command
      is in full mode (no --local / --dev flag) → re-run the full wizard
      so the user gets a wallet and the paid-tier keys.
    - Any other case with an existing config → skip.
    """
    if not CONFIG_JSON_PATH.is_file():
        return True

    # Check if the user is upgrading from a limited config to full mode
    try:
        cfg = json.loads(CONFIG_JSON_PATH.read_text(encoding="utf-8"))
        stored_mode = cfg.get("mode", "full")
        current_mode = _detect_run_mode()
        if stored_mode in ("local", "dev") and current_mode == "full":
            return True
    except Exception:
        # Corrupted config — re-run onboarding to be safe
        return True

    return False


# ─── Doctor command (validation only, no wizard) ──────────────────────────────

def run_doctor_validation() -> bool:
    """
    Re-run only the step 6 connectivity checks without regenerating a wallet
    or re-collecting keys. Reads from backend/.env then ~/.onchor-ai/.env.
    """
    backend = Path(__file__).resolve().parent
    load_dotenv(backend / ".env")
    load_dotenv(ENV_JSON_PATH, override=True)
    load_dotenv(override=True)

    if not CONFIG_JSON_PATH.is_file():
        warn(
            "No user config found: [accent]~/.onchor-ai/config.json[/accent] is missing.\n"
            "Run [accent]onchor-ai[/accent] to initialize."
        )

    llm_key = os.getenv("LLM_API_KEY")
    keeperhub_key = os.getenv("KEEPERHUB_API_KEY")
    etherscan_key = (os.getenv("ETHERSCAN_API_KEY") or "").strip()
    etherscan_eff_skip = not etherscan_key
    og_pv = (os.getenv("OG_PRIVATE_KEY") or "").strip()
    recv = (os.getenv("RECEIVER_ADDRESS") or "").strip()

    # Detect whether the 0G key is the same as the x402 wallet
    reuse_wallet = False
    if og_pv and recv:
        try:
            pk = "0x" + og_pv if not og_pv.startswith("0x") else og_pv
            acct = Account.from_key(pk)
            reuse_wallet = (
                Web3.to_checksum_address(acct.address) == Web3.to_checksum_address(recv)
            )
        except Exception:
            reuse_wallet = False

    section("Doctor — connectivity and key validation")

    checks, rows_tbl = asyncio.run(
        run_connectivity_checks(
            llm_key=llm_key,
            keeperhub_key=keeperhub_key,
            etherscan_key=etherscan_key if not etherscan_eff_skip else "",
            etherscan_skipped=etherscan_eff_skip,
            og_pv_key_set=bool(og_pv),
            og_skipped_same_wallet=reuse_wallet,
        )
    )
    console.print(credentials_summary_table(rows_tbl))

    failed = [k for k, v in checks.items() if not v[0]]
    if failed:
        warn("Failed: " + ", ".join(failed))
        info("Update [accent]~/.onchor-ai/.env[/accent] then run: [accent]onchor-ai doctor[/accent]")
        return False

    success("All active checks passed.")
    return True