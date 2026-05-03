#!/usr/bin/env python3
"""
Test 0G download through same path as Python pipeline (node 0g_download.js).

Usage (depuis le dossier backend/) :
  python scripts/test_0g_live.py 0x<rootHash>

Charge ``backend/.env`` puis force ``OG_STORAGE_MODE=live`` pour cet appel,
even if your .env uses ``mock`` in dev.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__.strip(), file=sys.stderr)
        sys.exit(1)

    rh = sys.argv[1].strip()
    sys.path.insert(0, str(_BACKEND))

    from dotenv import load_dotenv

    load_dotenv(_BACKEND / ".env")

    os.environ["OG_STORAGE_MODE"] = "live"

    from storage.zero_g_client import retrieve_pattern

    data = retrieve_pattern(rh)
    print(json.dumps(data, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
