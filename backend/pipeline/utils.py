import hashlib

def compute_pattern_hash(title: str, reason: str) -> str:
    """Hash canonique partagé entre Phase 4 et Phase 5."""
    return "0x" + hashlib.sha256(f"{title}-{reason}".encode()).hexdigest()