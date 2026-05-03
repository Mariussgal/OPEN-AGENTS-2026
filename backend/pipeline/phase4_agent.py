# backend/pipeline/phase4_agent.py
from typing import Any
import os
import re
import json
import asyncio
import subprocess
import hashlib
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

# MODEL and MAX_TURNS are now defined dynamically in run_investigation()

# ─── System prompt ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an adversarial Solidity security researcher.

INVESTIGATION ORDER — mandatory:
1. read_contract (full file) FIRST — always
2. get_call_graph if external calls detected
3. search_pattern only to CONFIRM a hypothesis already formed from reading
4. query_memory before escalating any finding to CONFIRMED
5. anchor_finding only for LIKELY or CONFIRMED

HARD LIMITS:
- Maximum 4 consecutive search_pattern calls — then you MUST use a structural tool
- Maximum 8 search_pattern calls total per file
- If you haven't found anything after 10 turns: conclude, don't loop

SCRATCHPAD — maintain this across turns:
After each structural tool call, update your internal state:
- READING: <file> — <what you found>
- HYPOTHESIS: <title> — <status: investigating/confirmed/dismissed>
- CONFIRMED: <finding> — <evidence>

Example:
READING: Token.sol — found setMaxWalletOnOff() assigns _balances directly
HYPOTHESIS: Arbitrary balance assignment — investigating
...
CONFIRMED: HIGH — setMaxWalletOnOff arbitrary mint — line 153

MINDSET:
- Read code as an attacker, not as a checklist auditor
- A full read_contract call reveals more than 10 regex searches
- Complexity hides bugs — trace call graphs before dismissing

CONFIDENCE LEVELS:
- SUSPECTED : pattern looks dangerous
- LIKELY    : strong indicators
- CONFIRMED : exploit path fully traced + query_memory done

FINDING FORMAT:
FINDING: <HIGH|MEDIUM|LOW> | <SUSPECTED|LIKELY|CONFIRMED> | <title> | <file>:<line>
REASON: <one sentence>
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
                    "query": {"type": "string", "description": "Natural language query"}
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
            "description": "Anchor a LIKELY or CONFIRMED finding onchain. JSON stored on 0G; omit root_hash unless overriding.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern_hash": {"type": "string", "description": "SHA-256 hex of normalized snippet"},
                    "root_hash": {"type": "string", "description": "Optional 0G root — leave empty for server-side upload"},
                    "title": {"type": "string", "description": "Finding title"},
                    "reason": {"type": "string", "description": "Technical reason"},
                    "severity": {"type": "string", "description": "HIGH|MEDIUM|LOW"},
                    "confidence": {"type": "string"},
                    "file": {"type": "string"},
                    "line": {"type": "string"}
                },
                "required": ["pattern_hash", "title", "reason"]
            }
        }
    }
]

# ─── Tool implementations ─────────────────────────────────────────────────────

def tool_read_contract(file: str, function_name: str = None) -> str:
    """Read Solidity source from a file or specific function."""
    if not os.path.exists(file):
        return f"ERROR: File not found: {file}"
    with open(file, "r", encoding="utf-8") as f:
        content = f.read()
    if not function_name:
        return content
    # Extract the specific function with a simple regex
    pattern = rf"function\s+{re.escape(function_name)}\s*\(.*?(?=\n\s*function|\Z)"
    match = re.search(pattern, content, re.DOTALL)
    if match:
        return match.group(0)
    return f"Function '{function_name}' not found in {file}.\nFull file:\n{content}"


def tool_search_pattern(regex: str, scope_files: list[str]) -> str:
    """Run regex grep across all .sol files in scope."""
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


async def tool_query_memory(query: str) -> str:
    output_lines = []

    # -- 1. Local Cognee memory --
    try:
        import cognee
        local_results = await cognee.recall(query)
        if local_results:
            for res in local_results[:3]:
                content = _extract_cognee_content(res)
                if content:
                    output_lines.append(f"[Local Memory] {content[:400]}")
    except Exception as e:
        output_lines.append(f"[Local Memory] error: {e}")

    # -- 2. 0G collective memory --
    try:
        from memory.collective_0g import (
            query_collective_memory,
            format_collective_results,
        )
        collective_results = await query_collective_memory(query)
        print(f"[DEBUG 0G] query='{query}' -> {len(collective_results)} results")
        if collective_results:
            formatted = format_collective_results(collective_results)
            output_lines.append(formatted)
    except Exception as e:
        import traceback
        print(f"[0G DETAILED ERROR] {e}")
        traceback.print_exc()
        output_lines.append(f"[0G Collective] error: {e}")

    if not output_lines:
        return "No memory hits found."

    return "\n---\n".join(output_lines)


