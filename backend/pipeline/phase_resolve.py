import os
import json
import httpx
from pathlib import Path
from typing import List, Optional, Dict
from dataclasses import dataclass

@dataclass
class UpstreamRef:
    name: str
    repo_url: str
    version: str

@dataclass
class ResolvedContract:
    files: List[str]
    is_onchain: bool
    upstream: Optional[UpstreamRef] = None
    address: Optional[str] = None

# Upstream database with metadata for future diffing
KNOWN_UPSTREAMS_DB = {
    "0x1f98431c8ad98523631ae4a59f267346ea31f984": UpstreamRef("Uniswap V3", "https://github.com/Uniswap/v3-core", "v1.0.0"),
    "0x49ca165bd6aee88825f59c557bc52a685e0594b5": UpstreamRef("Euler Vault", "https://github.com/euler-xyz/euler-vault", "v1.0")
}

async def detect_upstream_from_code(content: str) -> Optional[UpstreamRef]:
    """Detect upstream by scanning imports in local code."""
    if "IUniswapV2Router" in content or "UniswapV2" in content:
        return UpstreamRef("Uniswap V2 Fork", "https://github.com/Uniswap/v2-core", "unknown")
    if "@openzeppelin/contracts" in content:
        return UpstreamRef("OpenZeppelin Standard", "https://github.com/OpenZeppelin/openzeppelin-contracts", "latest")
    return None


_CHAIN_ID_BY_NAME = {
    "mainnet": "1",
    "ethereum": "1",
    "sepolia": "11155111",
}


def _resolve_chain_candidates() -> list[str]:
    """
    Etherscan lookup order for 0x addresses.
    Default: Sepolia then Mainnet (retro-compatible + mainnet support).
    """
    raw = (os.getenv("ONCHOR_ETHERSCAN_CHAIN_PRIORITY") or "11155111,1").strip()
    candidates = [c.strip() for c in raw.split(",") if c.strip()]
    return candidates or ["11155111", "1"]


async def fetch_etherscan_source(address: str) -> List[str]:
    api_key = os.getenv("ETHERSCAN_API_KEY")
    print(f"[Phase 0] Calling Etherscan V2 for {address}...")

    if not api_key:
        print("❌ Missing ETHERSCAN_API_KEY.")
        return []

    async with httpx.AsyncClient() as client:
        for chainid in _resolve_chain_candidates():
            try:
                url = (
                    "https://api.etherscan.io/v2/api"
                    f"?chainid={chainid}"
                    f"&module=contract&action=getsourcecode&address={address}&apikey={api_key}"
                )
                response = await client.get(url)
                data = response.json()
            except Exception as e:
                print(f"❌ Etherscan network error (chain {chainid}): {e}")
                continue

            # In API V2, success is validated by "status" == "1"
            if data.get("status") != "1":
                print(f"ℹ️ No verified code for {address} on chainid={chainid} ({data.get('result')})")
                continue

            result = data["result"][0]
            source_code_raw = result.get("SourceCode", "")

            if not source_code_raw:
                print(f"ℹ️ Empty SourceCode on chainid={chainid}, trying next...")
                continue

            temp_dir = f"temp_contracts/{address}"
            os.makedirs(temp_dir, exist_ok=True)
            file_list = []

            # Multi-file parsing logic {{...}}
            if source_code_raw.startswith("{{"):
                try:
                    # Etherscan V2 may require removing double braces
                    json_raw = source_code_raw[1:-1] if source_code_raw.startswith("{{") else source_code_raw
                    json_content = json.loads(json_raw)
                    sources = json_content.get("sources", json_content)

                    for rel_path, content_obj in sources.items():
                        full_path = os.path.join(temp_dir, rel_path)
                        os.makedirs(os.path.dirname(full_path), exist_ok=True)
                        with open(full_path, "w") as f:
                            f.write(content_obj.get("content", ""))
                        file_list.append(full_path)
                except Exception as e:
                    print(f"❌ JSON parsing error (chain {chainid}): {e}")
                    continue
            else:
                # Single-file case
                path = os.path.join(temp_dir, "Contract.sol")
                with open(path, "w") as f:
                    f.write(source_code_raw)
                file_list.append(path)

            print(f"✅ Phase 0 completed ({chainid}): {len(file_list)} file(s) fetched.")
            return file_list

    return []
        
def filter_diff_only(files: List[str], upstream: Optional[UpstreamRef]) -> List[str]:
    """Scope reduction: remove standard dependencies when upstream is known."""
    if not upstream:
        return files
    
    # Filtering logic: ignore items that look standard (lib, node_modules, etc.)
    # In an advanced version, compare hashes via repo URL
    filtered = [f for f in files if "node_modules" not in f and "lib/" not in f and "@openzeppelin" not in f]
    print(f"[Phase 0] Scope reduced: {len(files)} -> {len(filtered)} files (Delta focus)")
    return filtered

async def resolve_scope(path_or_address: str) -> ResolvedContract:
    upstream = None
    is_onchain = path_or_address.startswith("0x")

    if is_onchain:
        address = path_or_address.lower()
        files = await fetch_etherscan_source(address)
        upstream = KNOWN_UPSTREAMS_DB.get(address)
    else:
        # Local resolution
        files = []
        # Case 1: this is a single file
        if os.path.isfile(path_or_address):
            if path_or_address.endswith(".sol"):
                files.append(path_or_address)
        
        # Case 2: it is a directory
        elif os.path.isdir(path_or_address):
            for root, _, filenames in os.walk(path_or_address):
                for f in filenames:
                    if f.endswith(".sol"):
                        files.append(os.path.join(root, f))

        # Case 3: uvicorn server often has cwd = backend/ — relative to repo root
        if not files and not os.path.isabs(path_or_address):
            repo_root = Path(__file__).resolve().parents[2]
            cand = (repo_root / path_or_address).resolve()
            if cand.is_file() and cand.suffix == ".sol":
                files.append(str(cand))
            elif cand.is_dir():
                for root, _, filenames in os.walk(str(cand)):
                    for f in filenames:
                        if f.endswith(".sol"):
                            files.append(os.path.join(root, f))
        
        # Detect upstream from the first discovered file
        if files and not upstream:
            with open(files[0], 'r') as file:
                upstream = await detect_upstream_from_code(file.read())

    # Apply scope reduction
    files = filter_diff_only(files, upstream)

    return ResolvedContract(
        files=files,
        is_onchain=is_onchain,
        upstream=upstream,
        address=path_or_address if is_onchain else None
    )