import click
import httpx
import json
import os
from payments.x402_pricing import calculate_price

API_URL = "http://localhost:8000"

@click.group()
def cli():
    """
    ONCHOR.AI 🛡️
    Solidity Security Copilot with Persistent Collective Memory.
    """
    pass

@cli.command()
def init():
    """Initialise le dossier de configuration Onchor.ai."""
    if not os.path.exists(".onchor"):
        os.makedirs(".onchor")
        with open(".onchor/config.json", "w") as f:
            json.dump({"version": "0.1.0", "mode": "local"}, f)
        click.secho("🚀 Projet initialisé. Dossier .onchor créé.", fg="green")
    else:
        click.echo("Le projet est déjà initialisé.")

@cli.command()
@click.argument('path')  # <--- CORRECTION : On enlève le type=click.Path(exists=True)
@click.option('--local', is_flag=True, help='Bypass x402.')
@click.option('--dev', is_flag=True, help='Mode développement.')
def audit(path, local, dev):
    """Lance un audit sur un fichier, un répertoire ou une adresse 0x."""
    click.secho(f"\n[Onchor.ai] Préparation de l'audit : {path}", fg="blue", bold=True)

    # 1. Calcul du prix (x402) - CORRECTION pour gérer les adresses
    nb_files = 0
    if path.startswith("0x"):
        nb_files = 1  # Estimation pour une adresse onchain
    elif os.path.isdir(path):
        for root, _, filenames in os.walk(path):
            for f in filenames:
                if f.endswith(".sol"): nb_files += 1
    elif os.path.isfile(path) and path.endswith(".sol"):
        nb_files = 1
    
    if nb_files == 0 and not path.startswith("0x"):
        click.secho(f"❌ Erreur : Le chemin '{path}' n'existe pas ou ne contient pas de .sol", fg="red")
        return

    price = calculate_price(nb_files)
    
    # 2. Affichage et confirmation (UX x402)
    payment_hash = None
    if not local and not dev:
        click.secho(f"💰 Prix calculé : {price} USDC (pour {nb_files} fichiers)", fg="yellow")
        if click.confirm("Voulez-vous procéder au paiement x402 ?"):
            from payments.x402_client import process_x402_payment
            import asyncio
            payment_hash = asyncio.run(process_x402_payment(price))
            if not payment_hash:
                click.secho("❌ Annulation : Le paiement a échoué.", fg="red")
                return
        else:
            click.echo("Audit annulé.")
            return
    else:
        click.secho(f"ℹ️ Mode {'DEV' if dev else 'LOCAL'} : Audit gratuit.", fg="cyan")

    # 3. Appel au serveur
    click.echo("Transmission au moteur d'analyse...")
    try:
        # Note: on ajoute le mode et le hash de paiement dans les params
        params = {
            "path": path, 
            "mode": "local" if local or dev else "onchain",
            "payment_hash": payment_hash
        }
        with httpx.Client(timeout=120.0) as client:
            response = client.post(f"{API_URL}/audit/local", params=params)
            response.raise_for_status()
            data = response.json()
            click.secho("\n✅ Audit terminé avec succès.", fg="green", bold=True)
            click.echo(json.dumps(data, indent=2, ensure_ascii=False))
    except Exception as e:
        click.secho(f"\n❌ Erreur lors de l'audit : {e}", fg="red")

if __name__ == '__main__':
    cli()