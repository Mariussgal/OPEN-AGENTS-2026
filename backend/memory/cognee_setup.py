import os
from pathlib import Path

from dotenv import load_dotenv

# 1. Load .env first
load_dotenv()

# 2. Resolve absolute paths (avoid ambiguous paths + SQLite "unable to open database file")
_GLOBAL_MEMORY = Path(os.path.expanduser("~/.onchor-ai/memory")).resolve()
COGNEE_SYSTEM_DIR = str(_GLOBAL_MEMORY / ".cognee_system")
COGNEE_DATA_DIR = str(_GLOBAL_MEMORY / ".cognee_data")
COGNEE_CACHE_DIR = str(_GLOBAL_MEMORY / ".cognee_cache")
_DATABASES_DIR = str(Path(COGNEE_SYSTEM_DIR) / "databases")

# 3. Create user directories before any Cognee import (SQLite + WAL / graph / cache)
for _d in (
    _GLOBAL_MEMORY,
    Path(COGNEE_SYSTEM_DIR),
    Path(COGNEE_DATA_DIR),
    Path(COGNEE_CACHE_DIR),
    Path(_DATABASES_DIR),
):
    _d.mkdir(parents=True, exist_ok=True)

# 4. Cognee 1.x: BaseConfig is frozen on first ``get_base_config()`` during ``import cognee``.
#    COGNEE_* variables are not read by pydantic-settings; use SYSTEM_ROOT_DIRECTORY /
#    DATA_ROOT_DIRECTORY / CACHE_ROOT_DIRECTORY so SQLite does not point to site-packages
#    (souvent non inscriptible → OperationalError).
os.environ["SYSTEM_ROOT_DIRECTORY"] = COGNEE_SYSTEM_DIR
os.environ["DATA_ROOT_DIRECTORY"] = COGNEE_DATA_DIR
os.environ["CACHE_ROOT_DIRECTORY"] = COGNEE_CACHE_DIR
# Compat : autres modules / docs internes
os.environ["COGNEE_SYSTEM_ROOT_DIRECTORY"] = COGNEE_SYSTEM_DIR
os.environ["COGNEE_DATA_ROOT_DIRECTORY"] = COGNEE_DATA_DIR
os.environ["COGNEE_SKIP_CONNECTION_TEST"] = "true"
os.environ["MOCK_EMBEDDING"] = "true"

# 5. IMPORT COGNEE HERE (after makedirs + env)
import cognee

# Cascade explicite graphe / LanceDB sous databases/
cognee.config.system_root_directory(COGNEE_SYSTEM_DIR)
cognee.config.data_root_directory(COGNEE_DATA_DIR)

# If a SQLAlchemy engine was cached with a wrong path (early import), clear it.
try:
    from cognee.infrastructure.databases.relational.create_relational_engine import (
        create_relational_engine,
    )

    create_relational_engine.cache_clear()
except Exception:
    pass

# Import security and normalization modules
from memory.privacy_guard import sanitize_finding_for_memory
from memory.normalizer import normalize_snippet


async def _ensure_cognee_db_ready() -> None:
    """
    Cognee 1.x: ``recall`` / ``search`` require relational tables + a default user.
    Sans cet appel sur une install neuve → SearchPreconditionError (422).
    """
    try:
        from cognee.infrastructure.databases.relational import create_db_and_tables
        from cognee.modules.users.methods import get_default_user

        await create_db_and_tables()
        await get_default_user()
    except Exception as e:
        print(f"⚠️  [Cognee] DB init / default user: {e}")


async def setup_cognee():
    """Initialize Cognee with global memory."""

    await _ensure_cognee_db_ready()

    api_key = os.getenv("LLM_API_KEY")
    if not api_key:
        print("❌ ERROR: LLM_API_KEY is missing in .env")
        return False

    cognee.config.set_llm_provider("openai")
    cognee.config.set_llm_model("gpt-4o-mini")

    print("✅ Cognee engine initialized (Global Memory).")
    print(f"   System DB : {COGNEE_SYSTEM_DIR}")
    print(f"   Data Dir  : {COGNEE_DATA_DIR}")
    print(f"   Cache     : {COGNEE_CACHE_DIR}")
    return True


async def add_finding_to_memory(finding: dict, contract_name: str):
    """Store vulnerability safely in the graph."""

    safe_finding = sanitize_finding_for_memory(finding)
    safe_desc = normalize_snippet(safe_finding.get("description", ""))

    text_data = (
        f"Vulnerability Report for {contract_name}.\n"
        f"Type: {safe_finding.get('check', 'unknown')}.\n"
        f"Severity: {safe_finding.get('impact', 'unknown')}.\n"
        f"Description: {safe_desc}\n"
    )

    try:
        await cognee.add(text_data)
        await cognee.cognify()
        print(f"🧠 Global memory graph updated: {safe_finding.get('check')} for {contract_name}")
    except Exception as e:
        print(f"❌ Error while adding to memory: {e}")


async def load_known_findings(scope):
    """Search known vulnerabilities in global Cognee memory."""
    try:
        results = await cognee.search(f"findings for {scope.name}")
        return results if results else []
    except Exception as e:
        print(f"⚠️ Memory search error: {e}")
        return []
