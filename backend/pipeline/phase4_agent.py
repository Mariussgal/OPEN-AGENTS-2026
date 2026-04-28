# backend/pipeline/phase4_agent.py
import os
import re
import json
import asyncio
import hashlib
import subprocess
from openai import OpenAI
from dotenv import load_dotenv

from .phase_resolve import ResolvedContract
from memory.cognee_setup import setup_cognee

load_dotenv()

# ─── Client ───────────────────────────────────────────────────────────────────

def get_agent_client():
    return OpenAI(
        api_key=os.getenv("LLM_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL", "https://ai-gateway.vercel.sh/v1")
    )

MODEL = "anthropic/claude-sonnet-4-5"
MAX_TURNS = 30

# ─── System prompt ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an adversarial Solidity security researcher.
Read code as an attacker would — not as a checklist auditor.

MINDSET:
- Every external call is a potential reentrancy until proven otherwise
- Every access control is potentially bypassable
- Assume the developer made mistakes where complexity is high
- Trace the full call graph before dismissing anything

CONFIDENCE LEVELS:
- SUSPECTED : pattern looks dangerous, needs deeper analysis
- LIKELY    : strong indicators, consistent with known exploit patterns
- CONFIRMED : exploit path fully traced + memory cross-reference done

RULES:
1. Read the full function before concluding
2. Always call query_memory before escalating to CONFIRMED
3. Only anchor LIKELY and CONFIRMED (never SUSPECTED)
4. Never stop at the first finding

