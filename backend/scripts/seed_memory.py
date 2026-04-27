import asyncio
from memory.cognee_setup import setup_cognee, add_finding_to_memory

async def main():
    # 1. Init
    success = await setup_cognee()
    if not success: return

    # 2. On injecte le hack historique
    euler_data = {
        "check": "reentrancy-eth",
        "impact": "High",
        "description": "Exploit historique d'Euler Finance : Réentrance sur withdraw()."
    }

    print("🚀 Construction du graphe de connaissances...")
    await add_finding_to_memory(euler_data, "EulerVault")
    print("✅ Mémoire collective opérationnelle.")

if __name__ == "__main__":
    asyncio.run(main())