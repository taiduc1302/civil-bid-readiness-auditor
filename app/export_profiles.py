"""Controlled header profiles for known civil estimate export shapes.

Profiles only map source columns into the auditor's canonical fields. They do not
infer quantities, rates, units, resource types, or codebook values.
"""
from __future__ import annotations

from typing import Iterable


PROFILE_STRUCTURED_CIVIL = "structured_civil"

EXPORT_PROFILES: dict[str, dict[str, tuple[str, ...]]] = {
    PROFILE_STRUCTURED_CIVIL: {
        "description": ("Description", "Resource Description", "Item Description"),
        "quantity": ("Quantity", "Qty"),
        "unit": ("Unit", "UOM", "Unit of Measure"),
        "rate": ("Rate", "Unit Rate", "Unit Price"),
        "amount": ("Amount", "Total", "Extended Amount"),
        "category": ("Category", "Cost Category"),
        "bid_item": ("Bid Item No", "Bid Item Number", "Bid Item Code"),
        "activity": ("Activity Code", "Activity", "Activity ID"),
        "resource_type": ("Resource Type", "Resource Class", "Cost Type"),
        "resource_code": ("Resource Code", "Resource ID", "Resource No"),
    }
}


def mapping_for_profile(profile_name: str, headers: Iterable[str]) -> dict[str, str]:
    """Return deterministic canonical-to-source mappings for a named profile.

    Matching is case-insensitive and whitespace-normalized. Unknown or missing
    columns are left unmapped rather than guessed.
    """
    profile = EXPORT_PROFILES.get(profile_name)
    if profile is None:
        raise ValueError(f"Unknown export profile: {profile_name}")

    lookup = {" ".join(str(header).strip().casefold().split()): str(header) for header in headers if str(header).strip()}
    mapped: dict[str, str] = {}
    for field, candidates in profile.items():
        for candidate in candidates:
            key = " ".join(candidate.strip().casefold().split())
            if key in lookup:
                mapped[field] = lookup[key]
                break
    return mapped
