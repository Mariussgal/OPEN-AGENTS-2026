from memory.cognee_setup import load_known_findings, add_finding_to_memory

class ContractScope:
    """Small utility class matching Cognee expected signature."""
    def __init__(self, name: str):
        self.name = name

async def query_memory(contract_name: str, is_paid: bool) -> list:
    """
    Query Cognee memory.
    - Free (--local): returns only user-local patterns.
    - Paid (x402): returns local + collective base (Rekt, Immunefi, Audits).
    """
    print(f"🔍 [Memory] Searching patterns for '{contract_name}'...")
    
    scope = ContractScope(contract_name)
    raw_results = await load_known_findings(scope)
    
    # 1) Free mode (local only)
    if not is_paid:
        # Exclude bootstrap results (marked by "[Source:")
        local_only_results = [
            res for res in raw_results 
            if "[Source:" not in str(res)
        ]
        print(f"   ↳ 🔒 Free mode enabled: {len(local_only_results)} local pattern(s) found (collective memory locked).")
        return local_only_results

    # 2) Paid mode (local + collective)
    print(f"   ↳ 🌐 Paid mode (x402) active: {len(raw_results)} pattern(s) found (collective memory access enabled).")
    return raw_results

async def save_to_memory(finding: dict, contract_name: str):
    """Wrapper to add a new vulnerability to memory."""
    await add_finding_to_memory(finding, contract_name)

# --- Quick test when executed directly ---
if __name__ == "__main__":
    import asyncio
    async def test():
        # Free mode test
        await query_memory("EthCrossChainManager", is_paid=False)
        # Paid mode test
        await query_memory("EthCrossChainManager", is_paid=True)
    
    asyncio.run(test())