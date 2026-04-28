import click
import httpx
import json
import os
import asyncio

API_URL = "http://localhost:8000"

def load_config():
    """Charge la configuration et le solde de l'utilisateur."""
    if os.path.exists(".onchor/config.json"):
        with open(".onchor/config.json", "r") as f:
            config = json.load(f)
            # S'assure que le champ crédit existe pour les anciens fichiers
            if "credit_usdc" not in config:
                config["credit_usdc"] = 0.0
            return config
    return {"version": "0.1.0", "mode": "local", "credit_usdc": 0.0}

def save_config(config):
    """Sauvegarde la configuration et le nouveau solde."""
    os.makedirs(".onchor", exist_ok=True)
    with open(".onchor/config.json", "w") as f:
        json.dump(config, f, indent=2)

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
        save_config({"version": "0.1.0", "mode": "local", "credit_usdc": 0.0})
        click.secho("🚀 Projet initialisé. Dossier .onchor créé.", fg="green")
    else:
        click.echo("Le projet est déjà initialisé.")

@cli.command()
@click.argument('path')
@click.option('--local', is_flag=True, help='Mode local, sans paiement.')
@click.option('--dev',   is_flag=True, help='Mode dev, bypass total.')
def audit(path, local, dev):
    """Lance un audit sur un fichier, un répertoire ou une adresse 0x."""
    click.secho(f"\n[Onchor.ai] Audit : {path}", fg="blue", bold=True)
    
    # On charge le profil utilisateur (pour avoir son solde actuel)
    user_config = load_config()

    try:
        if local or dev:
            # ── Free tier ──────────────────────────────────────────────────
            click.secho(f"ℹ️  Mode {'DEV' if dev else 'LOCAL'} — gratuit", fg="cyan")
            with httpx.Client(timeout=120.0) as client:
                resp = client.post(f"{API_URL}/audit/local", params={"path": path})
                resp.raise_for_status()
                data = resp.json()
        else:
            # ── Paid tier ────────────────────────────────────────
            from payments.x402_client import run_paid_audit
            # Affichage du solde disponible avant l'audit
            if user_config["credit_usdc"] > 0:
                click.secho(f"💳 Solde disponible : {user_config['credit_usdc']:.2f} USDC", fg="cyan")
                
            data = asyncio.run(run_paid_audit(API_URL, path))

        click.secho("\n✅ Audit terminé.", fg="green", bold=True)
        click.echo(json.dumps(data, indent=2, ensure_ascii=False))

        # --- Étape 8 - Opt-in Contribution (100% Réel et Économiquement viable) ---
        investigation = data.get("investigation", {})
        findings = investigation.get("findings", [])
        if not findings:
            findings = data.get("slither", {}).get("findings", [])

        if findings and not local and not dev:
            click.secho(f"\n🌟 {len(findings)} vulnérabilité(s) identifiée(s) lors de cet audit.", fg="yellow")
            opt_in = click.confirm(
                "Voulez-vous partager ces patterns de façon ANONYME à la mémoire collective ?\n"
                "🎁 Récompense : Vous gagnerez 0.05 USDC par pattern validé."
            )
            
            if opt_in:
                # --- PROTECTION ECONOMIQUE ---
                # On ne récompense que les 3 vulnérabilités les plus critiques maximum
                MAX_REWARDABLE = 3
                payable_count = min(len(findings), MAX_REWARDABLE)
                
                # Calcul réaliste et plafonné : 0.05 USDC par vraie vulnérabilité (max 0.15 USDC)
                reward = payable_count * 0.05
                
                # --- PAIEMENT RÉEL VIA X402 ---
                click.secho(f"  ⟳  Envoi de la récompense ({reward:.2f} USDC) sur Base Sepolia...", fg="cyan")
                try:
                    contributor_address = os.getenv("RECEIVER_ADDRESS")
                    with httpx.Client(timeout=30.0) as client:
                        reward_resp = client.post(
                            f"{API_URL}/audit/reward",
                            params={"contributor_address": contributor_address, "amount": reward}
                        )
                        reward_resp.raise_for_status()
                        reward_data = reward_resp.json()
                        tx_hash = reward_data.get("tx")
                    
                    # Mise à jour REELLE du profil local
                    user_config["credit_usdc"] += reward
                    save_config(user_config)
                    
                    click.secho(f"✅ Succès ! {payable_count} pattern(s) payé(s) on-chain.", fg="green")
                    click.secho(f"🔗 TX: {tx_hash}", fg="dim")
                    click.secho(f"🏦 Nouveau solde : {user_config['credit_usdc']:.2f} USDC", fg="cyan", bold=True)
                except Exception as e:
                    click.secho(f"⚠️ Erreur lors du paiement : {e}", fg="red")
            else:
                click.secho("🔒 Contribution refusée. Vos données restent strictement locales.", fg="dim")

    except click.Abort:
        click.echo("\nAudit annulé.")
    except Exception as e:
        click.secho(f"\n❌ Erreur : {e}", fg="red")

if __name__ == '__main__':
    cli()