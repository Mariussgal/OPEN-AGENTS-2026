# backend/keeper/mcp_tools.py
"""
Outils MCP pour l'agent.
L'outil anchor_finding_mcp déclenche maintenant un paiement RÉEL via x402.
"""

import logging
from keeper.direct_api import anchor_contribution

logger = logging.getLogger(__name__)


async def anchor_finding_mcp(pattern_hash: str, root_hash_0g: str, contributor_address: str = None) -> str:
    """
    Ancre une découverte on-chain et déclenche le paiement de la récompense (0.15 USDC).

    Args:
        pattern_hash       : SHA-256 du snippet (0x...)
        root_hash_0g       : Merkle root 0G Storage (0x...)
        contributor_address : Adresse du portefeuille qui recevra les USDC (Base Sepolia).
    """
    if not pattern_hash.startswith("0x"):
        pattern_hash = "0x" + pattern_hash
    if not root_hash_0g.startswith("0x"):
        root_hash_0g = "0x" + root_hash_0g

    logger.info(f"[Agent tool 7] anchor_finding_mcp — Ancrage Proof-of-Concept pour {contributor_address} (0.0 USDC)")

    # Appelle la nouvelle logique dans direct_api.py qui gère le protocole x402
    # L'agent ancre sans récompense monétaire automatique
    tx_hash = await anchor_contribution(pattern_hash, root_hash_0g, contributor_address, amount_usdc=0.0)

    if tx_hash == "payment_failed":
        logger.error("[Agent tool 7] Échec du paiement x402.")
    elif tx_hash == "already_anchored":
        logger.info("[Agent tool 7] Pattern déjà ancré — skip")
    else:
        logger.info(f"[Agent tool 7] Succès ! Récompense envoyée — tx: {tx_hash}")

    return tx_hash