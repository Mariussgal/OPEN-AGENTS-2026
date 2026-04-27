import click
import httpx
import json
import os
import asyncio

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
@click.argument('path')
@click.option('--local', is_flag=True, help='Mode local, sans paiement.')
@click.option('--dev',   is_flag=True, help='Mode dev, bypass total.')
def audit(path, local, dev):
    """Lance un audit sur un fichier, un répertoire ou une adresse 0x."""
    click.secho(f"\n[Onchor.ai] Audit : {path}", fg="blue", bold=True)

    try:
        if local or dev:
            # ── Free tier ──────────────────────────────────────────────────
            click.secho(f"ℹ️  Mode {'DEV' if dev else 'LOCAL'} — gratuit", fg="cyan")
            with httpx.Client(timeout=120.0) as client:
                resp = client.post(f"{API_URL}/audit/local", params={"path": path})
                resp.raise_for_status()
                data = resp.json()
        else:
            # ── Paid tier — Option B ────────────────────────────────────────
            from payments.x402_client import run_paid_audit
            data = asyncio.run(run_paid_audit(API_URL, path))

        click.secho("\n✅ Audit terminé.", fg="green", bold=True)
        click.echo(json.dumps(data, indent=2, ensure_ascii=False))

    except click.Abort:
        click.echo("\nAudit annulé.")
    except Exception as e:
        click.secho(f"\n❌ Erreur : {e}", fg="red")

if __name__ == '__main__':
    cli()