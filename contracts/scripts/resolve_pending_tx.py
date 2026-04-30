# backend/scripts/resolve_pending_tx.py
"""
Résout les executionIds KeeperHub en attente dans l'historique des audits.
Usage : python scripts/resolve_pending_tx.py
"""

import asyncio
import json
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

AUDITS_FILE = Path(".onchor/audits.json")

async def resolve_one(execution_id: str) -> str | None:
    import httpx
    api_key = os.getenv("KEEPERHUB_API_KEY")
    if not api_key:
        return None

    # Tester plusieurs endpoints possibles
    endpoints = [
        f"https://app.keeperhub.com/api/execute/{execution_id}",
        f"https://app.keeperhub.com/api/executions/{execution_id}",
        f"https://app.keeperhub.com/api/v1/execute/{execution_id}",
    ]

    for url in endpoints:
        try:
            async with httpx.AsyncClient(timeout=10.0) as http:
                resp = await http.get(
                    url,
                    headers={"Authorization": f"Bearer {api_key}"}
                )
            print(f"  {url} → {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                print(f"  Response: {json.dumps(data, indent=2)[:300]}")
                # Chercher le tx hash dans la réponse
                tx = (
                    data.get("transactionHash")
                    or data.get("txHash")
                    or data.get("tx_hash")
                )
                if tx and tx not in ("pending", ""):
                    return tx
        except Exception as e:
            print(f"  {url} → error: {e}")

    return None


async def main():
    if not AUDITS_FILE.exists():
        print("Aucun historique d'audits trouvé.")
        return

    audits = json.loads(AUDITS_FILE.read_text())
    updated = False

    for audit in audits:
        findings = (
            audit.get("report", {}).get("findings", [])
            or audit.get("findings", [])
        )
        for f in findings:
            exe_id = f.get("keeperhub_execution_id")
            if exe_id and not f.get("onchain_proof"):
                print(f"\nRésolution de {exe_id} pour {f.get('title', '?')}...")
                tx = await resolve_one(exe_id)
                if tx:
                    print(f"  ✓ tx trouvée : {tx}")
                    f["onchain_proof"] = tx
                    updated = True
                else:
                    print(f"  ✗ toujours pending")

    if updated:
        AUDITS_FILE.write_text(json.dumps(audits, indent=2))
        print("\n✓ Historique mis à jour.")
    else:
        print("\nAucun tx résolu.")


if __name__ == "__main__":
    asyncio.run(main())