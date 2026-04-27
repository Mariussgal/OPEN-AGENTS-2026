import os
import json
import httpx
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

# Base de données d'upstreams avec métadonnées pour le futur diff
KNOWN_UPSTREAMS_DB = {
    "0x1f98431c8ad98523631ae4a59f267346ea31f984": UpstreamRef("Uniswap V3", "https://github.com/Uniswap/v3-core", "v1.0.0"),
    "0x49ca165bd6aee88825f59c557bc52a685e0594b5": UpstreamRef("Euler Vault", "https://github.com/euler-xyz/euler-vault", "v1.0")
}

async def detect_upstream_from_code(content: str) -> Optional[UpstreamRef]:
    """Détecte l'upstream en scannant les imports dans le code local."""
    if "IUniswapV2Router" in content or "UniswapV2" in content:
        return UpstreamRef("Uniswap V2 Fork", "https://github.com/Uniswap/v2-core", "unknown")
    if "@openzeppelin/contracts" in content:
        return UpstreamRef("OpenZeppelin Standard", "https://github.com/OpenZeppelin/openzeppelin-contracts", "latest")
    return None

async def fetch_etherscan_source(address: str) -> List[str]:
    api_key = os.getenv("ETHERSCAN_API_KEY")
    
    # URL API V2 d'Etherscan (Nouvelle norme)
    # On précise la chainid pour Sepolia
    url = f"https://api.etherscan.io/v2/api?chainid=11155111&module=contract&action=getsourcecode&address={address}&apikey={api_key}"
    
    print(f"[Phase 0] Appel Etherscan V2 pour {address}...")
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        data = response.json()
        
        # Sur l'API V2, le succès se vérifie toujours sur "status" == "1"
        if data.get("status") != "1":
            print(f"❌ Erreur Etherscan V2: {data.get('result')}")
            return []

        result = data["result"][0]
        source_code_raw = result.get("SourceCode", "")
        
        if not source_code_raw:
            print("❌ SourceCode vide renvoyé par Etherscan.")
            return []

        temp_dir = f"temp_contracts/{address}"
        os.makedirs(temp_dir, exist_ok=True)
        file_list = []

        # Logique de parsing multi-fichiers {{...}}
        if source_code_raw.startswith("{{"):
            try:
                # Etherscan V2 peut nécessiter d'enlever les doubles accolades
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
                print(f"❌ Erreur parsing JSON: {e}")
        else:
            # Cas fichier unique
            path = os.path.join(temp_dir, "Contract.sol")
            with open(path, "w") as f:
                f.write(source_code_raw)
            file_list.append(path)
            
        print(f"✅ Phase 0 terminée : {len(file_list)} fichiers récupérés.")
        return file_list
        
def filter_diff_only(files: List[str], upstream: Optional[UpstreamRef]) -> List[str]:
    """Réduction du scope : élimine les dépendances standards si un upstream est connu."""
    if not upstream:
        return files
    
    # Logique de filtrage : on ignore ce qui ressemble à du standard (lib, node_modules, etc.)
    # Dans une version avancée, on comparerait les hashes via l'URL du repo
    filtered = [f for f in files if "node_modules" not in f and "lib/" not in f and "@openzeppelin" not in f]
    print(f"[Phase 0] Scope réduit : {len(files)} -> {len(filtered)} fichiers (Focus sur le Delta)")
    return filtered

async def resolve_scope(path_or_address: str) -> ResolvedContract:
    upstream = None
    is_onchain = path_or_address.startswith("0x")

    if is_onchain:
        address = path_or_address.lower()
        files = await fetch_etherscan_source(address)
        upstream = KNOWN_UPSTREAMS_DB.get(address)
    else:
        # Résolution locale
        files = []
        # Cas 1 : C'est un fichier unique
        if os.path.isfile(path_or_address):
            if path_or_address.endswith(".sol"):
                files.append(path_or_address)
        
        # Cas 2 : C'est un répertoire
        elif os.path.isdir(path_or_address):
            for root, _, filenames in os.walk(path_or_address):
                for f in filenames:
                    if f.endswith(".sol"):
                        files.append(os.path.join(root, f))
        
        # Détection de l'upstream sur le premier fichier trouvé
        if files and not upstream:
            with open(files[0], 'r') as file:
                upstream = await detect_upstream_from_code(file.read())

    # Application de la réduction de scope
    files = filter_diff_only(files, upstream)

    return ResolvedContract(
        files=files,
        is_onchain=is_onchain,
        upstream=upstream,
        address=path_or_address if is_onchain else None
    )