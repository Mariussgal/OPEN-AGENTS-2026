# backend/keeper/direct_api.py
import os
import httpx
import logging
from typing import Optional
from payments.x402_client import sign_server_reward

logger = logging.getLogger(__name__)

FACILITATOR_URL  = os.getenv("X402_FACILITATOR_URL", "https://api.x402.org")
NETWORK          = "eip155:84532"

async def anchor_contribution(
    pattern_hash: str,
    root_hash_0g: str,
    contributor_address: str,
    amount_usdc: float = 0.05
) -> str:
    """
    Ancre une contribution IA on-chain.
    Si amount_usdc > 0, déclenche un vrai transfert USDC via le protocole x402.
    Le serveur (OG_PRIVATE_KEY) signe la récompense.
    """
    try:
        if amount_usdc <= 0:
            logger.info(f"⚓ Ancrage POC pour {pattern_hash} — Pas de récompense.")
            return "anchored_only"

        # 1. Signature du transfert USDC par le serveur (EIP-3009)
        # On arrondit pour éviter les erreurs de BigInt (ex: 0.15000000000000002)
        clean_amount = round(amount_usdc, 2)
        reward_payload = sign_server_reward(contributor_address, amount_usdc=clean_amount)
        
        # 2. Construction des requirements
        requirement = {
            "scheme": "exact",
            "network": NETWORK,
            "payTo": contributor_address,
            "asset": "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
            "price": f"${clean_amount:.2f}",
            "extra": {
                "name": "USD Coin",
                "symbol": "USDC",
                "decimals": 6,
                "version": "2",
                "chainId": 84532
            }
        }
        
        # 3. Construction du payload x402 complet
        payment_payload = {
            "x402Version": 2,
            "scheme": "exact",
            "network": NETWORK,
            "accepted": requirement,
            "payload": reward_payload
        }

        settle_body = {
            "x402Version": 2,
            "paymentPayload": payment_payload,
            "paymentRequirements": requirement # Singulier
        }

        logger.info(f"💰 Récompense x402 demandée : {clean_amount} USDC vers {contributor_address}")

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as http:
            resp = await http.post(f"{FACILITATOR_URL}/settle", json=settle_body)
            
            if not resp.is_success:
                logger.error(f"❌ Échec x402 settle: {resp.status_code} - {resp.text}")
                return "payment_failed"

            data = resp.json()
            tx_hash = data.get("transaction") 
            logger.info(f"✅ Vrai transfert USDC effectué ! TX: {tx_hash}")
            return tx_hash

    except Exception as e:
        logger.error(f"❌ Erreur x402 : {e}")
        return "error"

async def is_already_anchored(pattern_hash: str) -> bool:
    return False

async def poll_execution(exec_id: str) -> str:
    return exec_id