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

async def map_file_analysis(
    client,
    file_info: Dict[str, Any],
    findings: List[Dict[str, Any]],
    memory: List[Dict[str, Any]],
    *,
    slither_success: bool = True,
) -> Dict[str, Any]:
    """MAP phase: analyze a specific file."""
    file_path = file_info.get("file", "unknown")
    file_flags = file_info.get("flags", [])
    
    # Filter Slither findings for this file.
    # Compare basenames because filename_relative can vary.
    basename = os.path.basename(file_path)
    file_findings = [f for f in findings if os.path.basename(f.get("file", "")) == basename]

    # Do not treat empty list as clean: Slither may have failed before producing output.
    if slither_success is False:
        return {
            "file": basename,
            "risk_score": 6.0,
            "verdict": "CAUTION",
            "reasoning": (
                "Slither static analysis unavailable (solc compile, dependencies, or execution issue). "
                "No Slither findings does not mean safe code; fix toolchain/pragma before concluding."
            ),
        }
    
    if not file_findings and not file_flags:
        return {
            "file": basename,
            "risk_score": 0.5,
            "verdict": "CLEAR",
            "reasoning": "No Slither findings or suspicious flags detected."
        }

    prompt = f"""
    You are a smart contract auditor. Analyze this file: {basename}
    
    DETECTED FLAGS (Phase 1): {json.dumps(file_flags)}
    SLITHER FINDINGS (Phase 2): {json.dumps(file_findings)}
    COLLECTIVE MEMORY: {json.dumps(memory)}
    
    Evaluate the risk level of this specific file.
    Reply ONLY with a JSON object:
    {{
        "file": "{basename}",
        "risk_score": 0-10,
        "verdict": "SAFE/CAUTION/DANGER",
        "reasoning": "Concise analysis in English."
    }}
    """

    try:
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model="openai/gpt-4o-mini",
            messages=[{"role": "system", "content": "You are a Solidity security expert."}, {"role": "user", "content": prompt}],
            temperature=0
        )
        content = response.choices[0].message.content.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        return json.loads(content)
    except Exception as e:
        print(f"⚠️ Map error on {basename}: {e}")
        return {"file": basename, "risk_score": 5, "verdict": "ERROR", "reasoning": str(e)}

async def reduce_results(client, map_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """REDUCE phase: aggregate per-file analyses."""
    if not map_results:
        return {"risk_score": 0, "verdict": "SAFE", "reasoning": "No files to analyze."}
    
    prompt = f"""
    As lead auditor, synthesize these per-file analyses into a final contract verdict.
    
    FILE ANALYSES:
    {json.dumps(map_results, indent=2)}
    
    The final score must reflect the most critical issue found.
    If one file is 'DANGER', the overall contract is likely 'DANGER'.
    
    Reply ONLY with a JSON object:
    {{
        "risk_score": 0-10,
        "verdict": "SAFE/CAUTION/DANGER",
        "reasoning": "Global synthesis in English."
    }}
    """

    try:
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model="openai/gpt-4o-mini",
            messages=[{"role": "system", "content": "You are the lead auditor."}, {"role": "user", "content": prompt}],
            temperature=0
        )
        content = response.choices[0].message.content.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        return json.loads(content)
    except Exception as e:
        # Simple fallback: max score.
        max_score = max([r.get("risk_score", 0) for r in map_results])
        return {
            "risk_score": max_score,
            "verdict": "REDUCE_ERROR",
            "reasoning": f"Aggregation error: {e}. Using max score as a safety fallback."
        }

async def run_triage(slither_data: Dict[str, Any], inventory_data: Dict[str, Any]) -> Dict[str, Any]:
    print("🧐 [Phase 3] Starting Map/Reduce triage via Vercel Gateway...")
    client = get_vercel_client()
    if not client:
        return {"risk_score": 10, "verdict": "ERROR", "reasoning": "Missing API key."}

    findings = slither_data.get("findings", [])
    memory = inventory_data.get("known_findings", [])
    files_info = inventory_data.get("details", [])
    slither_ok = slither_data.get("success", True)

    # 1) MAP phase: analyze each file in parallel.
    tasks = [
        map_file_analysis(client, f, findings, memory, slither_success=slither_ok)
        for f in files_info
    ]
    map_results = await asyncio.gather(*tasks)
    
    print(f"✅ [Phase 3] {len(map_results)} files analyzed. Moving to Reduce...")

    # 2) REDUCE phase: global synthesis.
    final_triage = await reduce_results(client, map_results)

    # Guardrail: if Slither explicitly failed, do not conclude SAFE by itself.
    if slither_data.get("success") is False:
        if (final_triage.get("verdict") or "").upper() == "SAFE":
            final_triage["verdict"] = "CAUTION"
        final_triage["risk_score"] = max(float(final_triage.get("risk_score") or 0), 6.0)
        extra = (
            "Slither static analysis did not run; caution required until compilation succeeds."
        )
        prev = (final_triage.get("reasoning") or "").strip()
        final_triage["reasoning"] = f"{prev} {extra}".strip() if prev else extra
    
    # Add per-file details for frontend display.
    final_triage["file_details"] = map_results
    final_triage["slither_success"] = slither_ok
    
    return final_triage