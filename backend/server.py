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
from pathlib import Path

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

load_dotenv()

AUDITS_FILE = Path(".onchor/audits.json")
AUDITS_FILE.parent.mkdir(exist_ok=True)


def _load_audits() -> list:
    if AUDITS_FILE.exists():
        return json.loads(AUDITS_FILE.read_text())
    return []


def _save_audit(audit: dict):
    audits = _load_audits()
    audit["verdict"]     = _map_verdict(audit["triage"])
    audit["findings"]    = _format_findings(audit.get("slither", {}))
    audit["memory_hits"] = _format_memory_hits(audit.get("inventory", {}))
    audits.insert(0, audit)
    AUDITS_FILE.write_text(json.dumps(audits, indent=2))


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
        description=f"Onchor.ai audit — {nb_files} fichier(s)",
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
            detail="X-PAYMENT header manquant. Appelle GET /audit/quote d'abord.",
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
        raise HTTPException(status_code=400, detail=f"X-PAYMENT header invalide : {e}")

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
            detail=f"Paiement invalide : {facilitator_data.get('invalidReason', 'inconnu')}",
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
            detail=f"Settlement échoué : {settle_data.get('error', 'inconnu')}",
        )

    tx_hash = settle_data.get("transaction")
    print(f"✅ USDC settlé onchain — tx: {tx_hash}")

    # ── Pipeline complet ──────────────────────────────────────────────────────
    target = path
    if scope.is_onchain and scope.files:
        target = os.path.dirname(scope.files[0])

    inventory_data     = await run_inventory(scope)
    slither_data       = await run_slither(target)
    triage_data        = await run_triage(slither_data, inventory_data)
    investigation_data = await run_investigation(scope, slither_data, inventory_data, triage_data)

    # Phase 5 : Ancrage de sécurité
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
            "message": "Contrat jugé SAFE.",
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
    """Route gratuite — mode --local ou --dev, sans paiement."""
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
# Versions streaming des routes ci-dessus. Émettent un event JSON par ligne
# (`application/x-ndjson`) au fil de l'exécution des 7 phases pour que le CLI
# puisse afficher une progress bar dynamique. Le payload final est strictement
# identique à celui des routes non-stream.


@app.post("/audit/local/stream")
async def run_audit_local_stream(path: str):
    """Variante streaming de /audit/local — NDJSON, 1 event par phase."""
    scope = await resolve_scope(path)
    if not scope.files:
        raise HTTPException(
            status_code=400,
            detail=f"Aucun fichier Solidity trouvé : {path}"
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
    """Variante streaming de /audit (paid) — NDJSON, 1 event par phase.

    Le paiement x402 (verify + settle) émet deux events `phase: payment` au
    début du flux. Le pipeline démarre seulement si le settlement réussit.
    """
    if not x_payment:
        raise HTTPException(
            status_code=402,
            detail="X-PAYMENT header manquant. Appelle GET /audit/quote d'abord.",
        )

    # ── Pré-validation x402 (synchrone — peut 4xx avant streaming) ───────────
    scope     = await resolve_scope(path)
    if not scope.files:
        raise HTTPException(
            status_code=400,
            detail=f"Aucun fichier Solidity trouvé : {path}"
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
        raise HTTPException(status_code=400, detail=f"X-PAYMENT header invalide : {e}")

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
            detail=f"Paiement invalide : {verify_data.get('invalidReason', 'inconnu')}",
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
        print(f"USDC settlé onchain — tx: {tx_hash}")
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
    print(f"💰 Requête de récompense reçue : {amount} USDC pour {contributor_address}")
    clean_amount = round(float(amount), 2)
    contributed = []

    # 1. Upload réel sur 0G + mise à jour manifest
    if findings:
        try:
            from memory.collective_0g import contribute_patterns
            contributed = await contribute_patterns(findings)
            print(f"[0G] {len(contributed)} pattern(s) ajouté(s) à la mémoire collective")
        except Exception as e:
            print(f"[0G] Contribution failed (paiement quand même): {e}")

    # 2. Paiement USDC
    dummy_hash = "0x" + hashlib.sha256(contributor_address.encode()).hexdigest()
    tx_hash = await anchor_contribution(dummy_hash, dummy_hash, contributor_address, amount_usdc=clean_amount)

    if tx_hash in ["payment_failed", "error", "no_gas"]:
        detail = "Échec du transfert USDC."
        if tx_hash == "no_gas":
            detail = "Wallet serveur sans ETH — rechargez-le via faucet Base Sepolia"
        raise HTTPException(status_code=500, detail=detail)

    return {"status": "success", "tx": tx_hash, "contributed": contributed}



@app.get("/user/balance")
async def get_user_balance(address: str):
    """Récupère le solde USDC réel on-chain pour une adresse donnée."""
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
    address     = Account.from_key(private_key).address if private_key else "Non configuré"

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
    audits = _load_audits()
    return [
        {
            "id":           a["id"],
            "created_at":   a["created_at"],
            "target":       a["target"],
            "verdict":      _map_verdict(a["triage"]),
            "risk_score":   a["triage"].get("risk_score", 0),
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
    audits = _load_audits()
    audit  = next((a for a in audits if a["id"] == audit_id), None)
    if not audit:
        raise HTTPException(status_code=404, detail="Audit non trouvé")

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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)