"""
Assistant d'onboarding post-install (~/.onchor-ai/) : portefeuille, faucets,
clés Vercel / KeeperHub / Etherscan / 0G, tableau de synthèse et écriture .env + config.json.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import click
import httpx
from dotenv import load_dotenv
from eth_account import Account
from keeper.hub_anchor import KEEPERHUB_VALIDATE_READ_FALLBACK_URLS
from rich.panel import Panel
from rich.text import Text
from web3 import Web3

from ui import console, credentials_summary_table, error, info, section, success, warn

# ─── Chemins ─────────────────────────────────────────────────────────────────
ONCHOR_AI_DIR = Path.home() / ".onchor-ai"
CONFIG_JSON_PATH = ONCHOR_AI_DIR / "config.json"
ENV_JSON_PATH = ONCHOR_AI_DIR / ".env"


def hub_headers(api_key: str) -> dict[str, str]:
    from keeper.hub_anchor import _authorization_headers as _hdr

    return _hdr(api_key)


# ─── Réseaux & faucets (URLs du roadmap) ──────────────────────────────────────
SEP_ETH_MIN_WEI = Web3.to_wei(0.005, "ether")
BASE_USDC_MIN = 1.0  # USDC minimaux conseillés (affichage ; check >= 1 * 1e6 atomiques si strict)
OZ_G_ETH_MIN_WEI = Web3.to_wei(0.001, "ether")

SEP_RPC = os.getenv("SEPOLIA_RPC_URL") or "https://rpc.sepolia.org"
BASE_SEP_RPC = os.getenv("BASE_SEPOLIA_RPC_URL") or "https://sepolia.base.org"
USDC_BASE_SEPOLIA = "0x036CbD53842c5426634e7929541eC2318f3dCF7e"
OZ_G_RPC_DEFAULT = os.getenv("OG_EVM_RPC") or "https://evmrpc-testnet.0g.ai"

VERCEL_AI_GATEWAY = "https://ai-gateway.vercel.sh/v1"
VERCEL_AI_DOCS_URL = (
    "https://vercel.com/docs/ai-gateway"
)
KEEPERHUB_SETTINGS_KEYS = (
    "https://app.keeperhub.com/settings"
)

EULER_VAULT_DEMO_ADDR = "0x49Ca165Bd6AEe88825f59c557bC52A685e0594B5"


# Délai par RPC balance (soldes onboarding)
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


def needs_first_run_onboarding() -> bool:
    """True tant que ~/.onchor-ai/config.json n'existe pas."""
    return not CONFIG_JSON_PATH.is_file()


