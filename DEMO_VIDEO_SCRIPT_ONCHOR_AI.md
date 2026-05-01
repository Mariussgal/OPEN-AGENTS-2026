# 🎬 Script de démo vidéo — Onchor-ai · ETHGlobal Open Agents

**Durée totale estimée :** 4 minutes | **3 actes** | **1 speaker**

---

## AVANT DE MONTER SUR SCÈNE / DÉMARRER L'ENREGISTREMENT — checklist setup

- Terminal ouvert, fond noir, police 18px minimum, zoom 150%
- Dossier `~/demo/contracts/` prêt avec `SmartContract.sol` (V1) et `SmartContractV2.sol` (V2)
- Navigateur : 3 onglets pré-ouverts (Etherscan Sepolia, ENS app, `onchor-ai.vercel.app/history`)


---

## ACTE 0 — ONBOARDING

**⏱ 0:00 → 0:25**

**[ACTION : affiche le terminal vide, curseur qui clignote]**

**DIRE :**

Un développeur veut auditer son smart contract. Pas d'inscription SaaS, juste une ligne

**[ACTION : tape lentement, lisiblement]**

```bash
pip3 install onchor-ai
```

**DIRE :**

L'agent génère un wallet local. On le charge avec quelques USDC. Le paiement est 100% natif via x402. En 20 secondes, l'agent est prêt à auditer.

