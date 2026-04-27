import re
from typing import List, Dict, Any
from pipeline.phase_resolve import ResolvedContract

# Mots-clés dangereux à détecter (d'après le cahier des charges)
DANGEROUS_FLAGS = ['delegatecall', 'unchecked', 'assembly', 'selfdestruct']

def parse_structural(file_path: str) -> Dict[str, Any]:
    """Parse basique d'un fichier Solidity pour trouver des flags dangereux."""
    flags_found = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            for flag in DANGEROUS_FLAGS:
                # Utilisation d'une regex pour chercher le mot exact
                if re.search(r'\b' + flag + r'\b', content):
                    flags_found.append(flag)
    except Exception as e:
        print(f"Erreur lors de la lecture de {file_path}: {e}")
        
    return {
        "file": file_path,
        "flags": flags_found
    }

async def run_inventory(scope: ResolvedContract) -> dict:
    """Phase 1: Inventaire des fichiers et détection rapide."""
    print("[Phase 1] Inventory en cours...")
    inventory_results = []
    
    # On scanne chaque fichier trouvé en Phase 0
    for file in scope.files:
        parsed = parse_structural(file)
        inventory_results.append(parsed)
        
    # TODO: Plus tard, on intégrera ici load_known_findings() via Cognee
    
    return {
        "files_analyzed": len(scope.files),
        "details": inventory_results,
        "known_findings_loaded": 0  # Mock pour le moment
    }