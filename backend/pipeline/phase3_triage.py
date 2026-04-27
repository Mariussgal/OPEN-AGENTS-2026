import os
import json
import asyncio
from openai import OpenAI
from typing import Dict, Any, List

def get_vercel_client():
    api_key = os.getenv("LLM_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL", "https://ai-gateway.vercel.sh/v1")
    if not api_key:
        return None
    return OpenAI(api_key=api_key, base_url=base_url)

async def map_file_analysis(client, file_info: Dict[str, Any], findings: List[Dict[str, Any]], memory: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Phase MAP : Analyse d'un fichier spécifique."""
    file_path = file_info.get("file", "unknown")
    file_flags = file_info.get("flags", [])
    
    # Filtrer les findings Slither pour ce fichier
    # On compare le nom de base car filename_relative peut varier
    basename = os.path.basename(file_path)
    file_findings = [f for f in findings if os.path.basename(f.get("file", "")) == basename]
    
    if not file_findings and not file_flags:
        return {
            "file": basename,
            "risk_score": 0.5,
            "verdict": "CLEAR",
            "reasoning": "Aucune faille Slither ni flag suspect détecté."
        }

    prompt = f"""
    Tu es un auditeur de Smart Contracts. Analyse le fichier suivant : {basename}
    
    FLAGS DETECTES (Phase 1) : {json.dumps(file_flags)}
    FAILLES SLITHER (Phase 2) : {json.dumps(file_findings)}
    MEMOIRE COLLECTIVE : {json.dumps(memory)}
    
    Evalue la criticité de ce fichier spécifique.
    Réponds UNIQUEMENT avec un objet JSON :
    {{
        "file": "{basename}",
        "risk_score": 0-10,
        "verdict": "SAFE/CAUTION/DANGER",
        "reasoning": "Analyse concise en français."
    }}
    """

    try:
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model="openai/gpt-4o-mini",
            messages=[{"role": "system", "content": "Tu es un expert en sécurité Solidity."}, {"role": "user", "content": prompt}],
            temperature=0
        )
        content = response.choices[0].message.content.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        return json.loads(content)
    except Exception as e:
        print(f"⚠️ Erreur Map sur {basename}: {e}")
        return {"file": basename, "risk_score": 5, "verdict": "ERROR", "reasoning": str(e)}

async def reduce_results(client, map_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Phase REDUCE : Agrégation des analyses de fichiers."""
    if not map_results:
        return {"risk_score": 0, "verdict": "SAFE", "reasoning": "Aucun fichier à analyser."}
    
    prompt = f"""
    En tant qu'auditeur principal, synthétise ces analyses de fichiers individuels pour donner un verdict final sur le contrat.
    
    ANALYSES PAR FICHIER :
    {json.dumps(map_results, indent=2)}
    
    Le score final doit refléter la faille la plus critique trouvée. 
    Si un fichier est en 'DANGER', le contrat global est probablement en 'DANGER'.
    
    Réponds UNIQUEMENT avec un objet JSON :
    {{
        "risk_score": 0-10,
        "verdict": "SAFE/CAUTION/DANGER",
        "reasoning": "Synthèse globale en français."
    }}
    """

    try:
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model="openai/gpt-4o-mini",
            messages=[{"role": "system", "content": "Tu es l'auditeur en chef."}, {"role": "user", "content": prompt}],
            temperature=0
        )
        content = response.choices[0].message.content.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        return json.loads(content)
    except Exception as e:
        # Fallback simple : max des scores
        max_score = max([r.get("risk_score", 0) for r in map_results])
        return {
            "risk_score": max_score,
            "verdict": "REDUCE_ERROR",
            "reasoning": f"Erreur lors de l'agrégation : {e}. Score max utilisé par sécurité."
        }

async def run_triage(slither_data: Dict[str, Any], inventory_data: Dict[str, Any]) -> Dict[str, Any]:
    print("🧐 [Phase 3] Démarrage du Triage Map/Reduce via Vercel Gateway...")
    client = get_vercel_client()
    if not client:
        return {"risk_score": 10, "verdict": "ERROR", "reasoning": "Clé API manquante."}

    findings = slither_data.get("findings", [])
    memory = inventory_data.get("known_findings", [])
    files_info = inventory_data.get("details", [])

    # 1. Phase MAP : Analyse chaque fichier en parallèle
    tasks = [map_file_analysis(client, f, findings, memory) for f in files_info]
    map_results = await asyncio.gather(*tasks)
    
    print(f"✅ [Phase 3] {len(map_results)} fichiers analysés. Passage au Reduce...")

    # 2. Phase REDUCE : Synthèse globale
    final_triage = await reduce_results(client, map_results)
    
    # On ajoute le détail par fichier pour le frontend
    final_triage["file_details"] = map_results
    
    return final_triage