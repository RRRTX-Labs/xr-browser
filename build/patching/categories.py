"""Patch-budget categories + caps, transcribed from Plan §1.2.

Single source of truth for the ≤150 upstream-touched budget and the
per-class caps. Imported by build/patching/apply.py (lint) and
build/farm/budget_meter.py (report). The manifest (xr-core/patches/
manifest.yaml) declares which category each patch belongs to; it does NOT
carry the caps — the caps are plan law and live here + in the contract
docs/contracts/patch-manifest-v1.md.
"""

# cap=None means "unlimited-ish (cheap)" per Plan §1.2 — still counts toward total.
PLAN_CAPS: dict[str, int | None] = {
    "branding": None,
    "hook_points": 45,
    "blink_seams": 25,
    "content_seams": 30,
    "network_seams": 20,
    "ui": 35,
    "extension_chokepoint": 2,
}

TOTAL_CAP = 150


def validate_category(name: str) -> list[str]:
    if name not in PLAN_CAPS:
        return [f"category {name!r} is not a Plan §1.2 patch class ({sorted(PLAN_CAPS)})"]
    return []