**[ACTION : cut rapide au montage sur la fin de l'install, puis tape :]**

```bash
onchor-ai init
```

First launch detected — initial setup required.
This wizard runs only once.

ℹ Skip at any time: ONCHOR_SKIP_ONBOARDING=1


╭──────────────────────────────────────────────────────────────────────────────╮
│  [1 / 1]  User Wallet                                                        │
│  Generate your wallet and fund USDC on Base Sepolia for x402 payments.       │
╰──────────────────────────────────────────────────────────────────────────────╯
╭───────────────────────────── Copy this address ──────────────────────────────╮
│                                                                              │
│  Your wallet address  (triple-click to copy)                                 │
│                                                                              │
│  0xB70A7849188b44041Bd8bE1968683f62117Ae17a                                  │
│                                                                              │
│  Use this address on the Circle faucet.                                      │
│                                                                              │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─────────────────────────── Fund wallet — 1 faucet ───────────────────────────╮
│                                                                              │
│  USDC Base Sepolia — min ~1 USDC — x402 payments                             │
│  https://faucet.circle.com                                                   │
│                                                                              │
╰──────────────────────────────────────────────────────────────────────────────╯

Once funded, press Enter to verify USDC: 

**[ACTION : on envoie des USDC sur l'adresse et on appuie sur enter]**
✔  USDC Base Sepolia — 2.0000 USDC  (min ~1 USDC)
✔ USDC balance confirmed ✓

✔ Setup user complete — files written:
  ./.env.user                 user wallet + payment vars
  ~/.onchor-ai/config.json    onchor-ai profile
╭──────────────────────────────────────────────────────────────────────────────╮
│                                                                              │
│                                                                              │
│                                      .:                                      │
│                                     ..::                                     │
│                                   ....:::                                    │
│                                  .....::::                                   │
│                                 ......:::::                                  │
│                                .......::::::                                 │
│                               ......::-::::::                                │
│                              ...::::::-----:::                               │
│                              :::::::::--------                               │
│                    .         .. ::::::----- ::         :                     │
│                    ....       .... :::-- ::::       ::::                     │
│                    ......      ......  :::::      ::::::                     │
│                    .........     .....::::      ::::::::                     │
│                    .......        ....:::        :::::::                     │
│                    ........       ....:::       ::::::::                     │
│                    :   .......    ....::::   :::::::   :                     │
│                          .............:::::::::::::                          │
│                           ............:::::::::::                            │
│                               ........::::::::                               │
│                                  .....::::                                   │
│                                     ..:                                      │
│                                      .                                       │
│               ____             __                     ___    ____            │
│              / __ \____  _____/ /_  ____  _____      /   |  /  _/            │
│             / / / / __ \/ ___/ __ \/ __ \/ ___/_____/ /| |  / /              │
│            / /_/ / / / / /__/ / / / /_/ / /  /_____/ ___ |_/ /               │
│            \____/_/ /_/\___/_/ /_/\____/_/        /_/  |_/___/               │
│                                                                              │
│           Solidity Security Copilot · Persistent Collective Memory           │
│                   ETHGlobal Open Agents 2026 · CNM Agency                    │
│                                                                              │
╰──────────────────────────────────────────────────────────────────────────────╯
──────────────────────────────── Initialisation ────────────────────────────────
✔ Projet initialisé — dossier .onchor/ créé.


---

## ACTE 1 — "LE CONTRAT PIÉGÉ"

**⏱ 0:25 → 2:25**

### Setup — 20 secondes

**[ACTION : ouvre `SmartContract.sol` dans le terminal ou l'éditeur. Scroll jusqu'à la fonction `claimTokens`. Highlight l'espace vide entre le `require` et le `token.transfer`.]**

**DIRE :**

Ce contrat d'Airdrop semble parfait, mais il manque une ligne : le développeur a oublié d'enregistrer le 'claim'. C'est une attaque de Signature Replay que l'analyse statique classique ne voit pas

**[ACTION : ferme l'éditeur, retour au terminal]**

### L'audit en live — 100 secondes

**[ACTION : tape la commande]**

```bash
onchor-ai audit ./contracts/SmartContract.sol
```
╭──────────────────────────────────────────────────────────────────────────────╮
│                                                                              │
│                                                                              │
│                                      .:                                      │
│                                     ..::                                     │
│                                   ....:::                                    │
│                                  .....::::                                   │
│                                 ......:::::                                  │
│                                .......::::::                                 │
│                               ......::-::::::                                │
│                              ...::::::-----:::                               │
│                              :::::::::--------                               │
│                    .         .. ::::::----- ::         :                     │
│                    ....       .... :::-- ::::       ::::                     │
│                    ......      ......  :::::      ::::::                     │
│                    .........     .....::::      ::::::::                     │
│                    .......        ....:::        :::::::                     │
│                    ........       ....:::       ::::::::                     │
│                    :   .......    ....::::   :::::::   :                     │
│                          .............:::::::::::::                          │
│                           ............:::::::::::                            │
│                               ........::::::::                               │
│                                  .....::::                                   │
│                                     ..:                                      │
│                                      .                                       │
│               ____             __                     ___    ____            │
│              / __ \____  _____/ /_  ____  _____      /   |  /  _/            │
│             / / / / __ \/ ___/ __ \/ __ \/ ___/_____/ /| |  / /              │
│            / /_/ / / / / /__/ / / / /_/ / /  /_____/ ___ |_/ /               │
│            \____/_/ /_/\___/_/ /_/\____/_/        /_/  |_/___/               │
│                                                                              │
│           Solidity Security Copilot · Persistent Collective Memory           │
│                   ETHGlobal Open Agents 2026 · CNM Agency                    │
│                                                                              │
╰──────────────────────────────────────────────────────────────────────────────╯
──────────────────── Audit · /Users/nohemmg/user-type-defi ─────────────────────
ℹ Mode : PAID
ℹ Solde disponible : 2.00 USDC
  ⟳  Récupération du prix...
  →  2 fichier(s) détecté(s) — Prix : 0.5 USDC
  Procéder au paiement x402 ? [y/N]: y

**[ACTION : on clique sur y]**
**DIRE :**
"On lance l'audit. Le paiement USDC est réglé instantanément avec x402 paiement"

⟳  Signature du paiement (EIP-3009)...
  ✓  Payload signé (EIP-712)
ℹ Pipeline démarré — voir progression ci-dessous.
  ✓  Payment settled  ·  0.50 USDC  ·  tx: 0x8d270de5a961…


**[ACTION : Phase 0 à 3s'affiche]**

  > Resolving target — file detection / fork analysis...
✓  Phase 0 · Resolve target  ·  2 file(s)  ·  no upstream fork
  > Structural parse · flagging delegatecall / unchecked / assembly...
 ✓  Phase 1 · Inventory  ·  2 file(s)  ·  0 known finding(s)  ·  0 dup(s)
  > Running 89 detectors...
✓  Phase 2 · Slither static analysis  ·  11 finding(s) · slither OK
  > Cost-gate triage...
✓  Phase 3 · Triage  ·  risk score: 7 / 10  ·  CAUTION

**DIRE :**
Onchor pose les bases en quatre temps : délimitation du scope pour exclure les forks connus, inventaire via la mémoire locale Cognee, puis analyse statique avec Slither. Ces signaux bruts génèrent un score de risque qui déclenche l'IA. On passe d'un simple scan à une vraie investigation ciblée

**[ACTION : Phase 4-5, Utilisation 0G / KeeperHub c'est le moment clé]**

 > Spawning adversarial agent (7 tools)...
  > Adversarial agent still running (#1)…
  > Adversarial agent still running (#2)…
  > Adversarial agent still running (#3)…
  > Adversarial agent still running (#4)…
  > Adversarial agent still running (#5)…
  > Adversarial agent still running (#6)…
  > Adversarial agent still running (#7)…
  > Adversarial agent still running (#8)…
  > Adversarial agent still running (#9)…
  > Adversarial agent still running (#10)…
  > Adversarial agent still running (#11)…
  > Adversarial agent still running (#12)…
  ✓  Phase 4 · Adversarial agent  ·  1 finding(s)  ·  10 turn(s)
  > Anchoring confirmed findings on Sepolia...
  ✓  Phase 5 · Onchain anchor  ·  1 / 1 anchored onchain

**DIRE :**

"Là, on entre dans la Phase 4, le cœur d’Onchor.
L’agent adversarial ne fait pas un simple scan : il raisonne en plusieurs tours, lit le code ciblé, teste des hypothèses, et interroge la mémoire collective — les patterns stockés sur 0G Storage - pour confirmer un scénario d’attaque.
À la fin, il produit un finding justifié, avec un niveau de confiance, et ici il confirme une vulnérabilité en x tours.
Le pattern est persisté sur 0G puis ancré onchain via KeeperHub sur Sepolia, pour obtenir une trace vérifiable et immuable.

**[ACTION : Phase 6 s'affiche dans le terminal]**

 > Building enriched report + ENS certificate check...
  ✓  Phase 6 · Report  ·  verdict: FINDINGS_FOUND  ·  risk score: 8.0 / 10
  Pipeline complete ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% · 0:04:44
✔ Audit terminé.


Détails des findings critiques :
F-001 · Vault Inflation Attack: First Depositor Can Steal Funds via Share Price Manipulation
Description : Attacker deposits 1 wei for 1 share, donates large amount to inflate assetsBefore, causing victim's deposit to round down to minimal shares due to (amount  totalShares) / assetsBefore, division allowi 
Tx onchain : https://sepolia.etherscan.io/tx/0xa9d52225250e609c3c7ff6d5330391ebd9203cc5cbb7c360dbf569a1e5173a21 

Preuves onchain 
Anchor Registry  https://sepolia.etherscan.io/address/0x4DC06573aa7b214645f649E4b9412Fe5aEd775F
Network (anchor)  Ethereum Sepolia
Network (payment)  Base Sepolia                                            
Anchor #1 (F-001)  https://sepolia.etherscan.io/tx/0xa9d52225250e609c3c7ff6d5330391ebd9203cc5cbb7c360dbf569a1e5173a21
Payment USDC  https://sepolia.basescan.org/tx/0x8d270de5a961b470d8d333dc438cec3e7e1f6653e22b7d46572bd9363dca6d21

**DIRE :**

On obtient un rapport structuré directement dans le terminal. L'outil détaille l'attaque, fournit un exemple de correctif pour le développeur, et les preuves onchain.

**[ACTION : Tu scrolles brièvement sur le terminal pour montrer le rapport JSON brut, puis tu t'arrêtes sur le prompt Contribuer ? [y/N]]**

Contribution mémoire collective ──────────────────────────────────────────────────────────────────────────────────────
ℹ 1 vulnérabilité(s) identifiée(s). Partager ces patterns ANONYMES à la mémoire collective ?
ℹ Récompense : 0.05 USDC par pattern validé (max 3).
Contribuer ? [y/N]: y
**[ACTION : cliquer sur y]**
ℹ Envoi de la récompense (0.05 USDC) sur Base Sepolia…
✔ 1 pattern(s) payé(s) on-chain.
Preuves contribution 0G ──────────────────────────────────────────────────────────────────────────────────────────
ℹ [1] 0G tx: https://chainscan-galileo.0g.ai/tx/0x4476fa116d3c59d8b74c6b7703b7762aa8a61c1ab8954147f6a0e2b18cdccaa4
ℹ [1] root: 0x6c22d2277c4260875d4818bfeea9fed72ce99d1ca8b8f97f60fca3ee957d9cda

**DIRE :**
L'outil nous propose d'enrichir la mémoire collecive. En acceptant, le pattern d'attaque que nous venons de découvrir est uploadé sur le réseau 0G Storage. En échange de cet enrichissement de la mémoire collective, notre wallet reçoit instantanément une récompense de quelques USDC.








## ACTE 2 — "LE CONTRAT CERTIFIÉ"

**⏱ 2:25 → 3:50**

### Fix + re-audit — 60 secondes

**[ACTION : retour éditeur. Montre `SmartContractV2.sol`. Highlight la ligne ajoutée : `hasClaimed[msg.sender] = true;`]**

**DIRE :**

"Le développeur corrige. Il ajoute simplement la ligne manquante pour verrouiller l'état avant le transfert. Il re-soumet."

**[ACTION : tape dans le terminal]**

```bash
onchor audit ./contracts/SmartContractV2.sol
```

**[ACTION : laisse défiler les phases 0-3 en accéléré au montage. Arrêt sur la Phase 4]**

```text
> Pre-screening patterns...
  No CRITICAL pattern detected.
> Spawning adversarial agent (Sonnet · 10 turns)...
  [Turn 1/10]  → tool: read_contract
  [Turn 2/10]  → tool: query_memory
  ...
  [Turn 10/10] → no finding confirmed
✓  Phase 4 · Agent  ·  0 finding(s)
```

**DIRE :**

"L'agent scanne à nouveau le contrat. Le correctif est en place, l'attaque est impossible. Zéro finding confirmé."

**[ACTION : Phase 6 s'affiche]**

```text
✔  Verdict : CERTIFIED  ·  risk score: 1.5/10
🏅  contract-6994a7-2d4e.certified.onchor-ai.eth  ← ENS minté
```

**DIRE :**

"Verdict : CERTIFIED. Et là — automatiquement — un sous-domaine ENS est minté pour le contrat."

### Le certificat ENS — 20 secondes

**[ACTION : ouvre l'onglet ENS pré-chargé — `contract-6994a7-2d4e.certified.onchor-ai.eth`]**

**DIRE :**

"Ce nom de domaine appartient à ce contrat précis. N'importe quel protocole DeFi ou investisseur peut résoudre ce nom et trouver le hash du rapport d'audit. C'est un passeport onchain, vérifiable sans intermédiaire."

### La mémoire collective + récompense — 25 secondes

**[ACTION : retour terminal — montre les dernières lignes]**

```text
[0G] Pattern uploaded: Signature Replay / State Update Missing
[0G] Manifest re-uploadé — 47 patterns
✔  3 pattern(s) payé(s) onchain
    TX: 95dc3cc9...
    Nouveau solde : 10.65 USDC
```

**DIRE :**

"Pendant ce temps, le pattern de faille qu'on a trouvé tout à l'heure rejoint la mémoire collective décentralisée sur 0G Storage. Et le contributeur est récompensé en USDC directement sur sa wallet."

"Onchor-ai apprend à chaque audit. Plus il y a d'audits, plus la détection est rapide et l'écosystème sécurisé."

---

## CLÔTURE

**⏱ 3:50 → 4:00**

**[ACTION : revient sur le terminal global, tous les verdicts et lignes USDC bien visibles]**

**DIRE :**

"Paiement USDC natif via x402. Preuves ancrées sur Ethereum. Certificat ENS vérifiable. Mémoire décentralisée sur 0G. Onchor n'est pas juste un wrapper LLM, c'est un protocole d'audit complet."

"Pip install onchor-ai. Vous pouvez l'essayer dès maintenant."

**[ACTION : Cut au noir.]**

---

## ANNEXE — QUESTIONS JURY ANTICIPÉES (Pour la session Q&A)

### "Quelle est la précision du LLM — faux positifs ?"

"Le pipeline est conçu pour que le LLM ne confirme que ce qu'il peut justifier avec une trace d'exécution. Slither + triage filtrent le bruit en amont. Le fast-path regex a zéro faux positif sur les patterns connus — il ne fait que pré-screener, la confirmation finale avec la logique métier reste au LLM."

### "Pourquoi pas juste utiliser Slither ?"

"Slither est excellent pour la syntaxe, mais il ne comprend pas la logique métier. La faille de 'Signature Replay' qu'on vient de montrer passe souvent sous le radar d'une simple analyse statique car les transferts semblent légitimes. Notre agent adversarial, lui, simule le chemin d'exécution comme un attaquant qui chercherait à exploiter l'état du contrat."

### "Qu'est-ce qui est vraiment décentralisé dans l'architecture ?"

"Les preuves de findings (Ethereum Sepolia), les patterns de mémoire (0G Storage) et les certificats (ENS) sont décentralisés. Le pipeline d'exécution, lui, tourne en local sur la machine du dev — il n'y a pas de serveur centralisé Onchor qui voit le code source avant le déploiement."

### "Le coût $0.04 est-il réaliste en production ?"

"Sur testnet oui. En mainnet, les tokens LLM coûtent la même chose, le seul delta sera sur le gas d'ancrage Ethereum (qu'on peut batcher ou passer sur L2). L'économie du modèle tient dès que notre système de fast-path permet d'éviter un appel lourd à Claude Sonnet — ce qui arrive pour la majorité des patterns déjà indexés dans la mémoire."

