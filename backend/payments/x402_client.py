import os
import json
import time
import click
from web3 import Web3
from eth_account import Account
from dotenv import load_dotenv

load_dotenv()

# Configuration Sepolia
USDC_SEPOLIA = "0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238"
RPC_URL = f"https://eth-sepolia.g.alchemy.com/v2/{os.getenv('ALCHEMY_API_KEY')}"
RECEIVER_ADDRESS = "0x4DB6Bf931e0AC52E6a35601da70aAB3fF26657C4" # Ton Onchor Wallet

# ABI minimal pour le transfert USDC (ERC20)
ERC20_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "_to", "type": "address"},
            {"name": "_value", "type": "uint256"}
        ],
        "name": "transfer",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    }
]

async def process_x402_payment(amount_usdc: float) -> str:
    """
    Exécute un vrai paiement USDC sur Sepolia via x402-py logic.
    """
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    private_key = os.getenv("OG_PRIVATE_KEY")
    
    if not private_key:
        click.secho("❌ Erreur : OG_PRIVATE_KEY manquante dans le .env", fg="red")
        return ""

    account = Account.from_key(private_key)
    usdc_contract = w3.eth.contract(address=USDC_SEPOLIA, abi=ERC20_ABI)
    
    # 1 USDC = 1,000,000 units (6 decimals)
    amount_units = int(amount_usdc * 1_000_000)
    
    click.echo(f"⏳ Préparation du transfert de {amount_usdc} USDC...")
    
    # Vérification du solde
    balance = usdc_contract.functions.balanceOf(account.address).call()
    if balance < amount_units:
        click.secho(f"❌ Solde insuffisant : {balance/1_000_000} USDC sur {account.address}", fg="red")
        return ""

    # Construction de la transaction
    nonce = w3.eth.get_transaction_count(account.address)
    tx = usdc_contract.functions.transfer(RECEIVER_ADDRESS, amount_units).build_transaction({
        'chainId': 11155111, # Sepolia
        'gas': 150000,
        'gasPrice': w3.eth.gas_price,
        'nonce': nonce,
    })

    # Signature et envoi
    signed_tx = w3.eth.account.sign_transaction(tx, private_key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    
    click.secho(f"🚀 Transaction envoyée ! Hash: {tx_hash.hex()}", fg="cyan")
    click.echo("⏳ Attente de la confirmation (Sepolia)...")
    
    # Attente de la confirmation
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    
    if receipt.status == 1:
        click.secho(f"✅ Paiement x402 validé onchain !", fg="green", bold=True)
        return tx_hash.hex()
    else:
        click.secho("❌ Échec de la transaction onchain.", fg="red")
        return ""