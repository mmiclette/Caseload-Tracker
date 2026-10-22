"""
Medication catalog service.

The thin cocm-registry wrapper over the vendored bh-cds medication
registry (app/vendor/medication_registry.py — see app/vendor/__init__.py
for the vendoring rules). This registry needs a med picker — start typing
a name, pick the medication, pick one of its real FDA dose strengths —
not bh-cds's CDS engine logic (roles, coverage, warnings), so only the
flat catalog is vendored and this module exposes exactly what the picker
and the Medication entity need: search by name and key lookup.

Every entry in the vendored catalog is a behavioral-health medication by
construction (it's the med KB for the bh-cds psychiatric decision tools),
which is what lets Medication.medication_key double as the "is this a
psychotropic?" signal for the AIMS caseload column — see
app/models/medication.py.
"""

from dataclasses import dataclass

from app.vendor.medication_registry import MEDICATIONS, get_dose_steps


@dataclass(frozen=True)
class CatalogEntry:
    key: str
    display: str
    med_class: str
    doses: list[str]  # patient-facing dose labels, e.g. ["25 mg", "50 mg"]


def _entry(key: str) -> CatalogEntry:
    med = MEDICATIONS[key]
    return CatalogEntry(
        key=key,
        display=med["display"],
        med_class=med["class"],
        doses=get_dose_steps(key),
    )


def get_catalog_entry(key: str) -> CatalogEntry | None:
    """The catalog entry for a medication key, or None if the key is unknown."""
    if key not in MEDICATIONS:
        return None
    return _entry(key)


def search_catalog(query: str = "", limit: int = 20) -> list[CatalogEntry]:
    """
    Case-insensitive substring search over key and display name ("sert"
    matches "Sertraline (Zoloft)"; "zol" matches both Zoloft and
    Vilazodone). An empty query returns the full catalog alphabetically —
    the picker's initial dropdown state.
    """
    needle = query.strip().lower()
    matches = [
        _entry(key)
        for key, med in MEDICATIONS.items()
        if not needle or needle in key.lower() or needle in med["display"].lower()
    ]
    matches.sort(key=lambda e: e.display)
    return matches[:limit]