FINDING FORMAT (use this exact format):
FINDING: <HIGH|MEDIUM|LOW> | <SUSPECTED|LIKELY|CONFIRMED> | <title> | <file>:<line>
REASON: <one sentence technical explanation>
"""

# ─── Tool schemas ─────────────────────────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_contract",
            "description": "Read the full source code of a Solidity file or a specific function",
            "parameters": {
                "type": "object",
                "properties": {
                    "file": {"type": "string", "description": "Path to the .sol file"},
                    "function_name": {"type": "string", "description": "Optional: specific function to extract"}
                },
                "required": ["file"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_pattern",
            "description": "Search a regex pattern across all .sol files in scope",
            "parameters": {
                "type": "object",
                "properties": {
                    "regex": {"type": "string", "description": "Regex pattern to search"}
                },
                "required": ["regex"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_call_graph",
            "description": "Get the call graph of a contract via Slither",
            "parameters": {
                "type": "object",
                "properties": {
                    "contract": {"type": "string", "description": "Path to the .sol file"}
                },
                "required": ["contract"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_storage_layout",
            "description": "Get storage slot layout to detect collisions or shadowing",
            "parameters": {
                "type": "object",
                "properties": {
                    "contract": {"type": "string", "description": "Path to the .sol file"}
                },
                "required": ["contract"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_memory",
            "description": "Query Cognee memory for similar vulnerability patterns",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Natural language query"},
                    "collective": {"type": "boolean", "description": "Include collective memory (paid tier)", "default": True}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "simulate_call",
            "description": "Simulate a contract call to observe state changes (optional, skipped in dev mode)",
            "parameters": {
                "type": "object",
                "properties": {
                    "signature": {"type": "string", "description": "Function signature e.g. withdraw(uint256)"},
                    "args": {"type": "array", "items": {"type": "string"}, "description": "Call arguments"}
                },
                "required": ["signature"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "anchor_finding",
            "description": "Anchor a LIKELY or CONFIRMED finding onchain via KeeperHub. Never call for SUSPECTED.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern_hash": {"type": "string", "description": "SHA-256 of the normalized snippet"},
                    "root_hash": {"type": "string", "description": "0G Storage rootHash"}
                },
                "required": ["pattern_hash", "root_hash"]
            }
        }
    }
]

# ─── Tool implementations ─────────────────────────────────────────────────────

def tool_read_contract(file: str, function_name: str = None) -> str:
    """Lit le source Solidity d'un fichier ou d'une fonction spécifique."""
    if not os.path.exists(file):
        return f"ERROR: File not found: {file}"
    with open(file, "r", encoding="utf-8") as f:
        content = f.read()
    if not function_name:
        return content
    # Extraire la fonction spécifique via regex simple
    pattern = rf"function\s+{re.escape(function_name)}\s*\(.*?(?=\n\s*function|\Z)"
    match = re.search(pattern, content, re.DOTALL)
    if match:
        return match.group(0)
    return f"Function '{function_name}' not found in {file}.\nFull file:\n{content}"


def tool_search_pattern(regex: str, scope_files: list[str]) -> str:
    """Grep regex sur tous les .sol du scope."""
    results = []
    for file in scope_files:
        if not os.path.exists(file):
            continue
        with open(file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        for i, line in enumerate(lines, 1):
            if re.search(regex, line):
                results.append(f"{file}:{i}: {line.rstrip()}")
    if not results:
        return f"No matches found for pattern: {regex}"
    return "\n".join(results)


def tool_get_call_graph(contract: str) -> str:
    """Call graph via Slither."""
    try:
        result = subprocess.run(
            ["slither", contract, "--print", "call-graph"],
            capture_output=True, text=True, timeout=30
        )
        output = result.stdout or result.stderr
        return output[:3000] if output else "No call graph output"
    except subprocess.TimeoutExpired:
        return "ERROR: Slither call-graph timed out"
    except Exception as e:
        return f"ERROR: {e}"


def tool_get_storage_layout(contract: str) -> str:
    """Storage layout via Slither."""
    try:
        result = subprocess.run(
            ["slither", contract, "--print", "variable-order"],
            capture_output=True, text=True, timeout=30
        )
        output = result.stdout or result.stderr
        return output[:3000] if output else "No storage layout output"
    except subprocess.TimeoutExpired:
        return "ERROR: Slither storage layout timed out"
    except Exception as e:
        return f"ERROR: {e}"


async def tool_query_memory(query: str, collective: bool = True) -> str:
    """Interroge Cognee — local + collectif si paid tier."""
    try:
        import cognee
        results = await cognee.recall(query)
        if not results:
            return "No memory hits found."
        hits = []
        for res in results[:3]:  # max 3 hits
            content = ""
            if hasattr(res, "search_result"):
                val = getattr(res, "search_result")
                content = "\n".join(val) if isinstance(val, list) else str(val)
            elif isinstance(res, dict) and "search_result" in res:
                val = res["search_result"]
                content = "\n".join(val) if isinstance(val, list) else str(val)
            else:
                content = str(res)
            content = content.replace("['", "").replace("']", "").replace("', '", "\n")
            hits.append(content.strip()[:500])
        return "\n---\n".join(hits)
    except Exception as e:
        return f"Memory query error: {e}"


def tool_simulate_call(signature: str, args: list = None) -> str:
    """Simulation Tenderly — optionnel, skippé en dev."""
    return f"[simulate_call skipped — Tenderly not configured] signature={signature} args={args}"


async def tool_anchor_finding(pattern_hash: str, root_hash: str) -> str:
    """Ancre un finding LIKELY/CONFIRMED via KeeperHub Direct Execution API."""
    keeperhub_api_key = os.getenv("KEEPERHUB_API_KEY")
    anchor_registry = os.getenv("ANCHOR_REGISTRY_ADDRESS")

    if not keeperhub_api_key or not anchor_registry:
        return f"[anchor skipped — KEEPERHUB_API_KEY or ANCHOR_REGISTRY_ADDRESS not set] pattern_hash={pattern_hash}"

    try:
        import httpx
        async with httpx.AsyncClient(timeout=30.0) as http:
            resp = await http.post(
                "https://app.keeperhub.com/api/execute/contract-call",
                headers={"X-API-Key": keeperhub_api_key},
                json={
                    "contractAddress": anchor_registry,
                    "network": "84532",  # Base Sepolia
                    "functionName": "anchor",
                    "functionArgs": json.dumps([pattern_hash, root_hash])
                }
            )
            data = resp.json()
            execution_id = data.get("executionId", "unknown")
            tx_hash = data.get("transactionHash", "pending")
            print(f"  ✓ Anchored onchain — executionId: {execution_id} tx: {tx_hash}")
            return f"Anchored — executionId: {execution_id} | tx: {tx_hash}"
    except Exception as e:
        return f"Anchor error: {e}"


# ─── Tool dispatcher ──────────────────────────────────────────────────────────

async def dispatch_tool(tool_name: str, tool_args: dict, scope_files: list[str]) -> str:
    """Route l'appel outil de Claude vers la bonne implémentation."""
    if tool_name == "read_contract":
        return tool_read_contract(
            tool_args["file"],
            tool_args.get("function_name")
        )
    elif tool_name == "search_pattern":
        return tool_search_pattern(tool_args["regex"], scope_files)
    elif tool_name == "get_call_graph":
        return tool_get_call_graph(tool_args["contract"])
    elif tool_name == "get_storage_layout":
        return tool_get_storage_layout(tool_args["contract"])
    elif tool_name == "query_memory":
        return await tool_query_memory(
            tool_args["query"],
            tool_args.get("collective", True)
        )
    elif tool_name == "simulate_call":
        return tool_simulate_call(
            tool_args["signature"],
            tool_args.get("args", [])
        )
    elif tool_name == "anchor_finding":
        from keeper.mcp_tools import anchor_finding_mcp
        return await anchor_finding_mcp(
            tool_args["pattern_hash"],
            tool_args["root_hash"],
            contributor_address=os.getenv("RECEIVER_ADDRESS")
        )
    else:
        return f"ERROR: Unknown tool '{tool_name}'"


