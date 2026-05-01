### Hackathon — ETHGlobal Open Agents 2026

---

# ONCHOR.AI

**Onchor.ai** is a Solidity security copilot with **persistent collective memory**: **Slither** for a fixed static baseline, **0G** for decentralized pattern storage that grows with audits, **Cognee** for local graph ingest + semantic **recall** fed into the **LLM** (alongside 0G collective queries), plus **KeeperHub** anchoring and **ENS** certification.

---

### 1. 0G (decentralized storage)

- **Pattern payloads on Galileo:** CONFIRMED / LIKELY findings are serialized (title, reason, severity, file, line, etc.) and uploaded through the `0g/` Node helpers; the pipeline records a **`rootHash`** used as the immutable content pointer against **0G Galileo**.
- **Wallet / gas:** Galileo testnet for storage operations.


---

### 2. KeeperHub

- **MPC-backed execution:** High-confidence findings call KeeperHub's **Direct Execution** API (`POST https://app.keeperhub.com/api/execute/contract-call`) to invoke `AnchorRegistry.anchor(patternHash, rootHash0G)` on Ethereum Sepolia without putting your user key in the hot path for that transaction.
- **Proof:** Responses expose `transactionHash` / `executionId`; the backend can resolve the on-chain tx via Etherscan for display and ENS tooling. See `backend/keeper/hub_anchor.py` and `backend/pipeline/phase5_anchor.py`.

---

### 3. ENS — identity & audit ledger

- **Certified subtree:** Parent name defaults to `certified.onchor-ai.eth`; scripts mint or update subnames and resolver **text** records (verdict, counts, tx proof, report hash, audit date) so wallets and explorers can read a tamper-evident audit summary on-chain.
- **Flow:** Off-chain report hash and KeeperHub tx proof can be written to ENS text keys after an anchor succeeds, linking **0G root**, **on-chain anchor**, and **human-readable ENS** in one story.

---

### 4. Collective memory

Onchor combines a **fixed static baseline** with a **decentralized memory** that **feeds itself** over time — the “open agent” idea: every audit can strengthen what the next one knows.

- **Slither (fixed layer):** **Slither** brings a **stable, built-in rule set** of vulnerability detectors. It always runs the same static-analysis corpus on your code and yields a structured list of candidates before triage and LLM investigation — think of it as the **fixed reference** layer.
- **0G (collective layer):** **0G** on **Galileo** is our **shared / collective memory**: verified pattern payloads (hashed content) sit on the network and accumulate as audits run — especially when findings are **anchored** (and when users opt in to contribute patterns).
- **Cognee (local graph + recall):** Vulnerable snippets are **sanitized** (`memory/privacy_guard.py`), flattened to **structured text** (type / severity / description), then **`cognee.add` + `cognee.cognify()`** build Cognee’s graph under **`~/.onchor-ai/memory`**. **Phase 1** runs **`cognee.recall`** and turns hits into **`known_findings` dicts** for dedup / triage. **Phase 4** **`tool_query_memory`** combines **Cognee recall** (local) and **`query_collective_memory`** (**0G** manifest) so the LLM sees both. So: Cognee is **not** “only JSON filing” — it’s a **real local store + graph pipeline**; **cross-user, content-addressed blobs** stay centered on **0G** (`memory/collective_0g.py`) plus anchoring/contributions.
- **Paid path:** In the default **pip-install** flow, audits are **paid via x402**, which runs the full pipeline against that memory stack.
- **Opt-in contribution:** At the **end** of a paid audit, the CLI asks if you want to contribute **anonymized** patterns to the shared memory. If you accept, you get **0.05 USDC per finding** on **Base Sepolia**, for **up to three findings** per opt-in.

---

## Demo

- **Video:** 
---

## System architecture

```mermaid
flowchart LR
    subgraph Client
        CLI["onchor-ai CLI"]
        FE["Next.js frontend"]
    end

    subgraph Backend["Python backend"]
        API["FastAPI server"]
        Pipe["Audit pipeline\nSlither + LLM"]
        Cognee["Cognee\nlocal graph + recall"]
    end

    subgraph Chain["Ethereum Sepolia"]
        AR["AnchorRegistry"]
    end

    G["0G\n(Galileo)"]
    KH["KeeperHub\nDirect Execution"]
    ENSn["ENS\nRegistry + Resolver"]

    CLI --> API
    FE --> API
    API --> Pipe
    Pipe <--> Cognee
    Pipe --> G
    Pipe --> KH
    KH --> AR
    Pipe -.->|"optional cert texts"| ENSn
```

---

## Getting started

**Requirements:** Python 3.10+.

1. **Install the CLI**

   ```bash
   pip install onchor-ai
   ```

 A one-time wizard creates a wallet. Your private key is written to ./.env.user — back it up and never commit that file. 




2. **Fund (before the first run)**  
   Get **USDC on Base Sepolia** so you can fund the wallet the wizard will create — e.g. [Circle faucet](https://faucet.circle.com).  then press Enter so the CLI can check the balance.
3. **Run**  

   ```bash
   onchor-ai audit <target>
   ```

   **What you can pass as `<target>`**

   - **Directory** — e.g. `onchor-ai audit .` audits the current project; **all `*.sol` files under that folder are collected recursively** (subfolders included).
   - **Single Solidity file** — path to one `.sol`.
   - **On-chain address** — `onchor-ai audit 0x…` for a contract **verified on Etherscan** (including **Ethereum mainnet**): the API pulls verified source via **Etherscan**.

---
