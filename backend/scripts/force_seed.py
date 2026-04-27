import asyncio
import sys
import os

# Ajouter le dossier parent (backend/) au path pour les imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cognee
from dotenv import load_dotenv
from memory.cognee_setup import setup_cognee, add_finding_to_memory

load_dotenv()

async def force_seed():
    # 1. Initialiser Cognee avec les MÊMES chemins absolus que le serveur
    success = await setup_cognee()
    if not success:
        print("❌ Setup Cognee échoué.")
        return
    
    # 2. Injection du hack historique
    euler_data = {
        "check": "reentrancy-eth",
        "impact": "High",
        "description": "L'attaque d'Euler Finance est une réentrance classique sur la fonction withdraw où le solde est mis à jour après l'appel externe."
    }
    
    print("🧹 Injection dans le graphe de connaissances...")
    await add_finding_to_memory(euler_data, "EulerVault")
    print("✅ Donnée injectée dans le graphe.")

if __name__ == "__main__":
    asyncio.run(force_seed())