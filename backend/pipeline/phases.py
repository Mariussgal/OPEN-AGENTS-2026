"""
Métadonnées du pipeline d'audit (id + label des 7 phases).

Module volontairement minimaliste — *zéro import lourd* — pour que les clients
légers (CLI, frontend bridge, tests) puissent l'importer sans déclencher le
chargement de Cognee, Slither, Anthropic, etc.

Le module `pipeline.streaming` (côté serveur) ré-exporte `PIPELINE_PHASES` pour
back-compat.
"""

from __future__ import annotations


# Liste ordonnée des 7 phases du pipeline d'audit.
# Format : (phase_id, human_label).
# - phase_id   : utilisé dans les events NDJSON (`{"phase": "<id>", ...}`)
# - human_label: utilisé par le CLI pour la progress bar.
PIPELINE_PHASES: list[tuple[str, str]] = [
    ("resolve",     "Phase 0 · Resolve target"),
    ("inventory",   "Phase 1 · Inventory"),
    ("slither",     "Phase 2 · Slither static analysis"),
    ("triage",      "Phase 3 · Triage (claude-haiku)"),
    ("investigate", "Phase 4 · Adversarial agent (claude-sonnet)"),
    ("anchor",      "Phase 5 · Onchain anchor"),
    ("report",      "Phase 6 · Report"),
]
