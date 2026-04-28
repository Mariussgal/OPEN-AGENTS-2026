import asyncio
import requests
from bs4 import BeautifulSoup
from memory.cognee_setup import setup_cognee, add_finding_to_memory

async def scrape_and_inject_rekt():
    print("🌐 Récupération des données depuis Rekt.news...")
    
    # ---------------------------------------------------------
    # Squelette de scraping (à adapter selon le DOM de rekt.news)
    # url = "https://rekt.news/leaderboard/"
    # response = requests.get(url)
    # soup = BeautifulSoup(response.text, 'html.parser')
    # entries = soup.find_all('div', class_='leaderboard-row')
    # ---------------------------------------------------------
    
    # Pour démarrer immédiatement et tester Cognee, on utilise 
    # un jeu de données simulant les entrées formatées extraites du site :
    rekt_hacks = [
        {
            "check": "access-control-eth",
            "impact": "High",
            "description": "Poly Network Hack. L'attaquant a exploité une faille de contrôle d'accès dans la fonction verifyHeaderAndExecuteTx pour modifier les gardiens (keepers) du contrat.",
            "contract_name": "EthCrossChainManager"
        },
        {
            "check": "oracle-manipulation",
            "impact": "High",
            "description": "Cream Finance Hack. Manipulation de l'oracle de prix via des flash loans complexes causant un décalage de la valeur des actions yUSD.",
            "contract_name": "CreamLending"
        },
        {
            "check": "reentrancy-eth",
            "impact": "High",
            "description": "The DAO Hack. Réentrance classique lors de l'appel de splitDAO() permettant de retirer les fonds en boucle avant la mise à jour du solde.",
            "contract_name": "TheDAO"
        }
    ]

    print(f"📊 {len(rekt_hacks)} hacks historiques trouvés. Début de l'injection...")

    for hack in rekt_hacks:
        # On formate selon la structure attendue par ton add_finding_to_memory
        finding_data = {
            "check": hack["check"],
            "impact": hack["impact"],
            "description": f"[Source: Rekt.news] {hack['description']}"
        }
        
        await add_finding_to_memory(finding_data, hack["contract_name"])
        # Petit délai pour éviter de surcharger le LLM (OpenAI) lors de la "cognification"
        await asyncio.sleep(1)

    print("✅ Bootstrap Rekt.news terminé avec succès. La mémoire s'est enrichie.")

async def main():
    # 1. Initialisation de la base Cognee
    success = await setup_cognee()
    if not success:
        return

    # 2. Lancement du scraping et de l'injection
    await scrape_and_inject_rekt()

if __name__ == "__main__":
    asyncio.run(main())