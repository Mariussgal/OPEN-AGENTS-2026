# backend/keeper/direct_api.py
import os
import httpx
import logging
import base64
import json
from typing import Optional
from payments.x402_client import sign_server_reward

logger = logging.getLogger(__name__)

FACILITATOR_URL  = os.getenv("X402_FACILITATOR_URL", "https://api.x402.org")
NETWORK          = "eip155:84532"
API_BASE_URL      = os.getenv("API_BASE_URL", "http://localhost:8000")

async def anchor_contribution(
    pattern_hash: str,
    root_hash_0g: str,
    contributor_address: str,
    amount_usdc: float = 0.05
) -> str:
    """
    Ancre une contribution on-chain.
    Si amount_usdc > 0 → transfert USDC direct (ERC-20) signé par le serveur.
    Note : x402 est pour paiements ENTRANTS (client→serveur), pas sortants.
    """
    try:
        if amount_usdc <= 0:
            logger.info(f"⚓ Ancrage POC pour {pattern_hash} — Pas de récompense.")
            return "anchored_only"

        from web3 import Web3
        from eth_account import Account

        private_key = os.getenv("OG_PRIVATE_KEY")
        if not private_key:
            raise ValueError("OG_PRIVATE_KEY manquante")

        clean_amount  = round(amount_usdc, 2)
        amount_atomic = int(clean_amount * 1_000_000)   # 6 décimales USDC

        w3      = Web3(Web3.HTTPProvider("https://sepolia.base.org"))
        account = Account.from_key(private_key)

        usdc = w3.eth.contract(
            address=Web3.to_checksum_address("0x036CbD53842c5426634e7929541eC2318f3dCF7e"),
            abi=[{
                "inputs": [{"name": "_to", "type": "address"}, {"name": "_value", "type": "uint256"}],
                "name": "transfer",
                "outputs": [{"name": "", "type": "bool"}],
                "stateMutability": "nonpayable",
                "type": "function"
            }]
        )

        # Vérifie le solde ETH avant d'envoyer
        eth_balance = w3.eth.get_balance(account.address)
        gas_estimate = 80_000
        gas_price    = w3.eth.gas_price
        gas_needed   = gas_estimate * gas_price

        if eth_balance < gas_needed:
            eth_needed = w3.from_wei(gas_needed, 'ether')
            eth_have   = w3.from_wei(eth_balance, 'ether')
            logger.error(
                f"❌ Gas insuffisant — besoin: {eth_needed:.6f} ETH, "
                f"disponible: {eth_have:.6f} ETH\n"
                f"   → Recharge le wallet serveur : {account.address}\n"
                f"   → Faucet Base Sepolia : https://faucet.quicknode.com/base/sepolia"
            )
            return "no_gas"

        tx = usdc.functions.transfer(
            Web3.to_checksum_address(contributor_address),
            amount_atomic
        ).build_transaction({
            "from":     account.address,
            "nonce":    w3.eth.get_transaction_count(account.address),
            "gas":      gas_estimate,
            "gasPrice": gas_price,
            "chainId":  84532,
        })

        logger.info(f"💰 Envoi {clean_amount} USDC → {contributor_address} (ERC-20 direct)")
        signed  = account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)

        hex_hash = tx_hash.hex()
        if receipt.status == 1:
            logger.info(f"✅ Récompense envoyée — tx: {hex_hash}")
            return hex_hash
        else:
            logger.error(f"❌ Transaction revertée — tx: {hex_hash}")
            return "payment_failed"

    except Exception as e:
        logger.error(f"❌ Erreur transfert USDC direct : {e}")
        return "error"

async def is_already_anchored(pattern_hash: str) -> bool:
    return False

async def poll_execution(exec_id: str) -> str:
    return exec_id