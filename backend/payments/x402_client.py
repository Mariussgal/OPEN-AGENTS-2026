# payments/x402_client.py
import asyncio
import base64
import json
import os
import secrets
import time

import click
import httpx
from eth_account import Account
from dotenv import load_dotenv

load_dotenv()

USDC_BASE_SEPOLIA = "0x036CbD53842c5426634e7929541eC2318f3dCF7e"
BASE_SEPOLIA_RPC = os.getenv("BASE_SEPOLIA_RPC_URL") or "https://sepolia.base.org"

ERC20_BALANCE_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
    }
]


def _usdc_balance_base_sepolia(address: str) -> float:
    from web3 import Web3

    w3 = Web3(Web3.HTTPProvider(BASE_SEPOLIA_RPC))
    c = w3.eth.contract(
        address=Web3.to_checksum_address(USDC_BASE_SEPOLIA),
        abi=ERC20_BALANCE_ABI,
    )
    raw = c.functions.balanceOf(Web3.to_checksum_address(address)).call()
    return float(raw) / 1_000_000.0


async def _assert_usdc_covers_quote(private_key: str, price_usd: float) -> None:
    """Block paid audit when wallet does not have enough USDC on Base Sepolia."""
    account = Account.from_key(private_key)
    bal = await asyncio.to_thread(_usdc_balance_base_sepolia, account.address)
    if bal + 1e-6 < price_usd:
        raise click.ClickException(
            f"Solde USDC Base Sepolia insuffisant : {bal:.4f} USDC (requis ~{price_usd:.4f} USDC). "
            "Alimente le portefeuille : https://faucet.circle.com (Base Sepolia)."
        )


def _sign_eip3009(
    private_key: str,
    asset_address: str,
    token_name: str,
    token_version: str,
    chain_id: int,
    pay_to: str,
    amount: str,
    max_timeout_seconds: int,
) -> dict:
    """
    Signe une autorisation EIP-3009 (transferWithAuthorization).
    Utilisé par le client pour payer un audit ou par le serveur pour payer une récompense.
    Le facilitateur exécute le transfert USDC on-chain. Gaz gratuit pour le signataire.
    """
    account      = Account.from_key(private_key)
    valid_after  = 0
    valid_before = int(time.time()) + max_timeout_seconds
    nonce_bytes  = secrets.token_bytes(32)  # bytes32 aléatoire anti-replay
    nonce_hex    = "0x" + nonce_bytes.hex()

    signed = account.sign_typed_data(
        domain_data={
            "name":              token_name,
            "version":           token_version,
            "chainId":           chain_id,
            "verifyingContract": asset_address,
        },
        message_types={
            "TransferWithAuthorization": [
                {"name": "from",        "type": "address"},
                {"name": "to",          "type": "address"},
                {"name": "value",       "type": "uint256"},
                {"name": "validAfter",  "type": "uint256"},
                {"name": "validBefore", "type": "uint256"},
                {"name": "nonce",       "type": "bytes32"},
            ]
        },
        message_data={
            "from":        account.address,
            "to":          pay_to,
            "value":       int(amount),
            "validAfter":  valid_after,
            "validBefore": valid_before,
            "nonce":       nonce_hex,
        },
    )

    return {
        "signature": "0x" + signed.signature.hex(),
        "authorization": {
            "from":        account.address,
            "to":          pay_to,
            "value":       amount,
            "validAfter":  str(valid_after),
            "validBefore": str(valid_before),
            "nonce":       nonce_hex,
        },
    }

