# pipeline/phase1_inventory.py
import hashlib
import os
import re
from typing import List, Any, Dict

from .phase_resolve import ResolvedContract

# Initialize COGNEE_* on disk before first ``import cognee`` (avoid SQLite OperationalError).
from memory.cognee_setup import setup_cognee
import cognee


def analyze_solidity_file(file_path: str) -> Dict[str, Any]:
    """Fast structural analysis without LLM."""
    if not os.path.exists(file_path):
        return {"functions": [], "modifiers": [], "events": [], "flags": []}

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    functions = re.findall(r"function\s+([a-zA-Z0-9_]+)", content)
    modifiers = re.findall(r"modifier\s+([a-zA-Z0-9_]+)", content)
    events    = re.findall(r"event\s+([a-zA-Z0-9_]+)", content)

    flags = []
    if "delegatecall" in content: flags.append("delegatecall")
    if "selfdestruct" in content: flags.append("selfdestruct")
    if "assembly {"  in content: flags.append("assembly")
    if "unchecked {" in content: flags.append("unchecked")

    return {
        "functions_count": len(functions),
        "modifiers_count": len(modifiers),
        "events_count":    len(events),
        "flags":           flags,
    }


def generate_file_hash(file_path: str) -> str:
    """SHA256 hash of file contents."""
    try:
        if not os.path.exists(file_path):
            return ""
        with open(file_path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except Exception:
        return "hash_error"


def generate_pattern_hash(check: str, file_hash: str) -> str:
    """
    Deterministic hash for a finding type on a given file.
    Same check + same file content = same hash.
    Used for cross-audit deduplication.
    """
    raw = f"{check}:{file_hash}"
    return hashlib.sha256(raw.encode()).hexdigest()


def is_duplicate(pattern_hash: str, known_hashes: set) -> bool:
    """
    Check whether this pattern was already reported on this contract.
    Avoid reporting the same vulnerability twice.
    """
    return pattern_hash in known_hashes


async def load_known_findings(scope: ResolvedContract) -> tuple[List[Any], set]:
    """
    Load findings already documented in Cognee.
    Retourne (known_findings, known_hashes).
    known_hashes = set of previously seen pattern_hash values -> used for is_duplicate().
    """
    known_findings = []
    known_hashes   = set()

    contract_name = (
        os.path.basename(scope.files[0]).replace(".sol", "")
        if scope.files else "Smart Contract"
    )
    search_query = f"Vulnerabilities and historical exploits for {contract_name}"
    if scope.address:
        search_query += f" at {scope.address}"

    try:
        print(f"🧠 [Phase 1] Querying live memory: '{search_query}'...")
        search_results = await cognee.recall(search_query)

        if search_results:
            print(f"💡 [Phase 1] {len(search_results)} memory hit(s) retrieved from Knowledge Graph.")
            for res in search_results:
                content = ""

                if hasattr(res, "search_result"):
                    val     = getattr(res, "search_result")
                    content = "\n".join(val) if isinstance(val, list) else str(val)
                elif isinstance(res, dict) and "search_result" in res:
                    val     = res["search_result"]
                    content = "\n".join(val) if isinstance(val, list) else str(val)
                elif hasattr(res, "text"):
                    content = res.text
                else:
                    res_str = str(res)
                    if "'search_result': [" in res_str:
                        try:
                            parts   = res_str.split("'search_result': [")[1].split("]")[0]
                            content = parts.replace("\\n", "\n").replace("'", "").strip()
                        except Exception:
                            content = res_str
                    else:
                        content = res_str

                content = content.replace("['", "").replace("']", "").replace("', '", "\n")

                if content and content not in [f["description"] for f in known_findings]:
                    # Generate a pattern_hash for this memory item
                    # -> enables deduplication if the same finding appears again
                    mem_hash = hashlib.sha256(content.strip().encode()).hexdigest()
                    known_hashes.add(mem_hash)

                    known_findings.append({
                        "contract":     contract_name,
                        "type":         "Historical Memory",
                        "description":  content.strip(),
                        "pattern_hash": mem_hash,
                    })
        else:
            print("ℹ️  [Phase 1] No specific memory found in the graph.")

    except Exception as e:
        print(f"⚠️  [Phase 1] Cognee Recall Error : {e}")

    return known_findings, known_hashes


async def run_inventory(scope: ResolvedContract):
    """Run full inventory with deduplication enabled."""
    print(f"🔍 [Phase 1] Analyzing {len(scope.files)} file(s)...")

    await setup_cognee()

    # Load memory + known hashes
    known_findings, known_hashes = await load_known_findings(scope)

    inventory_details = []
    duplicates_count  = 0

    for file_path in scope.files:
        stats       = analyze_solidity_file(file_path)
        file_hash   = generate_file_hash(file_path)

        # Check deduplication for each detected flag
        file_duplicates = []
        for flag in stats["flags"]:
            p_hash = generate_pattern_hash(flag, file_hash)
            if is_duplicate(p_hash, known_hashes):
                file_duplicates.append(flag)
                duplicates_count += 1
                print(f"  ♻️  Duplicate detected: {flag} in {os.path.basename(file_path)}")

        inventory_details.append({
            "file":         file_path,
            "flags":        stats["flags"],
            "stats":        stats,
            "pattern_hash": file_hash,
            "duplicates":   file_duplicates,     # already known flags
            "is_duplicate": len(file_duplicates) == len(stats["flags"]) and len(stats["flags"]) > 0,
        })

    return {
        "files_analyzed":      len(scope.files),
        "details":             inventory_details,
        "duplicates_detected": duplicates_count,
        "known_findings":      known_findings,
        "known_findings_count": len(known_findings),
    }