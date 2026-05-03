import hashlib

def compute_pattern_hash(title: str, reason: str) -> str:
    """Canonical hash shared between Phase 4 and Phase 5."""
    return "0x" + hashlib.sha256(f"{title}-{reason}".encode()).hexdigest()