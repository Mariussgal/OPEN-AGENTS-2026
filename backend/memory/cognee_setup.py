import os
import cognee
from dotenv import load_dotenv

# Charge le .env dès le départ
load_dotenv()

# Chemin ABSOLU pour que seed + serveur pointent sur la même DB
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COGNEE_SYSTEM_DIR = os.path.join(BACKEND_DIR, ".cognee_system")
COGNEE_DATA_DIR = os.path.join(BACKEND_DIR, ".cognee_data")

async def setup_cognee():
    """Initialise Cognee avec des chemins absolus pour éviter le 'unable to open database file'."""
    
    api_key = os.getenv("LLM_API_KEY")
    if not api_key:
        print("❌ ERREUR : LLM_API_KEY est absente du .env")
        return False

    # 1. Forcer les chemins absolus AVANT toute opération Cognee
    os.makedirs(COGNEE_SYSTEM_DIR, exist_ok=True)
    os.makedirs(COGNEE_DATA_DIR, exist_ok=True)
    os.environ["COGNEE_SYSTEM_ROOT_DIRECTORY"] = COGNEE_SYSTEM_DIR
    os.environ["COGNEE_DATA_ROOT_DIRECTORY"] = COGNEE_DATA_DIR
    
    # 2. Désactive le test de connexion qui cause le timeout
    os.environ["COGNEE_SKIP_CONNECTION_TEST"] = "true"
    os.environ["MOCK_EMBEDDING"] = "true"
    
    # 3. Config interne Cognee
    cognee.config.set_llm_provider("openai")
    cognee.config.set_llm_model("gpt-4o-mini")
    
    print(f"✅ Moteur Cognee initialisé.")
    print(f"   System DB : {COGNEE_SYSTEM_DIR}")
    print(f"   Data Dir  : {COGNEE_DATA_DIR}")
    return True

async def add_finding_to_memory(finding: dict, contract_name: str):
    """Enregistre la vulnérabilité dans le graphe.
    
    IMPORTANT: Cognee 1.0.3 n'accepte que du texte (str) ou des fichiers.
    Les dictionnaires Python causent une IngestionError.
    On convertit donc en texte structuré.
    """
    # Cognee veut du TEXTE, pas un dict
    text_data = (
        f"Vulnerability Report for {contract_name}.\n"
        f"Type: {finding['check']}.\n"
        f"Severity: {finding['impact']}.\n"
        f"Description: {finding['description']}\n"
    )
    
    try:
        await cognee.add(text_data)
        await cognee.cognify()
        print(f"🧠 Graphe mis à jour : {finding['check']} pour {contract_name}")
    except Exception as e:
        print(f"❌ Erreur lors de l'ajout en mémoire : {e}")
async def load_known_findings(scope):
    """Recherche des vulnérabilités connues dans la mémoire Cognee."""
    try:
        # Recherche par similarité ou mot-clé sur le nom du contrat
        results = await cognee.search(f"findings for {scope.name}")
        return results if results else []
    except Exception as e:
        print(f"⚠️ Erreur lors de la recherche mémoire : {e}")
        return []
