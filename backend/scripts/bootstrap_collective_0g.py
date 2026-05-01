"""
Bootstrap la mémoire collective sur 0G KV Storage.
À lancer UNE FOIS depuis la machine du serveur.
Usage : python -m scripts.bootstrap_collective_0g
"""

import asyncio
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from storage.zero_g_client import store_pattern, pattern_storage_payload
from pipeline.utils import compute_pattern_hash

MANIFEST_KEY = "onchor-manifest-v1"

# ─── Dataset bootstrap ────────────────────────────────────────────────────────
# Sources : Rekt.news top 100 + Immunefi disclosures + OZ/Trail of Bits audits

BOOTSTRAP_PATTERNS = [
    # ── Reentrancy ─────────────────────────────────────────────────────────────
    {
        "type": "reentrancy",
        "severity": "HIGH",
        "abstract_description": "external call before state update in withdrawal function allowing recursive drain",
        "fix_pattern": "Apply CEI: update balances[msg.sender] = 0 BEFORE external call",
        "keywords": ["reentrancy", "withdraw", "external call", "state update"],
        "confirmation_count": 14,
        "source": "Euler Finance (2024-03-15) — $197M — Rekt.news",
    },
    {
        "type": "reentrancy",
        "severity": "HIGH",
        "abstract_description": "recursive call in splitDAO function drains funds before balance update",
        "fix_pattern": "Use ReentrancyGuard modifier or CEI pattern",
        "keywords": ["reentrancy", "recursive", "balance", "drain"],
        "confirmation_count": 20,
        "source": "The DAO (2016) — $60M — Rekt.news",
    },
    {
        "type": "reentrancy",
        "severity": "HIGH",
        "abstract_description": "cross-function reentrancy via shared state variable between deposit and withdraw",
        "fix_pattern": "Use single reentrancy lock across all state-modifying functions",
        "keywords": ["reentrancy", "cross-function", "shared state"],
        "confirmation_count": 8,
        "source": "Cream Finance (2021) — $130M — Immunefi",
    },
    # ── Access Control ─────────────────────────────────────────────────────────
    {
        "type": "access_control",
        "severity": "HIGH",
        "abstract_description": "unprotected admin function allows arbitrary caller to modify privileged state",
        "fix_pattern": "Add onlyOwner or role-based access control modifier",
        "keywords": ["access control", "onlyowner", "admin", "unauthorized"],
        "confirmation_count": 11,
        "source": "Uranium Finance (2021-04-28) — $50M — Rekt.news",
    },
    {
        "type": "access_control",
        "severity": "HIGH",
        "abstract_description": "missing access control on verifyHeaderAndExecuteTx allows attacker to modify keeper set",
        "fix_pattern": "Restrict keeper modification to multisig or timelock",
        "keywords": ["access control", "keeper", "verify", "execute"],
        "confirmation_count": 9,
        "source": "Poly Network (2021) — $611M — Immunefi",
    },
    # ── Oracle Manipulation ────────────────────────────────────────────────────
    {
        "type": "oracle",
        "severity": "HIGH",
        "abstract_description": "spot price oracle manipulated via flash loan to drain protocol liquidity",
        "fix_pattern": "Use TWAP oracle with minimum 30-min window, not spot price",
        "keywords": ["oracle", "flash loan", "price manipulation", "spot price"],
        "confirmation_count": 11,
        "source": "Mango Markets (2022-10-11) — $117M — Rekt.news",
    },
    {
        "type": "oracle",
        "severity": "HIGH",
        "abstract_description": "internal price oracle based on token balance ratio manipulable in single transaction",
        "fix_pattern": "Use Chainlink price feed or Uniswap V3 TWAP",
        "keywords": ["oracle", "price", "balance ratio", "manipulation"],
        "confirmation_count": 7,
        "source": "Cream Finance (2021-10-27) — $130M — Rekt.news",
    },
    # ── Flash Loan Governance ──────────────────────────────────────────────────
    {
        "type": "governance",
        "severity": "HIGH",
        "abstract_description": "governance flash loan attack passes malicious proposal in single transaction using borrowed voting power",
        "fix_pattern": "Add time-lock on governance, snapshot voting power at block N-1",
        "keywords": ["governance", "flash loan", "voting", "proposal", "timelock"],
        "confirmation_count": 7,
        "source": "Beanstalk (2022-04-17) — $182M — Rekt.news",
    },
    # ── Proxy / Uninitialized ──────────────────────────────────────────────────
    {
        "type": "proxy",
        "severity": "HIGH",
        "abstract_description": "uninitialized proxy implementation contract allows attacker to call initialize and take ownership",
        "fix_pattern": "Call _disableInitializers() in implementation constructor",
        "keywords": ["proxy", "uninitialized", "initialize", "implementation"],
        "confirmation_count": 6,
        "source": "Wormhole (2022) — $320M — Immunefi",
    },
    {
        "type": "proxy",
        "severity": "HIGH",
        "abstract_description": "delegatecall storage collision between proxy and implementation corrupts critical state variables",
        "fix_pattern": "Use EIP-1967 storage slots for proxy variables",
        "keywords": ["delegatecall", "storage collision", "proxy", "implementation"],
        "confirmation_count": 5,
        "source": "Parity Multisig (2017) — $30M — Trail of Bits",
    },
    # ── Integer Overflow ───────────────────────────────────────────────────────
    {
        "type": "overflow",
        "severity": "HIGH",
        "abstract_description": "integer overflow in ERC20 transfer allows minting arbitrary tokens via batch operations",
        "fix_pattern": "Use Solidity 0.8+ built-in overflow checks or SafeMath",
        "keywords": ["overflow", "integer", "batch", "transfer", "mint"],
        "confirmation_count": 5,
        "source": "BeautyChain batchOverflow (2018) — Rekt.news",
    },
    # ── Signature Replay ───────────────────────────────────────────────────────
    {
        "type": "signature",
        "severity": "HIGH",
        "abstract_description": "signature malleability in ecrecover allows replay of withdrawal signatures across chains",
        "fix_pattern": "Include chainId and nonce in signed message, use OpenZeppelin ECDSA",
        "keywords": ["signature", "replay", "ecrecover", "malleability", "chainid"],
        "confirmation_count": 6,
        "source": "Polygon Plasma Bridge (2021) — $850M potential — Immunefi",
    },
    # ── Precision Loss ─────────────────────────────────────────────────────────
    {
        "type": "precision_loss",
        "severity": "MEDIUM",
        "abstract_description": "divide before multiply causes precision loss leading to incorrect reward calculation",
        "fix_pattern": "Always multiply before dividing, use fixed-point math library",
        "keywords": ["precision", "divide", "multiply", "reward", "calculation"],
        "confirmation_count": 4,
        "source": "Trail of Bits — StakingRewards audit",
    },
    # ── Front Running ──────────────────────────────────────────────────────────
    {
        "type": "front_running",
        "severity": "MEDIUM",
        "abstract_description": "transaction ordering dependence allows MEV sandwich attack on AMM price impact",
        "fix_pattern": "Add deadline and minimum output amount parameters, use commit-reveal",
        "keywords": ["front running", "mev", "sandwich", "ordering", "amm"],
        "confirmation_count": 9,
        "source": "Classic MEV — Flashbots research",
    },
    # ── Honeypot / Arbitrary Mint ──────────────────────────────────────────────
    {
        "type": "arbitrary_balance_assignment",
        "severity": "HIGH",
        "abstract_description": "admin function assigns arbitrary balance to caller bypassing totalSupply constraints, enabling unlimited minting",
        "fix_pattern": "Remove _balances[msg.sender] = amount from non-mint functions; only _mint() should modify balances",
        "keywords": ["balance", "assignment", "admin", "maxwallet", "exempt", "rug", "honeypot"],
        "confirmation_count": 8,
        "source": "ERC20 Honeypot patterns — BSC/ETH rug pulls 2021-2024",
    },
    {
        "type": "hidden_mint_in_setter",
        "severity": "HIGH",
        "abstract_description": "setter function for a configuration parameter secretly modifies token balances, classic rug pull vector",
        "fix_pattern": "Setter functions must only modify their declared state variable, never _balances",
        "keywords": ["setter", "balance", "mint", "hidden", "rug", "erc20", "exempt"],
        "confirmation_count": 6,
        "source": "Token audit patterns — Trail of Bits / Immunefi",
    },
    {
        "type": "maxwallet_bypass_mint",
        "severity": "HIGH", 
        "abstract_description": "maxWalletExempt or similar whitelist allows arbitrary balance inflation for privileged addresses",
        "fix_pattern": "Exempt lists should only bypass transfer limits, never touch _balances directly",
        "keywords": ["maxwallet", "exempt", "whitelist", "balance", "inflation"],
        "confirmation_count": 5,
        "source": "BSC honeypot analysis — DeFiYield REKT database",
    },
]