def _extract_cognee_content(res) -> str:
    """Helper to extract content from a Cognee result."""
    if hasattr(res, "search_result"):
        val = getattr(res, "search_result")
        return "\n".join(val) if isinstance(val, list) else str(val)
    if isinstance(res, dict) and "search_result" in res:
        val = res["search_result"]
        return "\n".join(val) if isinstance(val, list) else str(val)
    return str(res)


def tool_simulate_call(signature: str, args: list = None) -> str:
    """Tenderly simulation — optional, skipped in dev."""
    return f"[simulate_call skipped — Tenderly not configured] signature={signature} args={args}"


async def tool_anchor_finding(pattern_hash: str, root_hash: str) -> str:
    """Anchor a LIKELY/CONFIRMED finding via KeeperHub (see keeper/hub_anchor)."""
    from keeper.hub_anchor import keeperhub_anchor_registry

    kh = await keeperhub_anchor_registry(pattern_hash, root_hash)
    if kh.get("skipped"):
        return "[anchor skipped — KEEPERHUB_API_KEY or ANCHOR_REGISTRY_ADDRESS not set]"
    if kh.get("error"):
        return f"Anchor error: {kh['error']}"
    tx = kh.get("tx_hash")
    exe = kh.get("execution_id")
    print(f"  ✓ Anchored — executionId: {exe} tx: {tx}")
    return f"Anchored — executionId: {exe} | tx: {tx or 'pending'}"


# ─── Tool dispatcher ──────────────────────────────────────────────────────────

async def dispatch_tool(tool_name: str, tool_args: dict, scope_files: list[str]) -> str:
    """Route Claude tool call to the correct implementation."""
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
        return await tool_query_memory(tool_args["query"])
    elif tool_name == "simulate_call":
        return tool_simulate_call(
            tool_args["signature"],
            tool_args.get("args", [])
        )
    elif tool_name == "anchor_finding":
        confidence = (tool_args.get("confidence") or "").upper().strip()
        severity   = (tool_args.get("severity") or "").upper().strip()

        # Block SUSPECTED, empty, or unknown
        if confidence not in ("LIKELY", "CONFIRMED"):
            return (
                f"[anchor_finding BLOCKED] confidence='{confidence}' — "
                f"only LIKELY and CONFIRMED are anchored. "
                f"Re-evaluate this finding before anchoring."
            )

        # Also block if severity is too low
        if severity == "LOW":
            return (
                f"[anchor_finding BLOCKED] severity=LOW — "
                f"only MEDIUM+ findings are anchored."
            )

        ph = tool_args.get("pattern_hash", "")
        if not re.match(r"^(0x)?[0-9a-fA-F]{64}$", ph):
            raw = f"{tool_args.get('title', '')}-{tool_args.get('reason', '')}"
            ph = "0x" + hashlib.sha256(raw.encode()).hexdigest()
            tool_args["pattern_hash"] = ph

        from keeper.mcp_tools import anchor_finding_mcp
        return await anchor_finding_mcp(
            tool_args["pattern_hash"],
            tool_args.get("root_hash"),
            title=tool_args.get("title", ""),
            reason=tool_args.get("reason", ""),
            severity=severity,
            confidence=confidence,
            file=tool_args.get("file", ""),
            line=tool_args.get("line"),
            contributor_address=os.getenv("RECEIVER_ADDRESS"),
        )
    else:
        return f"ERROR: Unknown tool '{tool_name}'"


# ─── Finding parser ───────────────────────────────────────────────────────────

def parse_findings_from_text(text: str) -> list[dict]:
    if not text:
        return []

    findings = []

    # Clean markdown before parsing
    clean_text = re.sub(r'\*+', '', text)        # supprimer **
    clean_text = re.sub(r'`+', '', clean_text)   # supprimer ```
    clean_text = re.sub(r'#+\s*', '', clean_text) # supprimer ## headers

    # Strict format on cleaned text
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

    # Fallback if strict format is not found
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


