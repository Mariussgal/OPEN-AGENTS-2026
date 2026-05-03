def sanitize_finding_for_memory(finding: dict) -> dict:
    """
    Privacy guardrail: ensure no sensitive client data is stored
    avant l'injection dans la base Cognee.
    """
    # Create a copy to avoid mutating the original object during audit
    sanitized = finding.copy()
    
    # 1. Strip contract address (client privacy)
    if "contract_address" in sanitized:
        sanitized["contract_address"] = "REDACTED_ADDRESS"
        
    # 2. Strip project name (audit confidentiality)
    if "project_name" in sanitized:
        sanitized["project_name"] = "REDACTED_PROJECT"
        
    # 3. Never store full raw source code (intellectual property)
    if "raw_code" in sanitized:
        del sanitized["raw_code"]
        
    return sanitized