async def bootstrap():
    print(f"🚀 Bootstrap mémoire collective sur 0G Storage")
    print(f"   {len(BOOTSTRAP_PATTERNS)} patterns à uploader...")
    print()

    manifest = []
    success = 0
    failed = 0

    for i, p in enumerate(BOOTSTRAP_PATTERNS):
        title = p["abstract_description"][:60]
        reason = p["fix_pattern"]
        ph = compute_pattern_hash(title, reason)

        payload = {
            "schema": "onchor-ai/pattern/v1",
            "pattern_hash": ph,
            "pattern_type": p["type"],
            "abstract_description": p["abstract_description"],
            "fix_pattern": p["fix_pattern"],
            "severity": p["severity"],
            "confidence": "CONFIRMED",
            "confirmation_count": p["confirmation_count"],
            "keywords": p["keywords"],
            "source": p["source"],
        }

        try:
            root_hash = store_pattern(payload)
            manifest.append({
                "pattern_hash": ph,
                "root_hash": root_hash,
                "type": p["type"],
                "severity": p["severity"],
                "abstract_description": p["abstract_description"],
                "keywords": p["keywords"],
            })
            success += 1
            print(f"  [{i+1:2d}/{len(BOOTSTRAP_PATTERNS)}] ✅ {p['type']:20s} → {root_hash[:20]}...")
        except Exception as e:
            failed += 1
            print(f"  [{i+1:2d}/{len(BOOTSTRAP_PATTERNS)}] ❌ {p['type']:20s} → {e}")

    print()
    print(f"📋 Upload manifest ({len(manifest)} entrées)...")
    try:
        manifest_payload = {
            "schema": "onchor-ai/manifest/v1",
            "key": "onchor-manifest-v1",
            "entries": manifest,
        }
        manifest_root = store_pattern(manifest_payload)
        print(f"✅ Manifest uploadé → rootHash: {manifest_root}")
    except Exception as e:
        print(f"❌ Manifest échoué : {e}")

    print()
    print(f"─── Résultat ───────────────────────────────")
    print(f"  Patterns uploadés : {success}/{len(BOOTSTRAP_PATTERNS)}")
    print(f"  Patterns échoués  : {failed}")
    print(f"  Manifest root     : {manifest_root if success > 0 else 'N/A'}")
    print()
    print("⚠️  Note : copie ce rootHash dans .env comme MANIFEST_ROOT_HASH")
    print(f"   MANIFEST_ROOT_HASH={manifest_root if success > 0 else 'à remplir'}")


if __name__ == "__main__":
    asyncio.run(bootstrap())