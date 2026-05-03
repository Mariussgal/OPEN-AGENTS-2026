"""
Audit pipeline metadata (id + label of 7 phases).

Intentionally minimal module — *zero heavy imports* — so clients
lightweight (CLI, frontend bridge, tests) can import it without triggering
chargement de Cognee, Slither, Anthropic, etc.

The `pipeline.streaming` module (server side) re-exports `PIPELINE_PHASES` for
back-compat.
"""

from __future__ import annotations


# Ordered list of the 7 audit pipeline phases.
# Format : (phase_id, human_label).
# - phase_id   : used in NDJSON events (`{"phase": "<id>", ...}`)
# - human_label: used by the CLI for the progress bar.
PIPELINE_PHASES: list[tuple[str, str]] = [
    ("resolve",     "Phase 0 · Resolve target"),
    ("inventory",   "Phase 1 · Inventory"),
    ("slither",     "Phase 2 · Slither static analysis"),
    ("triage",      "Phase 3 · Triage"),
    ("investigate", "Phase 4 · Adversarial agent"),
    ("anchor",      "Phase 5 · Onchain anchor"),
    ("report",      "Phase 6 · Report"),
]
