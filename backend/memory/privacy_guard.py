def sanitize_finding_for_memory(finding: dict) -> dict:
    """
    Garde-fou Privacy : S'assure qu'on ne stocke aucune donnée client sensible
    avant l'injection dans la base Cognee.
    """
    # On crée une copie pour ne pas modifier l'objet original en cours d'audit
    sanitized = finding.copy()
    
    # 1. Purger l'adresse du contrat (privacy client)
    if "contract_address" in sanitized:
        sanitized["contract_address"] = "REDACTED_ADDRESS"
        
    # 2. Purger le nom du projet (confidentialité de l'audit)
    if "project_name" in sanitized:
        sanitized["project_name"] = "REDACTED_PROJECT"
        
    # 3. Ne jamais stocker le code source brut complet (propriété intellectuelle)
    if "raw_code" in sanitized:
        del sanitized["raw_code"]
        
    return sanitized