import os
from dotenv import load_dotenv

# 1. Charge le .env dès le départ
load_dotenv()

# 2. Chemin ABSOLU GLOBAL pour persister entre tous les projets de la machine
GLOBAL_MEMORY_DIR = os.path.expanduser("~/.onchor-ai/memory")
COGNEE_SYSTEM_DIR = os.path.join(GLOBAL_MEMORY_DIR, ".cognee_system")
COGNEE_DATA_DIR = os.path.join(GLOBAL_MEMORY_DIR, ".cognee_data")

# 3. Forcer les variables d'environnement AVANT d'importer Cognee
os.makedirs(COGNEE_SYSTEM_DIR, exist_ok=True)
os.makedirs(COGNEE_DATA_DIR, exist_ok=True)
os.environ["COGNEE_SYSTEM_ROOT_DIRECTORY"] = COGNEE_SYSTEM_DIR
os.environ["COGNEE_DATA_ROOT_DIRECTORY"] = COGNEE_DATA_DIR
os.environ["COGNEE_SKIP_CONNECTION_TEST"] = "true"
os.environ["MOCK_EMBEDDING"] = "true"

# 4. IMPORT DE COGNEE ICI
import cognee

# Import de nos nouveaux modules de sécurité et normalisation
from memory.privacy_guard import sanitize_finding_for_memory
from memory.normalizer import normalize_snippet

async def setup_cognee():
    """Initialise Cognee avec la mémoire globale."""
    
    api_key = os.getenv("LLM_API_KEY")
    if not api_key:
        print("❌ ERREUR : LLM_API_KEY est absente du .env")
        return False
    
    # Config interne Cognee
    cognee.config.set_llm_provider("openai")
    cognee.config.set_llm_model("gpt-4o-mini")
    
    print(f"✅ Moteur Cognee initialisé (Mémoire Globale).")
    print(f"   System DB : {COGNEE_SYSTEM_DIR}")
    print(f"   Data Dir  : {COGNEE_DATA_DIR}")
    return True

async def add_finding_to_memory(finding: dict, contract_name: str):
    """Enregistre la vulnérabilité de façon sécurisée dans le graphe."""
    
    # 1. Nettoyage Privacy (Garde-fou)
    safe_finding = sanitize_finding_for_memory(finding)
    
    # 2. Normalisation du code/texte
    safe_desc = normalize_snippet(safe_finding.get('description', ''))
    
    # 3. Formatage en texte pour Cognee
    text_data = (
        f"Vulnerability Report for {contract_name}.\n"
        f"Type: {safe_finding.get('check', 'unknown')}.\n"
        f"Severity: {safe_finding.get('impact', 'unknown')}.\n"
        f"Description: {safe_desc}\n"
    )
    
    try:
        await cognee.add(text_data)
        await cognee.cognify()
        print(f"🧠 Graphe mis à jour en mémoire globale : {safe_finding.get('check')} pour {contract_name}")
    except Exception as e:
        print(f"❌ Erreur lors de l'ajout en mémoire : {e}")

async def load_known_findings(scope):
    """Recherche des vulnérabilités connues dans la mémoire Cognee globale."""
    try:
        results = await cognee.search(f"findings for {scope.name}")
        return results if results else []
    except Exception as e:
        print(f"⚠️ Erreur lors de la recherche mémoire : {e}")
        return []