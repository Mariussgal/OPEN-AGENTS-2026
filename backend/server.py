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

app = FastAPI(title="Keeper Memory API", version="0.1.0")

# Ajout du CORS pour que le frontend Next.js de Cyriac puisse communiquer avec notre API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # En prod, mettre l'URL du frontend Vercel
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Nouvelle fonction de vérification (Middleware logique)
async def verify_x402_payment(mode: str, price: float):
    """
    Vérifie si l'audit est autorisé selon le mode et le prix.
    """
    if mode == "local":
        return True
    
    if price > 0:
        # Ici, dans une version de production, on vérifierait le TxHash onchain
        # Pour le hackathon, on valide la logique de passage
        print(f"[x402] Vérification du paiement de {price} USDC...")
        return True
    
    return False

@app.get("/")
async def root():
    return {"message": "Keeper Memory Backend is running!"}

@app.get("/audit/stream")
async def stream_audit(path: str, mode: str = "local"):
    """
    Endpoint SSE (Server-Sent Events) attendu par le frontend (streamAudit).
    Envoie les mises à jour en temps réel au client.
    """
    async def event_generator():
        # --- PHASE 0 : Resolve ---
        yield f"data: {json.dumps({'phase': 0, 'status': 'running', 'message': 'Résolution du scope...'})}\n\n"
        await asyncio.sleep(0.5) # Léger délai pour l'UX Frontend
        scope = await resolve_scope(path)
        price = calculate_price(len(scope.files))
        
        yield f"data: {json.dumps({'phase': 0, 'status': 'completed', 'files_found': len(scope.files), 'price_usdc': price, 'is_onchain': scope.is_onchain})}\n\n"

        # VERIFICATION X402
        is_paid = await verify_x402_payment(mode, price)
        if not is_paid:
            yield f"data: {json.dumps({'phase': 'error', 'message': 'Paiement x402 requis pour débloquer la mémoire collective.'})}\n\n"
            return


        if len(scope.files) == 0:
            yield f"data: {json.dumps({'phase': 'error', 'message': 'Aucun fichier Solidity trouvé.'})}\n\n"
            return

        # --- PHASE 1 : Inventory ---
        yield f"data: {json.dumps({'phase': 1, 'status': 'running', 'message': 'Inventaire et recherche de flags rapides...'})}\n\n"
        inventory_data = await run_inventory(scope)
        yield f"data: {json.dumps({'phase': 1, 'status': 'completed', 'inventory': inventory_data})}\n\n"

        # --- PHASE 2 : Slither ---
        yield f"data: {json.dumps({'phase': 2, 'status': 'running', 'message': 'Analyse statique Slither en cours...'})}\n\n"
        
        target_path = os.path.dirname(scope.files[0]) if scope.is_onchain else path
        
        slither_data = await run_slither(target_path)
        yield f"data: {json.dumps({'phase': 2, 'status': 'completed', 'findings_count': slither_data.get('findings_count', 0)})}\n\n"

        # --- PHASE 3 : Triage ---
        yield f"data: {json.dumps({'phase': 3, 'status': 'running', 'message': 'Triage par l\'IA (Claude Haiku)...'})}\n\n"
        triage_data = await run_triage(slither_data, scope.files)
        yield f"data: {json.dumps({'phase': 3, 'status': 'completed', 'risk_score': triage_data.get('risk_score'), 'verdict': triage_data.get('verdict')})}\n\n"

        # --- Fin du stream ---
        yield f"data: {json.dumps({'phase': 'done', 'message': 'Analyse terminée'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/audit/local")
async def run_audit_local(path: str, mode: str = "local"):
    # 1. RESOLVE (Phase 0)
    scope = await resolve_scope(path)
    price = calculate_price(len(scope.files))
    
    if not await verify_x402_payment(mode, price):
        raise HTTPException(status_code=402, detail="Payment Required")

    # --- CRUCIAL : Définir la cible de l'analyse ---
    # Si c'est du onchain, on analyse le dossier où on a téléchargé les fichiers
    # Si c'est local, on garde le path d'origine
    target_for_analysis = path
    if scope.is_onchain and len(scope.files) > 0:
        # On prend le dossier parent du premier fichier téléchargé
        target_for_analysis = os.path.dirname(scope.files[0])
    
    # 2. INVENTORY (Phase 1)
    inventory_data = await run_inventory(scope)
    
    # 3. SLITHER (Phase 2)
    # On passe target_for_analysis (le dossier local) au lieu de l'adresse 0x
    slither_data = await run_slither(target_for_analysis)
    
    # 4. TRIAGE (Phase 3)
    triage_data = await run_triage(slither_data, scope.files)
    
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