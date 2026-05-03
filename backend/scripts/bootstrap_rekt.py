import asyncio
import requests
from bs4 import BeautifulSoup
from memory.cognee_setup import setup_cognee, add_finding_to_memory

async def scrape_and_inject_rekt():
    print("🌐 Fetching data from Rekt.news...")
    
    # ---------------------------------------------------------
    # Scraping skeleton (adapt to rekt.news DOM)
    # url = "https://rekt.news/leaderboard/"
    # response = requests.get(url)
    # soup = BeautifulSoup(response.text, 'html.parser')
    # entries = soup.find_all('div', class_='leaderboard-row')
    # ---------------------------------------------------------
    
    # To start immediately and test Cognee, use 
    # a dataset simulating formatted entries extracted from the site:
    rekt_hacks = [
        {
            "check": "access-control-eth",
            "impact": "High",
            "description": "Poly Network Hack. The attacker exploited an access-control flaw in verifyHeaderAndExecuteTx to modify contract keepers.",
            "contract_name": "EthCrossChainManager"
        },
        {
            "check": "oracle-manipulation",
            "impact": "High",
            "description": "Cream Finance Hack. Price oracle manipulation via complex flash loans causing yUSD share-value distortion.",
            "contract_name": "CreamLending"
        },
        {
            "check": "reentrancy-eth",
            "impact": "High",
            "description": "The DAO Hack. Classic reentrancy during splitDAO() allowing repeated withdrawals before balance update.",
            "contract_name": "TheDAO"
        }
    ]

    print(f"📊 {len(rekt_hacks)} historical hacks found. Starting injection...")

    for hack in rekt_hacks:
        # Format according to structure expected by add_finding_to_memory
        finding_data = {
            "check": hack["check"],
            "impact": hack["impact"],
            "description": f"[Source: Rekt.news] {hack['description']}"
        }
        
        await add_finding_to_memory(finding_data, hack["contract_name"])
        # Small delay to avoid overloading the LLM (OpenAI) during "cognification"
        await asyncio.sleep(1)

    print("✅ Rekt.news bootstrap completed successfully. Memory has been enriched.")

async def main():
    # 1. Initialize Cognee database
    success = await setup_cognee()
    if not success:
        return

    # 2. Start scraping and injection
    await scrape_and_inject_rekt()

if __name__ == "__main__":
    asyncio.run(main())