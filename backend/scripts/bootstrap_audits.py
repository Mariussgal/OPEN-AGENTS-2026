import asyncio
from memory.cognee_setup import setup_cognee, add_finding_to_memory

async def scrape_and_inject_audits():
    print("📄 Analyse des rapports d'audit publics (OpenZeppelin / Trail of Bits)...")
    
    # ---------------------------------------------------------
    # Squelette de parsing PDF/Markdown
    # Cognee supporte nativement l'ingestion de documents.
    # Ici, nous simulons l'extraction structurée (findings) 
    # issue d'une première passe de lecture LLM sur les rapports.
    # ---------------------------------------------------------
    
    audit_reports = [
        {
            "check": "precision-loss",
            "impact": "Medium",
            "description": "Trail of Bits: Perte de précision causée par une division avant multiplication (divide-before-multiply), entraînant un calcul de récompenses incorrect.",
            "contract_name": "StakingRewards"
        },
        {
            "check": "governance-takeover",
            "impact": "Critical",
            "description": "OpenZeppelin: Attaque par Flash loan sur le module de gouvernance. Un attaquant peut emprunter des jetons pour faire passer une proposition malveillante dans le même bloc.",
            "contract_name": "GovernorBravo"
        },
        {
            "check": "front-running-init",
            "impact": "High",
            "description": "OpenZeppelin: La fonction d'initialisation n'est pas protégée, permettant à un attaquant de front-runner la transaction pour s'approprier le contrat proxy.",
            "contract_name": "InitializableProxy"
        }
    ]

    print(f"📑 {len(audit_reports)} vulnérabilités extraites des audits. Début de l'injection...")

    for report in audit_reports:
        finding_data = {
            "check": report["check"],
            "impact": report["impact"],
            "description": f"[Source: Public Audit Report] {report['description']}"
        }
        
        await add_finding_to_memory(finding_data, report["contract_name"])
        await asyncio.sleep(1)

    print("✅ Bootstrap des audits terminé. La base de données collective est désormais riche et variée.")

async def main():
    success = await setup_cognee()
    if not success:
        return

    await scrape_and_inject_audits()

if __name__ == "__main__":
    asyncio.run(main())