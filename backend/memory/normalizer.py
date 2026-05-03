import re

def normalize_snippet(text: str) -> str:
    """
    Normalize code snippets and descriptions to:
    1. Improve clustering in vector memory (pattern matching).
    2. Anonymize part of the data.
    """
    if not text:
        return ""

    # 1. Replace all Ethereum addresses (0x followed by 40 hex chars)
    text = re.sub(r'0x[a-fA-F0-9]{40}', 'ADDR_MASKED', text)
    
    # 2. Replace transaction hashes (0x followed by 64 hex chars)
    text = re.sub(r'0x[a-fA-F0-9]{64}', 'TX_HASH_MASKED', text)

    # 3. Normalization dictionary for common variables/concepts
    replacements = {
        "yieldAmount": "VAR_AMOUNT",
        "rewardAmount": "VAR_AMOUNT",
        "feeRecipient": "ADDR_RECIPIENT",
        "treasury": "ADDR_TREASURY",
        "msg.sender": "CALLER",
        "owner": "OWNER_ADDR"
    }
    
    for specific_term, generic_term in replacements.items():
        # We could use regex to enforce whole words (\b), 
        # but keep it simple for now.
        text = text.replace(specific_term, generic_term)
        
    return text