async def keeperhub_validate_read_probe(api_key: str) -> tuple[bool, str]:
    """
    Validation lecture Bearer uniquement — pas d’appel POST /execute/contract-call
    (évite tout effet destructif ou facturation potentielle lors des installs répétées).

    KEEPERHUB_VALIDATION_URL : URL GET prioritaire si déjà documentée publiquement.
    KEEPERHUB_VALIDATION_URL_FALLBACKS : liste CSV (voir hub_anchor), essayée dans l’ordre.
    """
    if not (api_key or "").strip():
        return False, "clé vide"
    headers = hub_headers(api_key)
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
                return False, f"Bearer refusé (401) — {url}"
            if r.status_code == 403:
                return True, f"GET lecture → HTTP 403 ({url}) — Bearer accepté côté API"
            if 200 <= r.status_code < 300:
                return True, f"GET lecture → HTTP {r.status_code} ({url})"
            if r.status_code == 404:
                last_msg = f"404 sur {url} — chemin peut avoir changé côté KeeperHub"
                continue
            if r.status_code == 429:
                return False, "HTTP 429 — rate-limit KeeperHub ; réessaie dans un instant"
            if r.status_code < 500:
                return True, f"GET lecture → HTTP {r.status_code} ({url})"
            last_msg = f"HTTP {r.status_code} sur {url}"

    return (
        False,
        last_msg
        or (
            "Aucune route GET pour valider la clé — définit KEEPERHUB_VALIDATION_URL "
            "(URL documentée KeeperHub ou contact support)."
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
    """(checks dict pour logique erreur, rows pour tableau rich)."""

    def etherscan_ping() -> tuple[bool, str]:
        if etherscan_skipped:
            return True, "ignoré (option choisie)"
        if not etherscan_key:
            return False, "clé vide"
        try:
            u = (
                "https://api-sepolia.etherscan.io/api"
                "?module=account&action=balance&address=0x0&tag=latest"
                f"&apikey={etherscan_key}"
            )
            with httpx.Client(timeout=12.0) as client:
                r = client.get(u)
            try:
                j = r.json()
            except Exception:
                return False, "réponse non JSON"
            if j.get("status") == "1" or j.get("message") == "OK":
                return True, "OK"
            msg = str(j.get("result", j.get("message", "")))[:120]
            if "Invalid API Key" in msg or ("invalid" in msg.lower()):
                return False, msg or "jeton invalide"
            return True, msg or "OK"
        except Exception as e:
            return False, str(e)[:80]

    out: dict[str, tuple[bool, str]] = {}

    if llm_key:
        try:
            from openai import OpenAI

            client = OpenAI(api_key=llm_key, base_url=VERCEL_AI_GATEWAY, timeout=20.0)
            _ = client.chat.completions.create(
                model=os.getenv("ONBOARDING_GATEWAY_MODEL") or "anthropic/claude-3-5-haiku-20241022",
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=8,
            )
            out["Vercel AI Gateway"] = (True, "complétion courte OK")
        except Exception as e:
            out["Vercel AI Gateway"] = (False, str(e)[:120])
    else:
        out["Vercel AI Gateway"] = (False, "clé vide")

    out["KeeperHub API"] = await keeperhub_validate_read_probe(keeperhub_key or "")

    ok_e, detail_e = etherscan_ping()
    if etherscan_skipped:
        ok_e_final = True
    else:
        ok_e_final = ok_e

    out["Etherscan API"] = (ok_e_final, detail_e)

    out["0G Storage (OG_PRIVATE_KEY)"] = (
        (True, "réutilise le portefeuille x402")
        if og_skipped_same_wallet and og_pv_key_set
        else ((True, "clé fournie") if og_pv_key_set else (False, "clé vide"))
    )

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


def sep_eth_balance(addr: str) -> int:
    w3 = Web3(Web3.HTTPProvider(SEP_RPC))
    return int(w3.eth.get_balance(Web3.to_checksum_address(addr)))


def base_usdc_balance(addr: str) -> float:
    w3 = Web3(Web3.HTTPProvider(BASE_SEP_RPC))
    c = w3.eth.contract(
        address=Web3.to_checksum_address(USDC_BASE_SEPOLIA),
        abi=ERC20_ABI,
    )
    raw = c.functions.balanceOf(Web3.to_checksum_address(addr)).call()
    return float(raw) / 1e6


def oz_g_eth_balance(addr: str) -> int:
    w3 = Web3(Web3.HTTPProvider(OZ_G_RPC_DEFAULT))
    return int(w3.eth.get_balance(Web3.to_checksum_address(addr)))


async def _balance_call(
    fn, addr: str
) -> tuple[bool, int | float | None, str | None]:
    """(rpc_ok, valeur, message_erreur)."""
    try:
        val = await asyncio.wait_for(asyncio.to_thread(fn, addr), timeout=BALANCE_RPC_TIMEOUT)
        return True, val, None
    except asyncio.TimeoutError:
        return False, None, f"délai dépassé ({int(BALANCE_RPC_TIMEOUT)}s)"
    except Exception as e:
        return False, None, str(e)[:120]


async def balances_ok(address: str) -> tuple[bool, list[str], bool]:
    """
    Retourne ``(tous_les_soldes_ok, lignes, problème_RPC)``.
    ``problème_RPC`` si timeout/erreur sur au moins un endpoint (pour proposer « continuer sans vérifier »).
    """
    lines: list[str] = []

    sr, eth_s, s_err = await _balance_call(sep_eth_balance, address)
    ur, usdc_amt, u_err = await _balance_call(base_usdc_balance, address)
    or_ok, wei_og, o_err = await _balance_call(oz_g_eth_balance, address)

    rpc_issue = not (sr and ur and or_ok)

    if not sr:
        lines.append(
            f"[warn]⚠[/warn] ETH Ethereum Sepolia (KeeperHub / gas) — impossible de vérifier ({s_err})"
        )
    else:
        assert eth_s is not None
        eth_ok_bool = int(eth_s) >= SEP_ETH_MIN_WEI
        sty = "[ok]✔[/ok]" if eth_ok_bool else "[danger]✘[/danger]"
        lines.append(
            f"{sty} ETH Ethereum Sepolia — {Web3.from_wei(int(eth_s), 'ether')} ETH · "
            f"min conseillé {Web3.from_wei(SEP_ETH_MIN_WEI, 'ether')} ETH · sepoliafaucet.com",
        )

    if not ur:
        lines.append(
            f"[warn]⚠[/warn] USDC Base Sepolia (x402) — impossible de vérifier ({u_err})"
        )
    else:
        assert usdc_amt is not None
        u_ok = usdc_amt >= BASE_USDC_MIN
        sty = "[ok]✔[/ok]" if u_ok else "[danger]✘[/danger]"
        lines.append(
            f"{sty} USDC Base Sepolia — {usdc_amt:.4f} USDC · "
            f"min conseillé ~{BASE_USDC_MIN:g} · faucet.circle.com",
        )

    if not or_ok:
        lines.append(
            f"[warn]⚠[/warn] ETH réseau 0G (Galileo) — impossible de vérifier ({o_err})"
        )
    else:
        assert wei_og is not None
        og_ok_bool = int(wei_og) >= OZ_G_ETH_MIN_WEI
        sty = "[ok]✔[/ok]" if og_ok_bool else "[danger]✘[/danger]"
        lines.append(
            f"{sty} ETH Galileo / 0G — {Web3.from_wei(int(wei_og), 'ether')} · "
            f"min conseillé {Web3.from_wei(OZ_G_ETH_MIN_WEI, 'ether')} · faucet.0g.ai",
        )

    eth_ok = bool(sr and eth_s is not None and int(eth_s) >= SEP_ETH_MIN_WEI)
    usdc_ok_b = bool(ur and usdc_amt is not None and usdc_amt >= BASE_USDC_MIN)
    og_ok_fin = bool(or_ok and wei_og is not None and int(wei_og) >= OZ_G_ETH_MIN_WEI)

    all_green = (not rpc_issue) and eth_ok and usdc_ok_b and og_ok_fin
    return all_green, lines, rpc_issue


def _wallet_step() -> tuple[str, str]:
    """Retourne (private_key_hex_sans_prefixe_0x, address checksummée)."""
    acct = Account.create()
    key = acct.key.hex()
    addr = Web3.to_checksum_address(acct.address)
    section("Étape 2 — Portefeuille local")

    panel_body = (
        "[accent]Adresse[/accent] · ce portefeuille financera les audits (x402) et apparaît comme receveur.\n\n"
        f"[label]{addr}[/label]\n\n"
        "[label]Faucets (testnet)[/label] — utilise [accent]la même[/accent] adresse partout :\n"
        "  • ETH Ethereum Sepolia — min conseillé ~0,005 ETH — gas KeeperHub — "
        "[info]https://sepoliafaucet.com[/info]\n"
        "  • USDC Base Sepolia — min conseillé ~1 USDC — paiements x402 — "
        "[info]https://faucet.circle.com[/info]\n"
        "  • ETH Galileo / 0G testnet — min conseillé ~0,001 — stockage décentralisé — "
        "[info]https://faucet.0g.ai[/info]\n"
    )
    console.print(Panel(panel_body.strip(), border_style="brand.dim", title="Finance le portefeuille"))
    click.prompt("\nUne fois tes comptes crédités, presse Entrée pour vérifier les soldes automatiquement", default="", show_default=False)

    while True:
        all_green, lines_out, rpc_issue = asyncio.run(balances_ok(addr))
        for line in lines_out:
            console.print(Text.from_markup(line))

        if rpc_issue:
            if click.confirm(
                "Certaines vérifications RPC ont échoué ou expiré (délai "
                f"{int(BALANCE_RPC_TIMEOUT)}s par réseau). Continuer sans contrôler les soldes ? "
                "Tu pourras relancer ensuite : onchor-ai doctor",
                default=False,
            ):
                warn("Poursuite sans contrôle complet des faucets — réessaie quand la connexion est stable.")
                return key, addr
            click.prompt("Entrée pour réessayer les appels RPC…", default="", show_default=False)
            continue

        if all_green:
            success("Soldes conformes.")
            return key, addr

        if not click.confirm("Soldes encore insuffisants — réessaie après les faucets. Re-vérifier ?", default=True):
            break
        click.prompt("(Entrée quand tu es prêt)", default="", show_default=False)

    return key, addr


def _masked_prompt(label: str, text: str) -> str:
    click.echo("")
    console.print(Text.from_markup(f"[muted]{text}[/muted]"))
    return (click.prompt(label, hide_input=True, confirmation_prompt=False) or "").strip()


def _merge_dotenv_file(path: Path, updates: dict[str, str]) -> None:
    """Ajoute/remplace uniquement les clés onboarding à un .env existant (préservant les commentaires/autres lignes)."""
    used_keys: set[str] = set()
    out_lines: list[str] = []
    if path.is_file():
        for raw in path.read_text(encoding="utf-8").splitlines():
            if "=" in raw and not raw.strip().startswith("#"):
                k, sep, tail = raw.partition("=")
                kk = k.strip()
                if kk in updates:
                    vv = updates[kk].replace("\n", "")
                    out_lines.append(f"{kk}={vv}")
                    used_keys.add(kk)
                    continue
            out_lines.append(raw)
    for kk, vv in updates.items():
        if kk not in used_keys:
            out_lines.append(f"{kk}={vv.replace(chr(10), '').replace(chr(13), '')}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")


def _write_dotenv(kv: dict[str, str]) -> None:
    KEEPER_MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    lines = []
    for k in sorted(kv.keys()):
        v = kv[k].replace("\n", "")
        lines.append(f"{k}={v}")
    full = "\n".join(lines) + "\n"
    ENV_JSON_PATH.write_text(full, encoding="utf-8")

    cli_env = Path(__file__).resolve().parent / ".env"
    _merge_dotenv_file(cli_env, kv)


def run_onboarding_wizard() -> None:
    """Blocage complet jusqu’à fin du flux ou interruption."""
    if os.environ.get("ONCHOR_SKIP_ONBOARDING", "").strip() in ("1", "true", "yes"):
        warn("ONCHOR_SKIP_ONBOARDING actif — assistant ignoré.")
        return

    section("Onboarding Onchor.ai")
    info(
        "Configuration initiale : portefeuille, clés Vercel AI Gateway, KeeperHub, "
        "optionnellement Etherscan et 0G Storage."
    )

    pv, wallet_addr = _wallet_step()

    click.echo("")
    console.print(Text.from_markup(
        "[label]Étape 3 — Vercel AI Gateway[/label]\n"
        "[muted]Cette clé alimente les modèles claude-haiku et claude-sonnet qui analysent tes contrats.[/muted]\n"
        f"[info]{VERCEL_AI_DOCS_URL}[/info]",
    ))
    llm_raw = click.prompt(
        "Clé API Vercel AI Gateway",
        hide_input=True,
        prompt_suffix=" › ",
        default=os.getenv("LLM_API_KEY") or "",
    )
    if not str(llm_raw).strip():
        error("Une clé Vercel AI Gateway est requise.")
        raise click.Abort()

    click.echo("")
    console.print(Text.from_markup(
        "[label]Étape 4 — KeeperHub[/label]\n"
        "[muted]KeeperHub ancres tes résultats on-chain via un portefeuille MPC ; tu ne gères pas le gas KeeperHub dédié ainsi.[/muted]\n"
        f"Déjà une clé ? [accent]Réglages › API Keys[/accent] · [info]{KEEPERHUB_SETTINGS_KEYS}[/info]",
    ))
    keeper_raw = click.prompt(
        "Clé KeeperHub API",
        hide_input=True,
        prompt_suffix=" › ",
        default=os.getenv("KEEPERHUB_API_KEY") or "",
    )
    if not str(keeper_raw).strip():
        error("Une clé KeeperHub est requise pour l’ancrage par défaut.")
        raise click.Abort()

    click.echo("")
    console.print(Text.from_markup(
        "[label]Étape 5 — Etherscan[/label]\n"
        "[muted]Uniquement si tu prévois d’auditer des adresses on-chain (ex.[/muted] "
        "[accent]onchor-ai audit 0x…[/accent][muted]).[/muted]\n"
        "[info]https://etherscan.io/apis[/info]",
    ))
    etherscan_skip = click.confirm(
        "Ignorer Etherscan (audits fichier local uniquement) ?",
        default=False,
    )
    etherscan_key = ""
    if not etherscan_skip:
        etherscan_key = (
            click.prompt("Clé API Etherscan", hide_input=True, prompt_suffix=" › ").strip()
        )

    click.echo("")
    console.print(Text.from_markup(
        "[label]Étape 6 — Clé privée 0G Storage[/label]\n"
        "[muted]Signe les uploads de patterns vers la mémoire collective décentralisée (vault 0G).[/muted]",
    ))
    reuse_og = click.confirm(
        "Réutiliser la clé privée générée à l’étape 2 (cas le plus simple) ?",
        default=True,
    )
    raw_og = pv if reuse_og else (
        click.prompt(
            "Clé privée 0G (hex, avec ou sans 0x)",
            hide_input=True,
            prompt_suffix=" › ",
        )
        or ""
    ).strip()
    og_hex = raw_og.removeprefix("0x").strip()
    if not og_hex:
        error("Une clé privée 0G est requise (ou choisis la réutilisation du portefeuille).")
        raise click.Abort()

    kv: dict[str, str] = {
        "OG_PRIVATE_KEY": og_hex,
        "RECEIVER_ADDRESS": wallet_addr,
        "LLM_API_KEY": llm_raw.strip(),
        "EMBEDDING_API_KEY": llm_raw.strip(),
        "EMBEDDING_ENDPOINT": VERCEL_AI_GATEWAY,
        "KEEPERHUB_API_KEY": keeper_raw.strip(),
    }

    etherscan_eff_skip = etherscan_skip or not etherscan_key
    if etherscan_eff_skip:
        kv.pop("ETHERSCAN_API_KEY", None)
    elif etherscan_key:
        kv["ETHERSCAN_API_KEY"] = etherscan_key.strip()

    asyncio.run(_finalize_summary_and_write(kv, etherscan_eff_skip, reuse_og))


async def _finalize_summary_and_write(
    kv: dict[str, str],
    etherscan_eff_skip: bool,
    reuse_og_wallet: bool,
) -> None:
    section("Étape 7 — Récapitulatif et validation")
    info(
        "Chaque ligne est testée automatiquement. "
        "Une clé en erreur peut être ré-entrée seule dans cette étape — sans reprendre l’assistant depuis le début."
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
        warn("Certaines vérifications ont échoué : " + ", ".join(bad))
        if not click.confirm(
            "Corriger uniquement les clés en erreur maintenant (même étape — pas depuis l’étape 1) ?",
            default=True,
        ):
            raise click.Abort()

        for b in list(bad):
            if b == "Vercel AI Gateway":
                kv["LLM_API_KEY"] = _masked_prompt(
                    "Nouvelle clé Vercel AI Gateway",
                    "Colle la clé corrigée :",
                )
                kv["EMBEDDING_API_KEY"] = kv["LLM_API_KEY"]
            elif b == "KeeperHub API":
                kv["KEEPERHUB_API_KEY"] = _masked_prompt(
                    "Nouvelle clé KeeperHub",
                    "Colle la clé corrigée :",
                )
            elif b == "Etherscan API":
                kv["ETHERSCAN_API_KEY"] = _masked_prompt(
                    "Nouvelle clé Etherscan",
                    "Colle la clé corrigée :",
                )
                etherscan_eff_skip = False
            elif b == "0G Storage (OG_PRIVATE_KEY)":
                nv = _masked_prompt(
                    "Nouvelle clé privée 0G",
                    "Colle la clé hex (sans 0x ou avec) :",
                )
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

    cfg = {
        "version": "0.1.0",
        "mode": "local",
        "credit_usdc": 0.0,
        "onboarding_completed": True,
        "wallet_address": kv.get("RECEIVER_ADDRESS", ""),
    }
    KEEPER_MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_JSON_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")

    os.environ.update({k: v for k, v in kv.items()})
    load_dotenv(ENV_JSON_PATH, override=True)
    load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

    _write_dotenv(kv)
    success("Fichiers écrits : ~/.onchor-ai/.env · ~/.onchor-ai/config.json · backend/.env")

    section("Premier audit suggéré")

    body = Text.from_markup(
        "[brand]EulerVault.sol[/brand] (Sepolia) — commande prête à copier :\n\n"
        f"[accent]onchor-ai audit {EULER_VAULT_DEMO_ADDR}[/accent]"
    )
    console.print(Panel(body, border_style="brand", padding=(1, 2)))


def run_doctor_validation() -> bool:
    """
    Rejoue uniquement les tests de l’étape 7 (sans regénérer de portefeuille ni tout re-saisir).
    Charge backend/.env puis ~/.onchor-ai/.env.
    """
    backend = Path(__file__).resolve().parent
    load_dotenv(backend / ".env")
    load_dotenv(ENV_JSON_PATH, override=True)
    load_dotenv(override=True)

    if not CONFIG_JSON_PATH.is_file():
        warn(
            "Pas de configuration utilisateur : [accent]~/.onchor-ai/config.json[/accent] absent. "
            "`doctor` ne lit alors guère les clés que depuis [accent]backend/.env[/accent] ou ton shell — "
            "un tableau tout en erreur peut donc tromper. "
            "Pour une install propre : [accent]onchor-ai init[/accent] puis, au besoin, le premier passage "
            "[accent]onchor-ai[/accent] (assistant onboarding) pour remplir [accent]~/.onchor-ai/[/accent].",
        )

    llm_key = os.getenv("LLM_API_KEY")
    keeperhub_key = os.getenv("KEEPERHUB_API_KEY")
    etherscan_key = (os.getenv("ETHERSCAN_API_KEY") or "").strip()
    etherscan_eff_skip = not etherscan_key
    og_pv = (os.getenv("OG_PRIVATE_KEY") or "").strip()
    recv = (os.getenv("RECEIVER_ADDRESS") or "").strip()

    reuse_wallet = False
    if og_pv and recv:
        try:
            pk = "0x" + og_pv if not og_pv.startswith("0x") else og_pv
            acct = Account.from_key(pk)
            reuse_wallet = (
                Web3.to_checksum_address(acct.address)
                == Web3.to_checksum_address(recv)
            )
        except Exception:
            reuse_wallet = False

    section("Doctor — validation des accès et clés")

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
        warn("Échec(s) : " + ", ".join(failed))
        info("Mets à jour ~/.onchor-ai/.env puis relance : [accent]onchor-ai doctor[/accent]")
        return False

    success("Les vérifications actives sont au vert.")
    return True

