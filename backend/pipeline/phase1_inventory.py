import asyncio
import cognee
import hashlib
import os
from typing import List, Any, Dict
from .phase_resolve import ResolvedContract
from memory.cognee_setup import setup_cognee

import re

def analyze_solidity_file(file_path: str) -> Dict[str, Any]:
    """Analyse structurelle rapide sans LLM."""
    if not os.path.exists(file_path):
        return {"functions": [], "modifiers": [], "events": [], "flags": []}
    
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Extraction simple par regex
    functions = re.findall(r"function\s+([a-zA-Z0-9_]+)", content)
    modifiers = re.findall(r"modifier\s+([a-zA-Z0-9_]+)", content)
    events = re.findall(r"event\s+([a-zA-Z0-9_]+)", content)
    
    # Flags de sécurité rapides
    flags = []
    if "delegatecall" in content: flags.append("delegatecall")
    if "selfdestruct" in content: flags.append("selfdestruct")
    if "assembly {" in content: flags.append("assembly")
    if "unchecked {" in content: flags.append("unchecked")
    
    return {
        "functions_count": len(functions),
        "modifiers_count": len(modifiers),
        "events_count": len(events),
        "flags": flags
    }

def generate_file_hash(file_path: str) -> str:
    """Génère un hash SHA256 pour identifier le contrat."""
    try:
        if not os.path.exists(file_path): return ""
        with open(file_path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except Exception:
        return "hash_error"

async def load_known_findings(scope: ResolvedContract) -> List[Any]:
    """PHASE 1 : Recherche sémantique via la nouvelle API recall de Cognee."""
    known_findings = []
    
    # On construit une query basée sur ce qu'on sait du contrat
    # Si on a un nom de contrat ou une adresse, on l'utilise
    contract_name = os.path.basename(scope.files[0]).replace(".sol", "") if scope.files else "Smart Contract"
    search_query = f"Vulnerabilities and historical exploits for {contract_name}"
    
    if scope.address:
        search_query += f" at {scope.address}"
        
    try:
        print(f"🧠 [Phase 1] Interrogation de la mémoire vive : '{search_query}'...")
        
        # recall() parcourt le graphe de connaissances extrait lors du seed
        search_results = await cognee.recall(search_query)
        
        if search_results:
            print(f"💡 [Phase 1] {len(search_results)} souvenir(s) récupéré(s) du Knowledge Graph.")
            for res in search_results:
                content = ""
                
                # 1. On cherche 'search_result' qui contient la liste des faits trouvés
                if hasattr(res, "search_result"):
                    val = getattr(res, "search_result")
                    content = "\n".join(val) if isinstance(val, list) else str(val)
                elif isinstance(res, dict) and "search_result" in res:
                    val = res["search_result"]
                    content = "\n".join(val) if isinstance(val, list) else str(val)
                elif hasattr(res, "text"):
                    content = res.text
                else:
                    # Fallback ultime : on essaie de voir si c'est un string qui contient un dict
                    res_str = str(res)
                    if "'search_result': [" in res_str:
                        # Extraction rustique mais efficace pour le hackathon
                        try:
                            parts = res_str.split("'search_result': [")[1].split("]")[0]
                            content = parts.replace("\\n", "\n").replace("'", "").strip()
                        except:
                            content = res_str
                    else:
                        content = res_str

                # Nettoyage final pour enlever les résidus de formatage
                content = content.replace("['", "").replace("']", "").replace("', '", "\n")
                
                if content and content not in [f["description"] for f in known_findings]:
                    known_findings.append({
                        "contract": contract_name,
                        "type": "Historical Memory",
                        "description": content.strip()
                    })
        else:
            print("p [Phase 1] Aucun souvenir spécifique trouvé dans le graphe.")
                
    except Exception as e:
        print(f"⚠️ [Phase 1] Cognee Recall Error : {e}")
        
    return known_findings

async def run_inventory(scope: ResolvedContract):
    """Exécute l'inventaire complet."""
    print(f"🔍 [Phase 1] Analyse de {len(scope.files)} fichier(s)...")
    
    # 0. Initialiser Cognee avec les bons chemins
    await setup_cognee()
    
    # 1. Recherche de souvenirs
    known_findings = await load_known_findings(scope)
    
    # 2. Construction des détails
    inventory_details = []
    for file_path in scope.files:
        stats = analyze_solidity_file(file_path)
        inventory_details.append({
            "file": file_path,
            "flags": stats["flags"], 
            "stats": stats,
            "pattern_hash": generate_file_hash(file_path),
            "is_duplicate": False
        })
        
    return {
        "files_analyzed": len(scope.files),
        "details": inventory_details,
        "duplicates_detected": 0,
        "known_findings": known_findings,
        "known_findings_count": len(known_findings)
    }