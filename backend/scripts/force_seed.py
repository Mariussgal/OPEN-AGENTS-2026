import asyncio
import sys
import os

# Add parent folder (backend/) to import path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from memory.cognee_setup import setup_cognee, add_finding_to_memory

import cognee

load_dotenv()

async def force_seed():
    # 1. Initialize Cognee with the SAME absolute paths as the server
    success = await setup_cognee()
    if not success:
        print("❌ Cognee setup failed.")
        return
    
    # 2. Inject historical hack
    euler_data = {
        "check": "reentrancy-eth",
        "impact": "High",
        "description": "The Euler Finance attack is classic reentrancy on withdraw where balance is updated after external call."
    }
    
    print("🧹 Injection dans le graphe de connaissances...")
    await add_finding_to_memory(euler_data, "EulerVault")
    print("✅ Data injected into graph.")

if __name__ == "__main__":
    asyncio.run(force_seed())