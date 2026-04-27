import os
import json
import anthropic
from typing import Dict, Any

def get_anthropic_client():
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    return anthropic.Anthropic(api_key=api_key)

async def run_triage(slither_data: Dict[str, Any], files: list) -> Dict[str, Any]:
    print("[Phase 3] Démarrage du Triage avec Claude Haiku...")
    
    client = get_anthropic_client()
    
    # Mode Hackathon : Si on n'a pas encore mis la clé API, on simule la réponse
    if not client:
        print("[Phase 3] WARNING: Clé ANTHROPIC_API_KEY manquante dans .env !")
        print("[Phase 3] Utilisation d'un mock (simulation) pour continuer le pipeline.")
        return {
            "risk_score": 8.5,
            "verdict": "INVESTIGATE",
            "reasoning": "Mocked triage because Anthropic API key is missing. Forcing INVESTIGATE mode."
        }

    # Prompt système pour formater le JSON
    prompt = f"""
    You are an expert smart contract auditor.
    Review the following file list and Slither findings.
    Calculate a risk_score from 0 to 10 for the project.
    If the score is strictly less than 3, output the verdict "SAFE". Otherwise output "INVESTIGATE".

    Files: {files}
    Slither Findings: {slither_data.get('findings', [])}

    Format your response as strictly valid JSON without any markdown formatting:
    {{
        "risk_score": 7.5,
        "verdict": "INVESTIGATE",
        "reasoning": "Short explanation here"
    }}
    """

    try:
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=300,
            temperature=0,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        # Extraction et nettoyage du JSON
        result_text = response.content[0].text
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0].strip()
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0].strip()
            
        triage_result = json.loads(result_text)
        print(f"[Phase 3] Triage terminé. Score: {triage_result.get('risk_score')}/10 - {triage_result.get('verdict')}")
        return triage_result

    except Exception as e:
        print(f"[Phase 3] Erreur Anthropic: {e}")
        return {"error": str(e), "risk_score": 10, "verdict": "INVESTIGATE"}