DANGEROUS_PATTERNS = {
    r"_balances\[.*\]\s*=\s*(?!_balances\[|0\b)": "CRITICAL: Direct balance assignment",
    r"selfdestruct\s*\(": "CRITICAL: selfdestruct present",
    r"delegatecall\s*\(": "HIGH: delegatecall present",
    r"tx\.origin\s*==": "MEDIUM: tx.origin authentication",
    r"block\.(timestamp|number)\s*[<%>]": "MEDIUM: block variable manipulation",
    # Reentrancy: external call AND balance update in the same file
    r"\.call\{value:": "HIGH: External ETH call — check for reentrancy",
    r"transferWithAuthorization|permit\(": "MEDIUM: EIP-2612/3009 — check replay protection",
    r"initialize\s*\(": "MEDIUM: Initializer — check if protected",
}

FIX_HINTS = {
    "Direct balance assignment": "Remove the direct _balances[addr] = value assignment. Balance changes must only occur via _mint(), _burn(), or _transfer() with proper supply validation.",
    "selfdestruct present": "Remove selfdestruct or restrict to multisig with timelock.",
    "delegatecall present": "Use EIP-1967 storage slots to avoid storage collision.",
}


def _get_fix_hint(label: str) -> str:
    for key, hint in FIX_HINTS.items():
        if key in label:
            return hint
    return "Manual review required."


def _pre_screen(files: list[str]) -> list[dict]:
    """Deterministic regex detection of critical patterns before LLM audit."""
    hits = []
    for file in files:
        try:
            with open(file, "r", encoding="utf-8") as f:
                content = f.read()
                for pattern, label in DANGEROUS_PATTERNS.items():
                    if re.search(pattern, content, re.MULTILINE):
                        hits.append({"label": label, "file": file})
        except Exception:
            pass
    return hits


def _slither_to_hypotheses(findings: list[dict]) -> str:
    """Transform Slither findings into investigation hypotheses for the agent."""
    hypotheses = []
    for f in findings:
        impact = str(f.get("impact", "")).upper()
        if impact in ("HIGH", "MEDIUM"):
            hypotheses.append(
                f"HYPOTHESIS: {f['check']} detected in {f.get('file', 'unknown')} — "
                f"INVESTIGATE and CONFIRM or DISMISS\n"
                f"Evidence: {f.get('description', '')[:200]}"
            )
    if not hypotheses:
        return "No critical hypotheses from Slither."
    return "\n\n".join(hypotheses)


async def _call_llm_with_retry(client, **kwargs) -> Any:
    """LLM call with exponential retry on 429, no systematic sleep."""
    for attempt in range(3):
        try:
            return await asyncio.to_thread(
                client.chat.completions.create,
                **kwargs
            )
        except Exception as e:
            err_msg = str(e).lower()
            if "429" in err_msg or "rate_limit" in err_msg or "too many requests" in err_msg:
                wait = 0.5 * (2 ** attempt)  # 0.5s, 1s, 2s
                print(f"  ⚠ Rate limit, retry dans {wait}s...")
                await asyncio.sleep(wait)
            else:
                raise
    raise RuntimeError("Persistent LLM rate limit after 3 attempts")


# ─── Main agent loop ──────────────────────────────────────────────────────────

