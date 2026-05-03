# server.py
import os
import base64
import httpx
import json
import hashlib
from fastapi import FastAPI, Request, HTTPException, Header, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from typing import Any, AsyncGenerator, Optional, List
import uuid
from datetime import datetime
from x402 import x402ResourceServer, ResourceConfig
from x402.http import HTTPFacilitatorClient, FacilitatorConfig
from x402.mechanisms.evm.exact import ExactEvmServerScheme

from pipeline.phase_resolve import resolve_scope
from pipeline.phase1_inventory import run_inventory
from pipeline.phase2_slither import run_slither
from pipeline.phase3_triage import run_triage
from pipeline.phase4_agent import run_investigation
from pipeline.phase5_anchor import run_phase5_anchor
from pipeline.phase6_report import run_report          # ← NEW
from pipeline.streaming import stream_audit_pipeline   # ← NEW (NDJSON streaming)
from payments.x402_pricing import calculate_price
from keeper.direct_api import anchor_contribution
from storage.audits_store import load_audits, save_audit

load_dotenv()


def _prepare_audit_for_storage(audit: dict) -> None:
    """Champs dérivés pour l’historique (fichier ou Postgres)."""
    report = audit.get("report", {})
    audit["verdict"]     = report.get("verdict") or _map_verdict(audit.get("triage", {}))
    audit["risk_score"]  = report.get("risk_score") or audit.get("triage", {}).get("risk_score", 0)
    audit["findings"]    = report.get("findings") or _format_findings(audit.get("slither", {}))
    audit["memory_hits"] = _format_memory_hits(audit.get("inventory", {}))
    audit["ens"]         = report.get("ens")


def _save_audit(audit: dict):
    _prepare_audit_for_storage(audit)
    save_audit(audit)


def _format_findings(slither_data: dict) -> list:
    findings = []
    for i, f in enumerate(slither_data.get("findings", [])):
        impact   = f.get("impact", "").lower()
        severity = (
            "HIGH"   if impact == "high"   else
            "MEDIUM" if impact == "medium" else
            "LOW"    if impact == "low"    else
            "INFO"
        )
        findings.append({
            "id":             f"f-{i + 1:03d}",
            "severity":       severity,
            "confidence":     "CONFIRMED" if severity == "HIGH" else "LIKELY",
            "title":          f.get("check", "Unknown"),
            "file":           f.get("file", "unknown"),
            "description":    f.get("description", ""),
            "recommendation": "See description above.",
        })
    return findings


def _format_memory_hits(inventory_data: dict) -> list:
    return [
        {
            "query":            kf.get("contract", ""),
            "match":            kf.get("description", "")[:80],
            "confidence_boost": 2,
        }
        for kf in inventory_data.get("known_findings", [])
    ]


def _map_verdict(triage_data: dict) -> str:
    score   = triage_data.get("risk_score", 0)
    verdict = triage_data.get("verdict", "").upper()
    if verdict == "SAFE" or score < 3:
        return "SAFE"
    elif verdict in ("DANGER", "ERROR") or score >= 7:
        return "HIGH_RISK"
    elif verdict == "CAUTION" or score >= 4:
        return "MEDIUM_RISK"
    else:
        return "LOW_RISK"


