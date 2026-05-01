import subprocess
import json
import os
import re
from typing import Dict, Any

def _setup_solc_version(path: str) -> None:
    """Find required Solidity version and install it via solc-select."""
    try:
        version = None
        
        # Find one .sol file
        sol_file = None
        if os.path.isfile(path) and path.endswith('.sol'):
            sol_file = path
        elif os.path.isdir(path):
            for root, _, files in os.walk(path):
                for file in files:
                    if file.endswith('.sol'):
                        sol_file = os.path.join(root, file)
                        break
                if sol_file:
                    break
                    
        if sol_file:
            with open(sol_file, 'r', encoding='utf-8') as f:
                content = f.read()
                # Match `pragma solidity =0.6.6;` or `pragma solidity ^0.8.0;`
                match = re.search(r'pragma\s+solidity\s+[^0-9]*([0-9]+\.[0-9]+\.[0-9]+)', content)
                if match:
                    version = match.group(1)
        
        if version:
            print(f"  [Phase 2] Pragma solidity version detected: {version}. Running solc-select...")
            subprocess.run(["solc-select", "install", version], capture_output=True)
            subprocess.run(["solc-select", "use", version], capture_output=True)
            print(f"  [Phase 2] Switched to solc version {version}.")
    except Exception as e:
        print(f"  [Phase 2] Unable to configure solc-select: {e}")

async def run_slither(path: str) -> Dict[str, Any]:
    """
    Run Slither on folder/file and return parsed findings.
    """
    print(f"[Phase 2] Running Slither on {path}...")
    _setup_solc_version(path)
    
    # Use a temporary file for Slither JSON report
    json_report_path = "slither_report.json"
    
    try:
        # Command: slither <path> --json <output_file>
        # Use capture_output to keep server terminal clean
        process = subprocess.run(
            ["slither", path, "--json", json_report_path],
            capture_output=True,
            text=True
        )
        
        # Slither often returns non-zero when it finds issues,
        # so we parse JSON output instead of relying on returncode.
        
        if os.path.exists(json_report_path):
            with open(json_report_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Cleanup temp file
            os.remove(json_report_path)
            
            # Extract findings (detectors)
            findings = data.get("results", {}).get("detectors", [])
            
            # Format results for pipeline
            formatted_findings = []
            for f in findings:
                # Safe file extraction
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
                
            print(f"[Phase 2] Slither completed. {len(formatted_findings)} findings detected.")
            return {
                "success": True,
                "findings_count": len(formatted_findings),
                "findings": formatted_findings
            }
        else:
            return {"success": False, "error": "Slither JSON report file was not created.", "logs": process.stderr}
            
    except Exception as e:
        print(f"[Phase 2] Slither execution error: {e}")
        return {"success": False, "error": str(e)}