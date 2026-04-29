from memory.cognee_setup import load_known_findings, add_finding_to_memory

class ContractScope:
    """Petite classe utilitaire pour matcher la signature attendue par Cognee."""
    def __init__(self, name: str):
        self.name = name

async def query_memory(contract_name: str, is_paid: bool) -> list:
    """
    Interroge la mémoire Cognee.
    - Free (--local) : Retourne uniquement les patterns trouvés localement par l'utilisateur.
    - Paid (x402)    : Retourne le local + la base collective (Rekt, Immunefi, Audits).
    """
    print(f"🔍 [Mémoire] Recherche de patterns pour '{contract_name}'...")
    
    scope = ContractScope(contract_name)
    raw_results = await load_known_findings(scope)
    
    # 1. Mode Gratuit (Local uniquement)
    if not is_paid:
        # On exclut les résultats qui proviennent des bootstraps (marqués par "[Source:")
        local_only_results = [
            res for res in raw_results 
            if "[Source:" not in str(res)
        ]
        print(f"   ↳ 🔒 Mode gratuit activé : {len(local_only_results)} pattern(s) local(aux) trouvé(s) (Mémoire collective verrouillée).")
        return local_only_results

    # 2. Mode Payant (Local + Collectif)
    print(f"   ↳ 🌐 Mode payant (x402) actif : {len(raw_results)} pattern(s) trouvé(s) (Accès mémoire collective autorisé).")
    return raw_results

async def save_to_memory(finding: dict, contract_name: str):
    """Wrapper pour ajouter une nouvelle vulnérabilité à la mémoire."""
    await add_finding_to_memory(finding, contract_name)

# --- Test rapide si le fichier est exécuté directement ---
if __name__ == "__main__":
    import asyncio
    async def test():
        # Test mode gratuit
        await query_memory("EthCrossChainManager", is_paid=False)
        # Test mode payant
        await query_memory("EthCrossChainManager", is_paid=True)
    
    asyncio.run(test())