app = FastAPI(title="Onchor.ai API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── x402 setup ────────────────────────────────────────────────────────────────

RECEIVER_ADDRESS = os.getenv("RECEIVER_ADDRESS")
FACILITATOR_URL  = os.getenv("X402_FACILITATOR_URL", "https://x402.org/facilitator")
NETWORK          = "eip155:84532"
API_BASE_URL     = os.getenv("API_BASE_URL", "http://localhost:8000")

facilitator = HTTPFacilitatorClient(FacilitatorConfig(url=FACILITATOR_URL))
x402_server = x402ResourceServer(facilitator)
x402_server.register(NETWORK, ExactEvmServerScheme())
x402_server.initialize()


def _build_requirements(nb_files: int, price_usd: float):
    config = ResourceConfig(
        scheme="exact",
        network=NETWORK,
        pay_to=RECEIVER_ADDRESS,
        price=f"${price_usd:.2f}",
        resource=f"{API_BASE_URL}/audit",
        description=f"Onchor.ai audit — {nb_files} file(s)",
    )
    return x402_server.build_payment_requirements(config)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {"message": "Onchor.ai Backend is running!"}


@app.get("/audit/quote")
async def get_audit_quote(path: str):
    scope     = await resolve_scope(path)
    nb_files  = len(scope.files)
    price_usd = calculate_price(nb_files)
    reqs      = _build_requirements(nb_files, price_usd)
    return {
        "files_count":          nb_files,
        "price_usd":            price_usd,
        "payment_requirements": [r.model_dump() for r in reqs],
    }


@app.post("/audit")
async def run_audit(
    request: Request,
    path: str,
    x_payment: Optional[str] = Header(default=None),
):
    if not x_payment:
        raise HTTPException(
            status_code=402,
            detail="Missing X-PAYMENT header. Call GET /audit/quote first.",
        )

    scope     = await resolve_scope(path)
    nb_files  = len(scope.files)
    price_usd = calculate_price(nb_files)
    reqs      = _build_requirements(nb_files, price_usd)
    reqs_dict = [r.model_dump() for r in reqs]

    try:
        from x402.schemas import PaymentPayload
        payload_json = base64.b64decode(x_payment).decode("utf-8")
        payload_dict = json.loads(payload_json)
        payload      = PaymentPayload.model_validate(payload_dict)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid X-PAYMENT header: {e}")

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as http:
        facilitator_resp = await http.post(
            f"{FACILITATOR_URL}/verify",
            json={
                "x402Version":         payload_dict.get("x402Version", 2),
                "paymentPayload":      payload_dict,
                "paymentRequirements": reqs_dict[0],
            },
        )
        facilitator_data = facilitator_resp.json()

    if not facilitator_data.get("isValid"):
        raise HTTPException(
            status_code=402,
            detail=f"Invalid payment: {facilitator_data.get('invalidReason', 'unknown')}",
        )

    async with httpx.AsyncClient(timeout=300.0, follow_redirects=True) as http:
        settle_resp = await http.post(
            f"{FACILITATOR_URL}/settle",
            json={
                "x402Version":         payload_dict.get("x402Version", 2),
                "paymentPayload":      payload_dict,
                "paymentRequirements": reqs_dict[0],
            },
        )
        settle_data = settle_resp.json()

    if not settle_data.get("success"):
        raise HTTPException(
            status_code=402,
            detail=f"Settlement failed: {settle_data.get('error', 'unknown')}",
        )

    tx_hash = settle_data.get("transaction")
    print(f"✅ USDC settled onchain — tx: {tx_hash}")

    # ── Pipeline complet ──────────────────────────────────────────────────────
    target = path
    if scope.is_onchain and scope.files:
        target = os.path.dirname(scope.files[0])

    inventory_data     = await run_inventory(scope)
    slither_data       = await run_slither(target)
    triage_data        = await run_triage(slither_data, inventory_data)
    investigation_data = await run_investigation(scope, slither_data, inventory_data, triage_data)

    # Phase 5: security anchoring
    anchored_findings = await run_phase5_anchor(investigation_data.get("findings", []))
    investigation_data["findings"] = anchored_findings

    # Phase 6 : Rapport final                                                  ← NEW
    report = await run_report(
        scope=scope,
        slither_data=slither_data,
        inventory_data=inventory_data,
        triage_data=triage_data,
        investigation_data=investigation_data,
        target_address=path if path.startswith("0x") else None,
    )

    # Persistance
    audit_record = {
        "id":             str(uuid.uuid4()),
        "created_at":     datetime.utcnow().isoformat() + "Z",
        "target": {
            "kind":  "address" if path.startswith("0x") else "path",
            "value": os.path.basename(path) if not path.startswith("0x") else path,
        },
        "mode":            "paid",
        "price_paid":      price_usd,
        "triage":          triage_data,
        "slither":         slither_data,
        "inventory":       inventory_data,
        "investigation":   investigation_data,
        "report":          report,                       # ← NEW
        "anchored_count":  report["summary"]["anchored_count"],
        "scope":           {"files_found": nb_files, "is_onchain": scope.is_onchain},
    }
    _save_audit(audit_record)

    if triage_data.get("risk_score", 0) < 3:
        return {
            "status":  "success",
            "phase":   "gate_safe",
            "message": "Contract assessed as SAFE.",
            "triage":  triage_data,
            "report":  report,
        }

    return {
        "status": "success",
        "scope": {
            "files_found": nb_files,
            "is_onchain":  scope.is_onchain,
            "upstream":    scope.upstream.name if scope.upstream else None,
        },
        "inventory":     inventory_data,
        "slither":       slither_data,
        "triage":        triage_data,
        "investigation": investigation_data,
        "report":        report,                         # ← NEW
    }


@app.post("/audit/local")
async def run_audit_local(path: str):
    """Free route — --local or --dev mode, without payment."""
    scope  = await resolve_scope(path)
    target = path
    if scope.is_onchain and scope.files:
        target = os.path.dirname(scope.files[0])

    inventory_data     = await run_inventory(scope)
    slither_data       = await run_slither(target)
    triage_data        = await run_triage(slither_data, inventory_data)
    investigation_data = await run_investigation(scope, slither_data, inventory_data, triage_data)

    # Phase 5
    anchored_findings = await run_phase5_anchor(investigation_data.get("findings", []))
    investigation_data["findings"] = anchored_findings

    # Phase 6                                                                   ← NEW
    report = await run_report(
        scope=scope,
        slither_data=slither_data,
        inventory_data=inventory_data,
        triage_data=triage_data,
        investigation_data=investigation_data,
        target_address=path if path.startswith("0x") else None,
    )

    return {
        "status": "success",
        "scope": {
            "files_found": len(scope.files),
            "is_onchain":  scope.is_onchain,
        },
        "inventory":       inventory_data,
        "slither":         slither_data,
        "triage":          triage_data,
        "investigation":   investigation_data,
        "report":          report,                       # ← NEW
        "anchored_count":  report["summary"]["anchored_count"],
    }


# ── Streaming variants (NDJSON) ──────────────────────────────────────────────
# Streaming variants of the routes above. Emit one JSON event per line
# (`application/x-ndjson`) during the 7 phases so the CLI can display
# a dynamic progress bar. Final payload is strictly identical to non-stream routes.


@app.post("/audit/local/stream")
async def run_audit_local_stream(path: str):
    """Streaming variant of /audit/local — NDJSON, one event per phase."""
    scope = await resolve_scope(path)
    if not scope.files:
        raise HTTPException(
            status_code=400,
            detail=f"No Solidity files found: {path}"
        )
    return StreamingResponse(
        stream_audit_pipeline(path),
        media_type="application/x-ndjson",
        headers={
            "X-Accel-Buffering": "no",
            "Cache-Control":     "no-cache",
        },
    )


@app.post("/audit/stream")
async def run_audit_stream(
    request: Request,
    path: str,
    x_payment: Optional[str] = Header(default=None),
):
    """Streaming variant of /audit (paid) — NDJSON, one event per phase.

    x402 payment (verify + settle) emits two `phase: payment` events at stream start.
    Pipeline starts only if settlement succeeds.
    """
    if not x_payment:
        raise HTTPException(
            status_code=402,
            detail="Missing X-PAYMENT header. Call GET /audit/quote first.",
        )

    # ── x402 pre-validation (synchronous — may 4xx before streaming) ─────────
    scope     = await resolve_scope(path)
    if not scope.files:
        raise HTTPException(
            status_code=400,
            detail=f"No Solidity files found: {path}"
        )
    nb_files  = len(scope.files)
    price_usd = calculate_price(nb_files)
    reqs      = _build_requirements(nb_files, price_usd)
    reqs_dict = [r.model_dump() for r in reqs]

    try:
        from x402.schemas import PaymentPayload
        payload_json = base64.b64decode(x_payment).decode("utf-8")
        payload_dict = json.loads(payload_json)
        PaymentPayload.model_validate(payload_dict)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid X-PAYMENT header: {e}")

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as http:
        verify_resp = await http.post(
            f"{FACILITATOR_URL}/verify",
            json={
                "x402Version":         payload_dict.get("x402Version", 2),
                "paymentPayload":      payload_dict,
                "paymentRequirements": reqs_dict[0],
            },
        )
        verify_data = verify_resp.json()

    if not verify_data.get("isValid"):
        raise HTTPException(
            status_code=402,
            detail=f"Invalid payment: {verify_data.get('invalidReason', 'unknown')}",
        )

    # ── Wrapper async generator : payment events → pipeline → persistance ───
    async def _stream() -> AsyncGenerator[bytes, None]:
        def emit(event: dict[str, Any]) -> bytes:
            return (json.dumps(event, default=str) + "\n").encode("utf-8")

        # 1. Settle x402 — exécute le transfert USDC onchain.
        yield emit({"phase": "payment", "status": "start",
                    "msg": "Settling USDC payment via x402 facilitator..."})
        async with httpx.AsyncClient(timeout=300.0, follow_redirects=True) as http:
            settle_resp = await http.post(
                f"{FACILITATOR_URL}/settle",
                json={
                    "x402Version":         payload_dict.get("x402Version", 2),
                    "paymentPayload":      payload_dict,
                    "paymentRequirements": reqs_dict[0],
                },
            )
            settle_data = settle_resp.json()

        if not settle_data.get("success"):
            yield emit({"phase": "payment", "status": "fail",
                        "error": settle_data.get("error", "settlement failed")})
            return

        tx_hash = settle_data.get("transaction")
        print(f"USDC settled onchain — tx: {tx_hash}")
        yield emit({"phase": "payment", "status": "done",
                    "tx_hash": tx_hash, "amount_usd": price_usd})

        # 2. Pipeline streaming — capture le payload final pour persistance.
        full_result: dict[str, Any] = {}
        async for chunk in stream_audit_pipeline(
            path,
            target_address=path if path.startswith("0x") else None,
        ):
            yield chunk
            try:
                event = json.loads(chunk.decode("utf-8").rstrip("\n"))
                if event.get("phase") == "report" and event.get("status") == "done":
                    full_result = event.get("result") or {}
            except Exception:
                pass

        # 3. Persistance audit (post-pipeline) — historique paid.
        if full_result:
            try:
                report = full_result.get("report") or {}
                triage = full_result.get("triage") or {}
                audit_record = {
                    "id":             str(uuid.uuid4()),
                    "created_at":     datetime.utcnow().isoformat() + "Z",
                    "target": {
                        "kind":  "address" if path.startswith("0x") else "path",
                        "value": os.path.basename(path) if not path.startswith("0x") else path,
                    },
                    "mode":            "paid",
                    "price_paid":      price_usd,
                    "triage":          triage,
                    "slither":         full_result.get("slither", {}),
                    "inventory":       full_result.get("inventory", {}),
                    "investigation":   full_result.get("investigation", {}),
                    "report":          report,
                    "anchored_count":  report.get("summary", {}).get("anchored_count", 0),
                    "scope": {
                        "files_found": nb_files,
                        "is_onchain":  scope.is_onchain,
                    },
                }
                _save_audit(audit_record)
            except Exception as e:
                print(f"⚠ Audit persistence failed: {e}")

    return StreamingResponse(
        _stream(),
        media_type="application/x-ndjson",
        headers={
            "X-Accel-Buffering": "no",
            "Cache-Control":     "no-cache",
        },
    )


@app.post("/audit/reward")
async def send_reward(
    contributor_address: str,
    amount: float,
    findings: List[dict] = Body(default=[]),
):
    print(f"💰 Reward request received: {amount} USDC for {contributor_address}")
    clean_amount = round(float(amount), 2)
    contributed = []

    # 1. Real upload to 0G + manifest update
    if findings:
        try:
            from memory.collective_0g import contribute_patterns
            contributed = await contribute_patterns(findings)
            print(f"[0G] {len(contributed)} pattern(s) added to collective memory")
        except Exception as e:
            print(f"[0G] Contribution failed (payment still proceeds): {e}")

    # 2. USDC payment
    dummy_hash = "0x" + hashlib.sha256(contributor_address.encode()).hexdigest()
    tx_hash = await anchor_contribution(dummy_hash, dummy_hash, contributor_address, amount_usdc=clean_amount)

    if tx_hash in ["payment_failed", "error", "no_gas"]:
        detail = "USDC transfer failed."
        if tx_hash == "no_gas":
            detail = "Server wallet has no ETH — top it up via Base Sepolia faucet"
        raise HTTPException(status_code=500, detail=detail)

    return {"status": "success", "tx": tx_hash, "contributed": contributed}



@app.get("/user/balance")
async def get_user_balance(address: str):
    """Fetch real onchain USDC balance for a given address."""
    from web3 import Web3
    try:
        w3 = Web3(Web3.HTTPProvider("https://sepolia.base.org"))
        USDC_ADDRESS = "0x036CbD53842c5426634e7929541eC2318f3dCF7e"
        abi = [{"constant": True, "inputs": [{"name": "_owner", "type": "address"}],
                "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}],
                "type": "function"}]
        contract = w3.eth.contract(address=USDC_ADDRESS, abi=abi)
        raw = contract.functions.balanceOf(Web3.to_checksum_address(address)).call()
        return {"balance": raw / 1_000_000}
    except Exception as e:
        return {"balance": 0.0, "error": str(e)}


@app.get("/wallet")
async def get_wallet_info():
    from web3 import Web3
    from eth_account import Account

    private_key = os.getenv("OG_PRIVATE_KEY")
    address     = Account.from_key(private_key).address if private_key else "Not configured"

    balance_usdc = 0.0
    try:
        w3 = Web3(Web3.HTTPProvider("https://sepolia.base.org"))
        USDC_BASE_SEPOLIA = "0x036CbD53842c5426634e7929541eC2318f3dCF7e"
        abi = [{"constant": True, "inputs": [{"name": "_owner", "type": "address"}],
                "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}],
                "type": "function"}]
        contract     = w3.eth.contract(address=USDC_BASE_SEPOLIA, abi=abi)
        raw          = contract.functions.balanceOf(address).call()
        balance_usdc = raw / 1_000_000
    except Exception:
        pass

    return {"address": address, "balance_usdc": balance_usdc, "network": "Base Sepolia"}


@app.get("/audits")
async def get_audit_history():
    audits = load_audits()
    return [
        {
            "id":           a["id"],
            "created_at":   a["created_at"],
            "target":       a["target"],
            "verdict":      a.get("verdict") or _map_verdict(a.get("triage", {})),
            "risk_score":   a.get("risk_score", a.get("triage", {}).get("risk_score", 0)),
            "high_count":   a.get("report", {}).get("summary", {}).get("high_count",
                            sum(1 for f in a.get("slither", {}).get("findings", []) if f.get("impact") == "High")),
            "medium_count": a.get("report", {}).get("summary", {}).get("medium_count",
                            sum(1 for f in a.get("slither", {}).get("findings", []) if f.get("impact") == "Medium")),
            "price_paid":   a.get("price_paid"),
            "ens":          a.get("report", {}).get("ens"),    # ← NEW
        }
        for a in audits
    ]


@app.get("/audits/{audit_id}")
async def get_audit_report(audit_id: str):
    audits = load_audits()
    audit  = next((a for a in audits if a["id"] == audit_id), None)
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")

    if not audit.get("verdict"):
        audit["verdict"] = _map_verdict(audit.get("triage", {}))
    if not audit.get("risk_score"):
        audit["risk_score"] = audit.get("triage", {}).get("risk_score", 0)
    if not audit.get("findings"):
        # Préférer les findings enrichis de la Phase 6
        audit["findings"] = (
            audit.get("report", {}).get("findings")
            or _format_findings(audit.get("slither", {}))
        )
    if not audit.get("memory_hits"):
        audit["memory_hits"] = _format_memory_hits(audit.get("inventory", {}))
    if not audit.get("files_analyzed"):
        audit["files_analyzed"] = [
            d.get("file", "unknown")
            for d in audit.get("inventory", {}).get("details", [])
        ]

    return audit


@app.get("/memory")
async def get_memory_stats():
    from memory.collective_0g import _get_or_fetch_manifest
    try:
        manifest = await _get_or_fetch_manifest()
    except Exception as e:
        print(f"[0G] get_memory_stats: {e}")
        manifest = []

    total = len(manifest)
    
    # Calculate type counts
    types_count = {}
    for entry in manifest:
        t = entry.get("type", "unknown")
        types_count[t] = types_count.get(t, 0) + 1
        
    pattern_types = []
    for t, count in sorted(types_count.items(), key=lambda x: x[1], reverse=True):
        pattern_types.append({
            "type": t,
            "count": count,
            "pct": int(count / total * 100) if total > 0 else 0
        })
        
    # Convert latest entries to "recent hits" format
    recent_hits = []
    
    # Filter to only keep entries with a real tx_hash
    valid_entries = [e for e in manifest if e.get("tx_hash")]
    
    for entry in reversed(valid_entries[-50:]): # Last 50 valid ones
        recent_hits.append({
            "pattern": entry.get("type", "unknown"),
            "match": entry.get("abstract_description", ""),
            "keywords": entry.get("keywords", []),
            "pattern_hash": entry.get("pattern_hash", ""),
            "amount": "N/A",
            "confirmations": entry.get("confirmation_count", 1),
            "severity": entry.get("severity", "HIGH"),
            "tx_hash": entry.get("tx_hash", ""),
            "root_hash": entry.get("root_hash", "")
        })

    return {
        "total_patterns": total,
        "confirmed_patterns": total,
        "sources": [
            {
                "name": "Onchor.ai Agent (0xe97F...0Fd8)", 
                "count": total, 
                "color": "text-[#0DFC67]",
                "url": "https://storagescan-galileo.0g.ai/address/0xe97F62b7Bf214303419189ECD3D6688FdfF30Fd8"
            },
            {
                "name": "Slither Analyzer (Static Engine)",
                "count": total,
                "color": "text-zinc-300",
                "url": "https://github.com/crytic/slither"
            }
        ],
        "pattern_types": pattern_types,
        "recent_hits": recent_hits,
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)