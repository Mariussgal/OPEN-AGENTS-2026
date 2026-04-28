import re

def normalize_snippet(text: str) -> str:
    """
    Normalise les extraits de code et descriptions pour :
    1. Améliorer le clustering dans la mémoire vectorielle (pattern matching).
    2. Anonymiser une partie des données.
    """
    if not text:
        return ""

    # 1. Remplacer toutes les adresses Ethereum (0x suivi de 40 caractères hex)
    text = re.sub(r'0x[a-fA-F0-9]{40}', 'ADDR_MASKED', text)
    
    # 2. Remplacer les hash de transactions (0x suivi de 64 caractères hex)
    text = re.sub(r'0x[a-fA-F0-9]{64}', 'TX_HASH_MASKED', text)

    # 3. Dictionnaire de normalisation des variables/concepts courants
    replacements = {
        "yieldAmount": "VAR_AMOUNT",
        "rewardAmount": "VAR_AMOUNT",
        "feeRecipient": "ADDR_RECIPIENT",
        "treasury": "ADDR_TREASURY",
        "msg.sender": "CALLER",
        "owner": "OWNER_ADDR"
    }
    
    for specific_term, generic_term in replacements.items():
        # On pourrait utiliser des regex pour forcer les mots entiers (\b), 
        # mais on reste simple pour le moment.
        text = text.replace(specific_term, generic_term)
        
    return text

