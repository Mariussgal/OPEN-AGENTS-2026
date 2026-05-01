# User Type DeFi - Sample Audit Target

Ce dossier simule un "user type" qui veut auditer un petit protocole DeFi complet.

## Contenu

- `MockToken.sol`: token ERC20 minimal pour les tests.
- `YieldVault.sol`: vault de depots/retraits avec logique de shares.

## Lancer un audit

Depuis la racine du repo:

```bash
onchor-ai audit ./examples/user-type-defi
```

Ou fichier par fichier:

```bash
onchor-ai audit ./examples/user-type-defi/MockToken.sol
onchor-ai audit ./examples/user-type-defi/YieldVault.sol
```

