# server.py
import os
import base64
import httpx
import json
import hashlib
from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from typing import Optional
import json
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
from payments.x402_pricing import calculate_price

load_dotenv()

AUDITS_FILE = Path(".onchor/audits.json")
AUDITS_FILE.parent.mkdir(exist_ok=True)

def _load_audits() -> list:
    if AUDITS_FILE.exists():
        return json.loads(AUDITS_FILE.read_text())
    return []

def _save_audit(audit: dict):
    audits = _load_audits()
    # Ajouter les champs attendus par le frontend au niveau racine
    audit["verdict"]     = _map_verdict(audit["triage"])
    audit["findings"]    = _format_findings(audit.get("slither", {}))
    audit["memory_hits"] = _format_memory_hits(audit.get("inventory", {}))
    audits.insert(0, audit)
    AUDITS_FILE.write_text(json.dumps(audits, indent=2))

def _format_findings(slither_data: dict) -> list:
    """Convertit les findings Slither vers le format Finding du frontend."""
    findings = []
    for i, f in enumerate(slither_data.get("findings", [])):
        impact = f.get("impact", "").lower()
        severity = (
            "HIGH"   if impact == "high"          else
            "MEDIUM" if impact == "medium"         else
            "LOW"    if impact == "low"            else
            "INFO"
        )
        findings.append({
            "id":             f"f-{i+1:03d}",
            "severity":       severity,
            "confidence":     "CONFIRMED" if severity == "HIGH" else "LIKELY",
            "title":          f.get("check", "Unknown"),
            "file":           f.get("file", "unknown"),
            "description":    f.get("description", ""),
            "recommendation": "See description above.",
        })
    return findings


def _format_memory_hits(inventory_data: dict) -> list:
    """Convertit les known_findings Cognee vers le format MemoryHit du frontend."""
    hits = []
    for kf in inventory_data.get("known_findings", []):
        hits.append({
            "query":            kf.get("contract", ""),
            "match":            kf.get("description", "")[:80],
            "confidence_boost": 2,
        })
    return hits

def _map_verdict(triage_data: dict) -> str:
    """Convertit le verdict du triage vers le format attendu par le frontend."""
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

RECEIVER_ADDRESS  = os.getenv("RECEIVER_ADDRESS")
FACILITATOR_URL   = os.getenv("X402_FACILITATOR_URL", "https://x402.org/facilitator")
NETWORK           = "eip155:84532"  # Base Sepolia
API_BASE_URL      = os.getenv("API_BASE_URL", "http://localhost:8000")

facilitator = HTTPFacilitatorClient(FacilitatorConfig(url=FACILITATOR_URL))
x402_server = x402ResourceServer(facilitator)
x402_server.register(NETWORK, ExactEvmServerScheme())
x402_server.initialize()

# ── Helper ────────────────────────────────────────────────────────────────────

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
    """
    Route GRATUITE.
    Retourne le prix dynamique + PaymentRequirements pour Base Sepolia.
    Le CLI signe ces requirements localement avant d'appeler /audit.
    """
    scope     = await resolve_scope(path)
    nb_files  = len(scope.files)
    price_usd = calculate_price(nb_files)
    reqs = _build_requirements(nb_files, price_usd)

    return {
        "files_count": nb_files,
        "price_usd": price_usd,
        "payment_requirements": [r.model_dump() for r in reqs],  # ← liste de dicts
    }


@app.post("/audit")
async def run_audit(
    request: Request,
    path: str,
    x_payment: Optional[str] = Header(default=None),
):
    """
    Route PAYANTE.
    Vérifie le header X-PAYMENT via le facilitator Coinbase (Base Sepolia).
    Le facilitator vérifie la signature EIP-3009 et settle l'USDC onchain.
    Le client n'a pas besoin d'ETH — le facilitator paie le gas.
    """
    if not x_payment:
        raise HTTPException(
            status_code=402,
            detail="X-PAYMENT header manquant. Appelle GET /audit/quote d'abord.",
        )

    # Reconstruire les requirements côté serveur pour la vérification
    scope     = await resolve_scope(path)
    nb_files  = len(scope.files)
    price_usd = calculate_price(nb_files)
    reqs      = _build_requirements(nb_files, price_usd)
    reqs_dict = [r.model_dump() for r in reqs]

    # Décoder le payload base64 → dict pour le facilitator
    try:
        from x402.schemas import PaymentPayload
        payload_json = base64.b64decode(x_payment).decode("utf-8")
        payload_dict = json.loads(payload_json)                          # ← dict brut
        payload = PaymentPayload.model_validate(payload_dict)            # ← objet Pydantic
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"X-PAYMENT header invalide : {e}")

    # Appel facilitator avec le dict décodé (pas le base64)
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as http:
        facilitator_resp = await http.post(
            f"{FACILITATOR_URL}/verify",
            json={
                "x402Version":         payload_dict.get("x402Version", 2),
                "paymentPayload":      payload_dict,       # ← dict, pas base64
                "paymentRequirements": reqs_dict[0],
            },
        )

        facilitator_data = facilitator_resp.json()

    if not facilitator_data.get("isValid"):
        raise HTTPException(
            status_code=402,
            detail=f"Paiement invalide : {facilitator_data.get('invalidReason', 'inconnu')}",
        )

    # Settlement — c'est ici que l'USDC bouge vraiment onchain
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as http:
        settle_resp = await http.post(
            f"{FACILITATOR_URL}/settle",
            json={
                "x402Version":         payload_dict.get("x402Version", 2),
                "paymentPayload":      payload_dict,
                "paymentRequirements": reqs_dict[0],
            },
        )
        settle_data = settle_resp.json()
        print(f"=== Settle status : {settle_resp.status_code}")
        print(f"=== Settle body   : {settle_resp.text!r}")

    if not settle_data.get("success"):
        raise HTTPException(
            status_code=402,
            detail=f"Settlement échoué : {settle_data.get('error', 'inconnu')}",
        )

    tx_hash = settle_data.get("txHash")
    print(f"✅ USDC settlé onchain — tx: {tx_hash}")

    # Paiement confirmé — lancer le pipeline
    target = path
    if scope.is_onchain and scope.files:
        target = os.path.dirname(scope.files[0])

    inventory_data       = await run_inventory(scope)
    slither_data         = await run_slither(target)
    triage_data          = await run_triage(slither_data, inventory_data)
    investigation_data   = await run_investigation(scope, slither_data, inventory_data, triage_data)

    # Phase 5 : Ancrage de sécurité (filet de sécurité)
    anchored_findings = await run_phase5_anchor(investigation_data.get("findings", []))
    investigation_data["findings"] = anchored_findings

    # Sauvegarder l'audit pour l'historique frontend
    audit_record = {
        "id":         str(uuid.uuid4()),
        "created_at": datetime.utcnow().isoformat() + "Z",
        "target": {
            "kind":  "address" if path.startswith("0x") else "path",
            "value": os.path.basename(path) if not path.startswith("0x") else path,
        },
        "mode":          "paid",
        "price_paid":    price_usd,
        "triage":        triage_data,
        "slither":       slither_data,
        "inventory":     inventory_data,
        "investigation": investigation_data,
        "anchored_count": len([f for f in anchored_findings if f.get("tx_hash")]),
        "scope":         {"files_found": nb_files, "is_onchain": scope.is_onchain},
    }
    _save_audit(audit_record)

    if triage_data.get("risk_score", 0) < 3:
        return {
            "status": "success",
            "phase": "gate_safe",
            "message": "Contrat jugé SAFE.",
            "triage": triage_data,
        }

    return {
        "status": "success",
        "scope": {
            "files_found": nb_files,
            "is_onchain": scope.is_onchain,
            "upstream": scope.upstream.name if scope.upstream else None,
        },
        "inventory": inventory_data,
        "slither": slither_data,
        "triage": triage_data,
        "investigation": investigation_data,
    }


