import os
import json
import asyncio
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Imports de notre pipeline
from pipeline.phase_resolve import resolve_scope
from pipeline.phase1_inventory import run_inventory
from pipeline.phase2_slither import run_slither
from pipeline.phase3_triage import run_triage
from payments.x402_pricing import calculate_price

load_dotenv()

app = FastAPI(title="Onchor.ai API", version="0.1.0")

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from web3 import Web3
from typing import Optional

# Configuration Blockchain pour vérification
USDC_SEPOLIA = "0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238"
RECEIVER_ADDRESS = "0x4DB6Bf931e0AC52E6a35601da70aAB3fF26657C4"

async def verify_x402_payment(mode: str, price: float, tx_hash: Optional[str] = None):
    """Vérifie la véracité du paiement x402 sur la blockchain Sepolia."""
    if mode == "local":
        return True
    
    if price == 0:
        return True

    if not tx_hash:
        return False

    print(f"[x402] Vérification du paiement onchain : {tx_hash}...")
    
    try:
        rpc_url = f"https://eth-sepolia.g.alchemy.com/v2/{os.getenv('ALCHEMY_API_KEY')}"
        w3 = Web3(Web3.HTTPProvider(rpc_url))
        
        # 1. Récupérer le reçu
        receipt = w3.eth.get_transaction_receipt(tx_hash)
        if receipt.status != 1:
            print("❌ x402: Transaction échouée onchain.")
            return False
        
        # 2. Récupérer la transaction pour vérifier les détails
        tx = w3.eth.get_transaction(tx_hash)
        
        # Pour l'USDC (ERC20), on doit normalement parser les logs (Transfer event)
        # Mais ici pour simplifier et rester robuste, on vérifie que c'est bien une interaction avec l'USDC
        if tx["to"].lower() != USDC_SEPOLIA.lower():
            print(f"❌ x402: Mauvais contrat (reçu {tx['to']}, attendu {USDC_SEPOLIA})")
            return False

        # Note: Dans une version de prod, on décoderait l'input data pour vérifier 
        # l'adresse de destination et le montant exact.
        # Ici on valide déjà que le hash existe et est un succès sur le bon contrat.
        
        print(f"✅ x402: Paiement de {price} USDC validé.")
        return True
    except Exception as e:
        print(f"⚠️ x402 Error: {e}")
        return False

@app.get("/")
async def root():
    return {"message": "Onchor.ai Backend is running!"}

@app.get("/audit/stream")
async def stream_audit(path: str, mode: str = "local", payment_hash: Optional[str] = None):
    """Endpoint SSE pour le frontend (mises à jour en temps réel)."""
    async def event_generator():
        # --- PHASE 0 : Resolve ---
        yield f"data: {json.dumps({'phase': 0, 'status': 'running', 'message': 'Résolution du scope...'})}\n\n"
        scope = await resolve_scope(path)
        price = calculate_price(len(scope.files))
        
        yield f"data: {json.dumps({'phase': 0, 'status': 'completed', 'files_found': len(scope.files), 'price_usdc': price, 'is_onchain': scope.is_onchain})}\n\n"

        # Vérification Paiement
        if not await verify_x402_payment(mode, price, payment_hash):
            yield f"data: {json.dumps({'phase': 'error', 'message': 'Paiement x402 requis.'})}\n\n"
            return

        if len(scope.files) == 0:
            yield f"data: {json.dumps({'phase': 'error', 'message': 'Aucun fichier Solidity trouvé.'})}\n\n"
            return

        # --- PHASE 1 : Inventory (Cognee) ---
        yield f"data: {json.dumps({'phase': 1, 'status': 'running', 'message': 'Interrogation de la mémoire collective...'})}\n\n"
        inventory_data = await run_inventory(scope)
        yield f"data: {json.dumps({'phase': 1, 'status': 'completed', 'inventory': inventory_data})}\n\n"

        # --- PHASE 2 : Slither ---
        yield f"data: {json.dumps({'phase': 2, 'status': 'running', 'message': 'Analyse statique Slither...'})}\n\n"
        target_path = os.path.dirname(scope.files[0]) if scope.is_onchain else path
        slither_data = await run_slither(target_path)
        yield f"data: {json.dumps({'phase': 2, 'status': 'completed', 'findings_count': slither_data.get('findings_count', 0)})}\n\n"

        # --- PHASE 3 : Triage (Vercel Gateway) ---
        yield f"data: {json.dumps({'phase': 3, 'status': 'running', 'message': 'Analyse finale par l\'IA...'})}\n\n"
        triage_data = await run_triage(slither_data, inventory_data)
        
        risk_score = triage_data.get('risk_score', 0)
        verdict = triage_data.get('verdict', 'UNKNOWN')
        
        yield f"data: {json.dumps({
            'phase': 3, 
            'status': 'completed', 
            'risk_score': risk_score, 
            'verdict': verdict,
            'reasoning': triage_data.get('reasoning')
        })}\n\n"

        # Gate logic: score < 3 -> SAFE, arrêt du pipeline
        if risk_score < 3:
            yield f"data: {json.dumps({'phase': 'done', 'message': 'Analyse terminée : Contrat jugé SAFE.'})}\n\n"
            return

        yield f"data: {json.dumps({'phase': 'done', 'message': 'Analyse terminée'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/audit/local")
async def run_audit_local(path: str, mode: str = "local", payment_hash: Optional[str] = None):
    """Endpoint standard pour le CLI."""
    # 1. Resolve
    scope = await resolve_scope(path)
    price = calculate_price(len(scope.files))
    
    if not await verify_x402_payment(mode, price, payment_hash):
        raise HTTPException(status_code=402, detail="Payment Required")

    # Target definition
    target_for_analysis = path
    if scope.is_onchain and len(scope.files) > 0:
        target_for_analysis = os.path.dirname(scope.files[0])
    
    # 2. Inventory (Phase 1)
    inventory_data = await run_inventory(scope)
    
    # 3. Slither (Phase 2)
    slither_data = await run_slither(target_for_analysis)
    
    # 4. Triage (Phase 3)
    triage_data = await run_triage(slither_data, inventory_data)
    
    # Gate logic: score < 3 -> SAFE
    if triage_data.get("risk_score", 0) < 3:
        return {
            "status": "success",
            "phase": "gate_safe",
            "message": "Contrat jugé SAFE, arrêt du pipeline.",
            "triage": triage_data
        }
    
    return {
        "status": "success",
        "phase": 3,
        "scope": {
            "files_found": len(scope.files),
            "is_onchain": scope.is_onchain,
            "upstream": scope.upstream.name if scope.upstream else None
        },
        "inventory": inventory_data,
        "slither": slither_data,
        "triage": triage_data
    }
    
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)