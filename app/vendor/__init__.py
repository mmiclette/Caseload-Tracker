"""
Vendored modules copied byte-identical from other NeuroFlow codebases.

medication_registry.py is copied from bh-cds
(Manage_Additions/backend/cds_core/medication_registry.py) — the flat,
engine-independent medication catalog (display names, class, FDA dose
steps). Keep it byte-identical to the source so re-syncing is a plain copy;
put any cocm-registry-specific logic in app/services/medication_catalog.py,
never in the vendored file. bh-cds may eventually lift its per-engine
MED_KBs into one shared module — when that happens, re-vendor from the new
location rather than forking here.
"""
