#!/usr/bin/env python3
"""
Quick test for Phase 5 + live 0G + KeeperHub without running full pipeline (no LLM).

Prerequisites (backend/.env or export) ::
  OG_* for live upload · KEEPERHUB_* · ANCHOR_REGISTRY_ADDRESS

Usage (depuis ``backend/``) ::
  OG_STORAGE_MODE=live python scripts/run_e2e_quick.py

Full end-to-end audit (fixture + CLI) ::
  Terminal 1 (depuis ``backend/``) : ``python3 -m uvicorn server:app --host 127.0.0.1 --port 8000``
      ou ``bash scripts/start_api.sh``
  Terminal 2: ``cp ../contracts/fixtures/E2EMiniVault.sol ./`` ou passe le chemin absolu
             ``export OG_STORAGE_MODE=live``
             ``cd .. && onchor-ai audit contracts/fixtures/E2EMiniVault.sol --local``

Chain verification ::
  ``cd contracts && ANCHOR_RPC_URL=… npx ts-node scripts/verifyChain.ts 0x<pattern_hash>``

Download JSON ::
  ``node ../0g/0g_download.js 0x<rootHash>``
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent


def main() -> None:
    sys.path.insert(0, str(_BACKEND))
    from dotenv import load_dotenv

    load_dotenv(_BACKEND / ".env")
    os.environ.setdefault("OG_STORAGE_MODE", os.getenv("OG_STORAGE_MODE") or "live")

    async def run() -> None:
        from pipeline.phase5_anchor import run_phase5_anchor

        mock = [
            {
                "severity": "HIGH",
                "confidence": "CONFIRMED",
                "title": "E2E reentrancy sanity",
                "reason": "External call before state update (E2EMiniVault fixture).",
                "file": "E2EMiniVault.sol",
                "line": "18",
            }
        ]

        print("phase5_anchor(findings[]) — 0G upload + KeeperHub…")
        out = await run_phase5_anchor(mock)

        print(json.dumps(out, indent=2, default=str, ensure_ascii=False))
        print("\nProchaines commandes:")
        for f in out:
            if f.get("pattern_hash"):
                print(f"  verifyChain.ts: npx ts-node scripts/verifyChain.ts {f['pattern_hash']}")
            if f.get("root_hash"):
                print(f"  0g download: node 0g/0g_download.js {f['root_hash']}")

    asyncio.run(run())


if __name__ == "__main__":
    main()
