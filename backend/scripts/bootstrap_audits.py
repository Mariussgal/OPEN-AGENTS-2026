import asyncio
from memory.cognee_setup import setup_cognee, add_finding_to_memory

async def scrape_and_inject_audits():
    print("📄 Analyse des rapports d'audit publics (OpenZeppelin / Trail of Bits)...")
    
    # ---------------------------------------------------------
    # PDF/Markdown parsing skeleton
    # Cognee natively supports document ingestion.
    # Here we simulate structured extraction (findings)
    # from an initial LLM pass over reports.
    # ---------------------------------------------------------
    
    audit_reports = [
        {
            "check": "precision-loss",
            "impact": "Medium",
            "description": "Trail of Bits: Precision loss caused by divide-before-multiply, producing incorrect reward calculations.",
            "contract_name": "StakingRewards"
        },
        {
            "check": "governance-takeover",
            "impact": "Critical",
            "description": "OpenZeppelin: Flash-loan attack on governance module. An attacker can borrow tokens to pass a malicious proposal in the same block.",
            "contract_name": "GovernorBravo"
        },
        {
            "check": "front-running-init",
            "impact": "High",
            "description": "OpenZeppelin: Initialization function is unprotected, allowing an attacker to front-run and take over the proxy contract.",
            "contract_name": "InitializableProxy"
        }
    ]

    print(f"📑 {len(audit_reports)} vulnerabilities extracted from audits. Starting injection...")

    for report in audit_reports:
        finding_data = {
            "check": report["check"],
            "impact": report["impact"],
            "description": f"[Source: Public Audit Report] {report['description']}"
        }
        
        await add_finding_to_memory(finding_data, report["contract_name"])
        await asyncio.sleep(1)

    print("✅ Audit bootstrap completed. Collective database is now rich and varied.")

async def main():
    success = await setup_cognee()
    if not success:
        return

    await scrape_and_inject_audits()

if __name__ == "__main__":
    asyncio.run(main())