async def run_investigation(
    scope: ResolvedContract,
    slither_data: dict,
    inventory_data: dict,
    triage_data: dict
) -> dict:
    """
    Adversarial claude-sonnet-4-5 agent with 7 tools, 30 turns max.
    Returns confirmed findings + onchain anchors.
    """
    print(f"🕵️  [Phase 4] Adversarial agent — {len(scope.files)} file(s)...")
    await setup_cognee()
    auto_findings: list[dict] = []

    # 1. Deterministic pre-screening (to drive routing)
    screening_hits = _pre_screen(scope.files)
    screening_str = "\n".join([f"!!! {h['label']} in {h['file']}" for h in screening_hits])

    # Full short-circuit when requested via ENV (bypass LLM for obvious CRITICAL findings)
    critical_hits = [h for h in screening_hits if "CRITICAL" in h["label"]]
    if critical_hits:
        print(f"  ⚡ Fast-path: {len(critical_hits)} critical pattern(s) detected by regex")
        
        # Generate preliminary findings without LLM
        auto_findings = [{
            "severity": "HIGH",
            "confidence": "LIKELY",
            "title": h["label"].split(": ", 1)[1] if ": " in h["label"] else h["label"],
            "file": h["file"],
            "line": None,
            "reason": f"Deterministic pattern match: {h['label']}",
            "fix_hint": _get_fix_hint(h["label"]),
        } for h in critical_hits]

        if os.getenv("ONCHOR_SKIP_LLM_ON_CRITICAL", "").lower() == "true":
            print("  ⚡ ONCHOR_SKIP_LLM_ON_CRITICAL=true — full LLM agent bypass")
            return {
                "findings": auto_findings,
                "anchored": [],
                "turns_used": 0,
                "model": "deterministic-prescreening",
            }

    # 2. Hybrid architecture: routing based on pre-screening + triage score
    risk_score = float(triage_data.get("risk_score", 0))
    
    if screening_hits and any("CRITICAL" in h["label"] for h in screening_hits):
        # Critical pattern detected -> Haiku is sufficient for quick confirmation
        MODEL = "anthropic/claude-haiku-4-5"
        MAX_TURNS = 5
    elif risk_score >= 7:
        # Cas complexe/haut risque → Sonnet requis
        MODEL = "anthropic/claude-sonnet-4-5"
        MAX_TURNS = 25
    elif risk_score >= 4:
        # Risque moyen
        MODEL = "anthropic/claude-haiku-4-5"
        MAX_TURNS = 15
    else:
        # Risque faible
        MODEL = "anthropic/claude-haiku-4-5"
        MAX_TURNS = 8

    print(f"  ↳ Routing: {MODEL} ({MAX_TURNS} turns max) | Risk: {risk_score}")

    # Preload collective memory (Phase 1++)
    if critical_hits:
        print("  ⚡ Fast-path: skip collective memory pre-load")
        memory_context = "Skipped — fast-path confirmation mode. Query memory tool if needed."
    else:
        print("  ⟳  Pre-loading collective memory...")
        memory_query = "ERC20 token vulnerabilities balance assignment admin function honeypot access control"
        try:
            memory_context = await asyncio.wait_for(
                tool_query_memory(memory_query),
                timeout=3.0
            )
        except asyncio.TimeoutError:
            print("  ⚠ Memory timeout (3s): the agent will query on demand")
            memory_context = "Memory timeout during pre-load. Use query_memory tool if needed."
        except Exception as e:
            print(f"  ⚠ Memory error: {e}")
            memory_context = f"Memory error: {e}"

    client = get_agent_client()

    # Initial context for the agent (preload code to save turns)
    initial_context = {}
    for file in scope.files:
        try:
            with open(file, "r", encoding="utf-8") as f:
                content = f.read()
            line_count = content.count("\n")
            
            if line_count < 200:
                initial_context[file] = content
            else:
                # Too large for initial input (can degrade Haiku performance)
                initial_context[file] = (
                    f"[File too large — use read_contract tool]\n"
                    f"Line count: {line_count}\n"
                    f"Flagged by pre-screening: {screening_str}"
                )
        except Exception as e:
            print(f"  ⚠ Unable to load {file}: {e}")
            initial_context[file] = f"[ERROR: could not read file — {e}]"

    slither_findings = slither_data.get("findings", [])
    slither_summary = "\n".join([
        f"- [{f['impact']}] {f['check']}: {f['description'][:100]}..."
        for f in slither_findings
    ])
    slither_hypotheses = _slither_to_hypotheses(slither_findings)

    memory_hints = "\n".join([
        kf.get("description", "")[:200]
        for kf in inventory_data.get("known_findings", [])
    ])

    initial_message = f"""Audit scope — contracts already loaded:

{chr(10).join(f'=== {path} ==={chr(10)}{content}' for path, content in initial_context.items())}

SLITHER PRE-ANALYSIS:
{slither_summary or "No Slither findings"}

COLLECTIVE MEMORY (pre-loaded — use this as reference):
{memory_context}

DETERMINISTIC PRE-SCREENING HITS (CRITICAL):
{screening_str or "No direct critical hits detected."}

HYPOTHESES TO INVESTIGATE (from Slither):
{slither_hypotheses}

MEMORY HINTS (from past audits):
{memory_hints or "No memory hits yet"}

TRIAGE SCORE: {triage_data.get('risk_score', 0)}/10 — {triage_data.get('verdict', 'UNKNOWN')}

Start your adversarial investigation. You already have the code above. 
For each hypothesis: read the relevant function, trace the call graph, 
then CONFIRM or DISMISS with a one-line reason. 
Anchor LIKELY and CONFIRMED only.
"""

    # Short-circuit if critical pre-screening was already triggered
    if critical_hits:
        print(f"  ⚡ Pre-screening short-circuit: {len(critical_hits)} critical finding(s) detected")
        print("  ↳ LLM agent running in CONFIRMATION-ONLY mode")

        # Agent only confirms, not explores
        initial_message += f"""
\n⚠️  CRITICAL PATTERNS ALREADY DETECTED by deterministic analysis:
{screening_str}

Your ONLY job: CONFIRM or DISMISS each hit above. 
Do NOT explore further. Read only the flagged functions. Max 5 turns.
"""
        MAX_TURNS = 5  # Override

    messages = [{"role": "user", "content": initial_message}]
    all_findings = []
    anchored_txs = []
    pending_anchors: dict[str, dict[str, str]] = {}
    turns = 0

    # --- State variables for guardrails ---
    seen_regexes = set()
    total_regex_calls = 0
    consecutive_regex_calls = 0
    structural_calls = 0
    turns_since_finding = 0

    while turns < MAX_TURNS:
        turns += 1
        turns_since_finding += 1
        print(f"  [Turn {turns}/{MAX_TURNS}]", end=" ", flush=True)

        response = await _call_llm_with_retry(
            client,
            model=MODEL,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0,
            max_tokens=4096,
        )

        choice = response.choices[0]
        msg = choice.message

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

        if msg.content:
            print(f"thinking...")
            new_findings = parse_findings_from_text(msg.content)
            if new_findings:
                turns_since_finding = 0  # Reset
                for f in new_findings:
                    if f["title"] in pending_anchors:
                        anchor_data = pending_anchors.pop(f["title"])
                        f["execution_id"] = anchor_data["execution_id"]
                        f["pattern_hash"] = anchor_data["pattern_hash"]
                all_findings.extend(new_findings)
                print(f"  → {len(new_findings)} finding(s) detected")

        if msg.tool_calls:
            tool_results = []
            for tc in msg.tool_calls:
                tool_name = tc.function.name
                tool_args = json.loads(tc.function.arguments)
                print(f"  → tool: {tool_name}({list(tool_args.keys())})")

                # --- Apply guardrails ---
                if tool_name == "search_pattern":
                    regex = tool_args.get("regex", "")
                    if regex in seen_regexes:
                        result = "ERROR: You already searched for this exact regex. Use a different strategy."
                    elif total_regex_calls >= 8:
                        result = "ERROR: Regex budget exceeded (max 8). You MUST use structural tools like read_contract or get_call_graph."
                    elif consecutive_regex_calls >= 3:
                        result = "ERROR: Too many consecutive regex searches (max 3). You MUST use a structural tool now."
                    else:
                        seen_regexes.add(regex)
                        total_regex_calls += 1
                        consecutive_regex_calls += 1
                        result = await dispatch_tool(tool_name, tool_args, scope.files)
                else:
                    consecutive_regex_calls = 0  # Reset du streak
                    if tool_name in ("read_contract", "get_call_graph", "get_storage_layout"):
                        structural_calls += 1
                    
                    result = await dispatch_tool(tool_name, tool_args, scope.files)

                if tool_name == "anchor_finding" and not isinstance(result, str):
                    result = str(result)
                
                if tool_name == "anchor_finding":
                    anchored_txs.append(result)
                    exe_match = re.search(r'executionId:\s*(\S+)', str(result))
                    if exe_match:
                        exe_id = exe_match.group(1).rstrip("|").strip()
                        title_arg = tool_args.get("title", "")
                        ph = tool_args.get("pattern_hash", "")
                        pending_anchors[title_arg] = {
                            "execution_id": exe_id,
                            "pattern_hash": ph,
                        }

                tool_results.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": str(result)[:2000]
                })

            # If severe stagnation occurs, force a reminder
            if turns_since_finding >= 8 and len(all_findings) == 0:
                tool_results.append({
                    "role": "user",
                    "content": "SYSTEM NOTICE: You have been searching for several turns without any findings. If you believe the contract is secure, you MUST STOP your investigation immediately and output your conclusion. Do not force findings."
                })

            messages.extend(tool_results)

        # Stop if agent has finished (no tool calls + conclusion message)
        elif choice.finish_reason == "stop":
            print(f"  ✓ Agent concluded after {turns} turns")
            break

    # Deduplicate findings by title
    seen_titles = set()
    unique_findings = []
    for f in all_findings:
        if f["title"] not in seen_titles:
            seen_titles.add(f["title"])
            unique_findings.append(f)

    findings = unique_findings
    if not findings and turns == 0 and auto_findings:
        findings = auto_findings
    elif not findings and auto_findings:
        for f in auto_findings:
            f["confidence"] = "SUSPECTED"
            f["severity"] = "MEDIUM"
        findings = auto_findings

    print(f"\n✅ [Phase 4] {len(unique_findings)} unique finding(s) — {len(anchored_txs)} anchor(s)")

    return {
        "findings": findings,
        "anchored": anchored_txs,
        "turns_used": turns,
        "model": MODEL,
    }