@app.post("/audit/local")
async def run_audit_local(path: str):
    """Route gratuite — mode --local ou --dev, sans paiement."""
    scope = await resolve_scope(path)
    target = path
    if scope.is_onchain and scope.files:
        target = os.path.dirname(scope.files[0])

    inventory_data       = await run_inventory(scope)
    slither_data         = await run_slither(target)
    triage_data          = await run_triage(slither_data, inventory_data)
    investigation_data   = await run_investigation(scope, slither_data, inventory_data, triage_data)

    # Phase 5 : Security anchoring (safety net)
    anchored_findings = await run_phase5_anchor(investigation_data.get("findings", []))
    investigation_data["findings"] = anchored_findings

    return {
        "status": "success",
        "scope": {
            "files_found": len(scope.files),
            "is_onchain": scope.is_onchain,
        },
        "inventory": inventory_data,
        "slither": slither_data,
        "triage": triage_data,
        "investigation": investigation_data,
        "anchored_count": len([f for f in anchored_findings if f.get("tx_hash")]),
    }


@app.get("/wallet")
async def get_wallet_info():
    """Info wallet pour le frontend."""
    from web3 import Web3
    from eth_account import Account

    private_key = os.getenv("OG_PRIVATE_KEY")
    address = Account.from_key(private_key).address if private_key else "Non configuré"

    # Solde USDC Base Sepolia
    balance_usdc = 0.0
    try:
        w3 = Web3(Web3.HTTPProvider("https://sepolia.base.org"))
        USDC_BASE_SEPOLIA = "0x036CbD53842c5426634e7929541eC2318f3dCF7e"
        abi = [{"constant": True, "inputs": [{"name": "_owner", "type": "address"}],
                "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}],
                "type": "function"}]
        contract = w3.eth.contract(address=USDC_BASE_SEPOLIA, abi=abi)
        raw = contract.functions.balanceOf(address).call()
        balance_usdc = raw / 1_000_000  # USDC a 6 décimales
    except Exception:
        pass

    return {
        "address": address,
        "balance_usdc": balance_usdc,
        "network": "Base Sepolia",
    }


@app.get("/audits")
async def get_audit_history():
    """Historique des audits pour le frontend."""
    audits = _load_audits()
    # Retourner le format AuditSummary attendu par le frontend
    return [
        {
            "id":           a["id"],
            "created_at":   a["created_at"],
            "target":       a["target"],
            "verdict":      _map_verdict(a["triage"]),
            "risk_score":   a["triage"].get("risk_score", 0),
            "high_count":   sum(1 for f in a.get("slither", {}).get("findings", []) if f["impact"] == "High"),
            "medium_count": sum(1 for f in a.get("slither", {}).get("findings", []) if f["impact"] == "Medium"),
            "price_paid":   a.get("price_paid"),
        }
        for a in audits
    ]


@app.get("/audits/{audit_id}")
async def get_audit_report(audit_id: str):
    audits = _load_audits()
    audit  = next((a for a in audits if a["id"] == audit_id), None)
    if not audit:
        raise HTTPException(status_code=404, detail="Audit non trouvé")

    # Rétrocompatibilité — calculer les champs manquants pour les anciens records
    if not audit.get("verdict"):
        audit["verdict"] = _map_verdict(audit.get("triage", {}))
    if not audit.get("risk_score"):
        audit["risk_score"] = audit.get("triage", {}).get("risk_score", 0)
    if not audit.get("findings"):
        audit["findings"] = _format_findings(audit.get("slither", {}))
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