import time
import click

async def process_x402_payment(amount_usdc: float) -> str:
    """
    Simule ou exécute un paiement x402 sur la blockchain.
    Retourne un hash de transaction fictif pour la démo.
    """
    click.echo(f"⏳ Initialisation du transfert de {amount_usdc} USDC via x402...")
    
    # Simulation du délai réseau/blockchain
    time.sleep(1.5) 
    
    tx_hash = "0x" + "a1b2c3d4" * 8 # Simulation d'un TxHash
    
    click.secho(f"✅ Paiement confirmé ! Tx: {tx_hash}", fg="green")
    return tx_hash