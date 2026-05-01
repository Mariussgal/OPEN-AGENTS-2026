### Hackathon — ETHGlobal Open Agents 2026

---

# ONCHOR.AI

**Onchor.ai** is a Solidity security copilot with **persistent collective memory**: **Slither** provides a fixed static-analysis baseline, **0G** holds the decentralized pattern store that **self-grows** with each audit, and the stack adds LLM investigation, optional **Cognee** recall, **KeeperHub** anchoring, and **ENS** certification.

---

### 1. 0G (decentralized storage)

- **Pattern payloads on Galileo:** CONFIRMED / LIKELY findings are serialized (title, reason, severity, file, line, etc.) and uploaded through the `0g/` Node helpers; the pipeline records a **`rootHash`** used as the immutable content pointer.
- **Modes:** `OG_STORAGE_MODE` supports `live` (real 0G testnet), `merkle` (root only), and `mock` (local files under `backend/storage/.zero_g_mock/`). See `backend/storage/zero_g_client.py`.
- **Wallet / gas:** Galileo testnet for storage operations


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
- **0G (collective layer):** **0G storage** is our **shared / collective memory**: verified pattern payloads (hashed content) live on the network and accumulate as audits run — especially when findings are **anchored** (and when users opt in to contribute patterns). The store **replenishes itself** from the pipeline instead of staying a closed file.
- **Cognee (in-flight recall):** During an audit, **Cognee** supports semantic **recall** over a knowledge graph so the agent can connect Slither output and prior context; durable, cross-user sharing of pattern blobs remains centered on **0G** + anchoring.
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
        Cognee["Cognee\nknowledge graph"]
    end

    subgraph Chain["Ethereum Sepolia"]
        AR["AnchorRegistry"]
    end

    G["0G Storage\n(Galileo)"]
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
   - **On-chain address** — `onchor-ai audit 0x…` for a contract **verified on Etherscan** (including **Ethereum mainnet**): the API pulls verified source via **Etherscan** (set **`ETHERSCAN_CHAIN_ID`** on the server, e.g. `1` for mainnet, `11155111` for Sepolia).

---

*Built for ETHGlobal Open Agents 2026.*
