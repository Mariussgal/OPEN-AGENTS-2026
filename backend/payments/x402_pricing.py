# payments/x402_pricing.py

def calculate_price(files_count: int) -> float:
    """
    Calcule le prix de l'audit en USDC selon la complexité du projet.
    Basé sur la grille tarifaire du cahier des charges Keeper Memory.
    """
    if files_count <= 3:
        return 0.50  # Petit contrat (ex: Token ERC20 simple)
    elif files_count <= 10:
        return 1.00  # Projet standard (ex: Vault + Router + interfaces)
    elif files_count <= 30:
        return 2.00  # Protocole DeFi complet
    else:
        return 4.00  # Gros protocole complexe