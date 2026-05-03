# payments/x402_pricing.py

def calculate_price(files_count: int) -> float:
    """
    Calculate audit price in USDC based on project complexity.
    Based on the Keeper Memory pricing specification.
    """
    if files_count <= 3:
        return 0.50  # Small contract (e.g. simple ERC20 token)
    elif files_count <= 10:
        return 1.00  # Standard project (e.g. Vault + Router + interfaces)
    elif files_count <= 30:
        return 2.00  # Full DeFi protocol
    else:
        return 4.00  # Large complex protocol