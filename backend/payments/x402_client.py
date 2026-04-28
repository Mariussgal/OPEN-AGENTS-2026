# payments/x402_client.py
import os
import time
import json
import base64
import secrets
import click
import httpx
from eth_account import Account
from dotenv import load_dotenv

load_dotenv()

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
            "nonce":       nonce_bytes,
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
        raise ValueError("OG_PRIVATE_KEY manquante pour le remboursement")

    # Configuration Base Sepolia USDC
    USDC_ADDRESS = "0x036CbD53842c5426634e7929541eC2318f3dCF7e"
    CHAIN_ID = 84532
    
    # Conversion en unités atomiques (6 décimales pour USDC) avec arrondi strict
    amount_atomic = str(int(round(amount_usdc, 2) * 1_000_000))

    return _sign_eip3009(
        private_key=private_key,
        asset_address=USDC_ADDRESS,
        token_name="USD Coin",
        token_version="2",
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

async def run_paid_audit(api_url: str, path: str) -> dict:
    private_key = os.getenv("OG_PRIVATE_KEY")
    if not private_key:
        raise click.ClickException("Clé privée OG_PRIVATE_KEY manquante.")

    resource_url = f"{api_url}/audit"

    # 1. Quote
    click.secho("  ⟳  Récupération du prix...", fg="cyan")
    quote    = await fetch_quote(api_url, path)
    price    = float(quote["price_usd"])
    nb_files = quote["files_count"]
    reqs     = quote["payment_requirements"]

    click.secho(f"  →  {nb_files} fichier(s) détecté(s) — Prix : {price} USDC", fg="yellow")

    if not click.confirm("  Procéder au paiement x402 ?"):
        raise click.Abort()

    # 2. Signature EIP-3009
    click.secho("  ⟳  Signature du paiement (EIP-3009)...", fg="cyan")
    x_payment = _build_x_payment_header(reqs[0], private_key, price)
    click.secho("  ✓  Payload signé (EIP-712)", fg="green")

    # 3. Envoi au serveur avec X-PAYMENT
    click.secho("  ⟳  Envoi au serveur avec X-PAYMENT...", fg="cyan")
    async with httpx.AsyncClient(timeout=300.0) as http:
        resp = await http.post(
            resource_url,
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