# ─── Finding parser ───────────────────────────────────────────────────────────

def parse_findings_from_text(text: str) -> list[dict]:
    if not text:
        return []

    findings = []

    # Nettoyer le markdown avant de parser
    clean_text = re.sub(r'\*+', '', text)        # supprimer **
    clean_text = re.sub(r'`+', '', clean_text)   # supprimer ```
    clean_text = re.sub(r'#+\s*', '', clean_text) # supprimer ## headers

    # Format strict sur texte nettoyé
    pattern = r"FINDING:\s*(HIGH|MEDIUM|LOW)\s*\|\s*(SUSPECTED|LIKELY|CONFIRMED)\s*\|\s*([^|\n]+?)\s*\|\s*([^\n]+?)\s*\nREASON:\s*([^\n]+)"
    matches = re.findall(pattern, clean_text, re.IGNORECASE | re.MULTILINE)

    for match in matches:
        severity, confidence, title, location, reason = match
        location = location.strip().rstrip("*").rstrip("-").strip()
        file_ref = location.split(":")[0].strip() if ":" in location else location
        line_ref = location.split(":")[1].strip() if ":" in location else None
        findings.append({
            "severity":   severity.strip().upper(),
            "confidence": confidence.strip().upper(),
            "title":      title.strip(),
            "file":       file_ref,
            "line":       line_ref,
            "reason":     reason.strip(),
        })

    # Fallback si format strict pas trouvé
    if not findings:
        lines = clean_text.split("\n")
        for i, line in enumerate(lines):
            for sev in ["HIGH", "MEDIUM", "LOW"]:
                for conf in ["CONFIRMED", "LIKELY", "SUSPECTED"]:
                    if sev in line and conf in line and "|" in line:
                        parts = [p.strip() for p in line.split("|")]
                        reason_line = ""
                        for j in range(i+1, min(i+3, len(lines))):
                            if "REASON:" in lines[j]:
                                reason_line = lines[j].replace("REASON:", "").strip()
                                break
                        findings.append({
                            "severity":   sev,
                            "confidence": conf,
                            "title":      parts[2] if len(parts) > 2 else line.strip(),
                            "file":       parts[3].split(":")[0] if len(parts) > 3 else "unknown",
                            "line":       parts[3].split(":")[1] if len(parts) > 3 and ":" in parts[3] else None,
                            "reason":     reason_line,
                        })

    return findings