def sign_server_reward(contributor_address: str, amount_usdc: float = 0.15) -> dict:
    """
    Génère la signature EIP-3009 pour que le serveur paie un contributeur.
    Réutilise la clé privée du serveur (OG_PRIVATE_KEY).
    """
    private_key = os.getenv("OG_PRIVATE_KEY")
    if not private_key:
        raise ValueError("Missing OG_PRIVATE_KEY for refund path")

    # Configuration Base Sepolia USDC
    USDC_ADDRESS = "0x036CbD53842c5426634e7929541eC2318f3dCF7e"
    CHAIN_ID = 84532
    
    # Conversion en unités atomiques (6 décimales pour USDC) avec arrondi strict
    amount_atomic = str(int(round(amount_usdc, 2) * 1_000_000))

    return _sign_eip3009(
        private_key=private_key,
        asset_address=USDC_ADDRESS,
        token_name="USD Coin",
        token_version="USDC",
        chain_id=CHAIN_ID,
        pay_to=contributor_address,
        amount=amount_atomic,
        max_timeout_seconds=3600  # 1 heure de validité
    )

def _build_x_payment_header(requirement: dict, private_key: str, price_usd: float) -> str:
    """Construit le header X-PAYMENT standard pour le protocole x402."""
    chain_id = int(requirement["network"].split(":")[1])
    # Conversion du prix numérique en unités atomiques USDC (6 décimales)
    amount_atomic = str(int(price_usd * 1_000_000))
    
    inner    = _sign_eip3009(
        private_key         = private_key,
        asset_address       = requirement["asset"],
        token_name          = requirement["extra"]["name"],
        token_version       = requirement["extra"]["version"],
        chain_id            = chain_id,
        pay_to              = requirement["payTo"],
        amount              = amount_atomic,
        max_timeout_seconds = 3600
    )
    
    return base64.b64encode(json.dumps({
        "x402Version": 2,
        "scheme":      requirement["scheme"],
        "network":     requirement["network"],
        "accepted":    requirement,
        "payload":     inner,
    }).encode()).decode()

async def fetch_quote(api_url: str, path: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{api_url}/audit/quote", params={"path": path})
        resp.raise_for_status()
        return resp.json()


async def prepare_x_payment(api_url: str, path: str) -> tuple[str, float, int]:
    """Fetch quote, ask for user confirmation, sign EIP-3009 authorization.

    Returns:
        (x_payment_header, price_usd, nb_files)

    Raises:
        click.Abort if user declines payment.
        click.ClickException if private key is missing.
    """
    private_key = os.getenv("OG_PRIVATE_KEY")
    if not private_key:
        raise click.ClickException("Missing private key OG_PRIVATE_KEY.")

    # 1. Quote
    click.secho("  ⟳  Fetching quote...", fg="cyan")
    quote    = await fetch_quote(api_url, path)
    price    = float(quote["price_usd"])
    nb_files = quote["files_count"]
    reqs     = quote["payment_requirements"]

    click.secho(f"  →  {nb_files} file(s) detected — Price: {price} USDC", fg="yellow")

    await _assert_usdc_covers_quote(private_key, price)

    if not click.confirm("  Proceed with x402 payment?"):
        raise click.Abort()

    # 2. Signature EIP-3009
    click.secho("  ⟳  Signing payment (EIP-3009)...", fg="cyan")
    x_payment = _build_x_payment_header(reqs[0], private_key, price)
    click.secho("  ✓  Payload signed (EIP-712)", fg="green")

    return x_payment, price, nb_files


async def run_paid_audit(api_url: str, path: str) -> dict:
    """Paid non-streaming mode (legacy). Kept for backward compatibility."""
    x_payment, _price, _nb = await prepare_x_payment(api_url, path)

    click.secho("  ⟳  Envoi au serveur avec X-PAYMENT...", fg="cyan")
    async with httpx.AsyncClient(timeout=300.0) as http:
        resp = await http.post(
            f"{api_url}/audit",
            params={"path": path},
            headers={"X-PAYMENT": x_payment},
        )

        if resp.status_code in (400, 402):
            try:
                detail = resp.json()
            except Exception:
                detail = resp.text
            raise click.ClickException(f"❌ {resp.status_code} : {detail}")

        resp.raise_for_status()
        return resp.json()