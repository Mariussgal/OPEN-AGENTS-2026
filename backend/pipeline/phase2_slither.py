import subprocess
import json
import os
from typing import Dict, Any

async def run_slither(path: str) -> Dict[str, Any]:
    """
    Lance Slither sur le dossier/fichier et retourne les findings parsés.
    """
    print(f"[Phase 2] Lancement de Slither sur {path}...")
    
    # On utilise un fichier temporaire pour stocker le rapport JSON de Slither
    json_report_path = "slither_report.json"
    
    try:
        # Commande : slither <chemin> --json <fichier_sortie>
        # On utilise capture_output pour ne pas polluer le terminal du serveur
        process = subprocess.run(
            ["slither", path, "--json", json_report_path],
            capture_output=True,
            text=True
        )
        
        # Slither renvoie souvent un code d'erreur s'il trouve des failles,
        # donc on ne vérifie pas process.returncode directement, on lit juste le JSON.
        
        if os.path.exists(json_report_path):
            with open(json_report_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Nettoyage du fichier temporaire
            os.remove(json_report_path)
            
            # Extraction des findings (détecteurs de failles)
            findings = data.get("results", {}).get("detectors", [])
            
            # Formatage des résultats pour notre pipeline
            formatted_findings = []
            for f in findings:
                # Sécurisation de l'extraction du fichier
                elements = f.get("elements", [])
                if elements:
                    source_mapping = elements[0].get("source_mapping", {})
                    filename = source_mapping.get("filename_relative", "unknown")
                else:
                    filename = "unknown"
                
                formatted_findings.append({
                    "check": f.get("check"),
                    "impact": f.get("impact"),
                    "description": f.get("description"),
                    "file": filename
                })
                
            print(f"[Phase 2] Slither a terminé. {len(formatted_findings)} failles trouvées.")
            return {
                "success": True,
                "findings_count": len(formatted_findings),
                "findings": formatted_findings
            }
        else:
            return {"success": False, "error": "Le fichier JSON de Slither n'a pas été créé.", "logs": process.stderr}
            
    except Exception as e:
        print(f"[Phase 2] Erreur d'exécution de Slither: {e}")
        return {"success": False, "error": str(e)}