# ─── Main agent loop ──────────────────────────────────────────────────────────

async def run_investigation(
    scope: ResolvedContract,
    slither_data: dict,
    inventory_data: dict,
    triage_data: dict
) -> dict:
    """
    Agent adversarial claude-sonnet-4-5 avec 7 outils, 30 turns max.
    Retourne les findings confirmés + anchors onchain.
    """
    print(f"🕵️  [Phase 4] Agent adversarial — {len(scope.files)} fichier(s)...")
    await setup_cognee()

    client = get_agent_client()

    # Contexte initial pour l'agent
    slither_summary = "\n".join([
        f"- [{f['impact']}] {f['check']}: {f['description'][:100]}..."
        for f in slither_data.get("findings", [])
    ])
    files_list = "\n".join(scope.files)
    memory_hints = "\n".join([
        kf.get("description", "")[:200]
        for kf in inventory_data.get("known_findings", [])
    ])

    initial_message = f"""Audit scope:
FILES:
{files_list}

SLITHER PRE-ANALYSIS:
{slither_summary or "No Slither findings"}

MEMORY HINTS (from past audits):
{memory_hints or "No memory hits yet"}

TRIAGE SCORE: {triage_data.get('risk_score', 0)}/10 — {triage_data.get('verdict', 'UNKNOWN')}

Start your adversarial investigation. Read the contracts, trace call graphs, 
query memory, and confirm or dismiss each finding. Anchor LIKELY and CONFIRMED only.
"""

    messages = [{"role": "user", "content": initial_message}]
    all_findings = []
    anchored_txs = []
    turns = 0

    while turns < MAX_TURNS:
        turns += 1
        print(f"  [Turn {turns}/{MAX_TURNS}]", end=" ", flush=True)

        # AJOUT : Pause pour éviter le Rate Limit de la Vercel AI Gateway
        # 4 secondes x 10 turns = 40 secondes (en dessous du quota de 60s)
        await asyncio.sleep(4.0) 

        response = await asyncio.to_thread(
            client.chat.completions.create,
            model=MODEL,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0,
            max_tokens=4096,
        )

        choice = response.choices[0]
        msg = choice.message

        # Ajouter la réponse à l'historique
        messages.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments}
                }
                for tc in (msg.tool_calls or [])
            ] or None
        })

        # Parser les findings du texte libre
        if msg.content:
            print(f"thinking...")
            new_findings = parse_findings_from_text(msg.content)
            if new_findings:
                all_findings.extend(new_findings)
                print(f"  → {len(new_findings)} finding(s) detected")

        # Exécuter les tool calls
        if msg.tool_calls:
            tool_results = []
            for tc in msg.tool_calls:
                tool_name = tc.function.name
                tool_args = json.loads(tc.function.arguments)
                print(f"  → tool: {tool_name}({list(tool_args.keys())})")

                result = await dispatch_tool(tool_name, tool_args, scope.files)

                # Tracker les anchors
                if tool_name == "anchor_finding" and "tx:" in str(result):
                    anchored_txs.append(result)

                tool_results.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": str(result)[:2000]  # limite pour éviter overflow
                })

            messages.extend(tool_results)

        # Stop si l'agent a fini (pas de tool calls + message de conclusion)
        elif choice.finish_reason == "stop":
            print(f"  ✓ Agent concluded after {turns} turns")
            break

    # Dédupliquer les findings par titre
    seen_titles = set()
    unique_findings = []
    for f in all_findings:
        if f["title"] not in seen_titles:
            seen_titles.add(f["title"])
            unique_findings.append(f)

    print(f"\n✅ [Phase 4] {len(unique_findings)} unique finding(s) — {len(anchored_txs)} anchor(s)")

    return {
        "findings": unique_findings,
        "anchored": anchored_txs,
        "turns_used": turns,
        "model": MODEL,
    }