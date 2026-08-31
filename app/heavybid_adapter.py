"""Controlled HeavyBid-style export adapter.

This module recognizes only explicitly supported flat resource-export headers and
maps them into the auditor's vendor-neutral canonical model. It does not access
HeavyBid databases, infer missing values, or validate company codebooks.
"""
from __future__ import annotations

from typing import Iterable


PROFILE_HEAVYBID_STYLE_RESOURCE_EXPORT = "heavybid_style_resource_export"

# Exact semantic candidates observed in common estimating exports. Matching is
# case-insensitive and whitespace-normalized, but never fuzzy.
HEAVYBID_STYLE_FIELDS: dict[str, tuple[str, ...]] = {
    "bid_item": ("Bid Item", "Bid Item No", "Biditem", "Biditem Code"),
    "activity": ("Activity", "Activity Code", "Activity ID"),
    "resource_type": ("Resource Type", "Resource Class", "Cost Type"),
    "resource_code": ("Resource Code", "Resource ID", "Resource No"),
    "description": ("Resource Description", "Description", "Item Description"),
    "quantity": ("Quantity", "Qty"),
    "unit": ("Unit", "UOM", "Unit of Measure"),
    "rate": ("Rate", "Unit Rate", "Unit Price"),
    "amount": ("Amount", "Total", "Extended Amount"),
    "category": ("Category", "Cost Category"),
    "crew_code": ("Crew Code", "Crew", "Crew ID"),
    "production_rate": ("Production Rate", "Prod Rate", "Prod. Rate"),
}

# Require hierarchy plus the four canonical audit fields before auto-selecting
# this profile. Operational Crew/Production fields are always optional and are
# mapped only when explicitly present; they never affect profile detection.
DETECTION_REQUIRED_FIELDS = (
    "bid_item",
    "activity",
    "resource_type",
    "description",
    "quantity",
    "unit",
    "rate",
)


def _norm(value: object) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def map_heavybid_style_headers(headers: Iterable[str]) -> dict[str, str]:
    """Map only explicitly supported headers; missing fields remain unmapped."""
    lookup = {_norm(header): str(header) for header in headers if str(header).strip()}
    mapped: dict[str, str] = {}
    for field, candidates in HEAVYBID_STYLE_FIELDS.items():
        for candidate in candidates:
            source = lookup.get(_norm(candidate))
            if source is not None:
                mapped[field] = source
                break
    return mapped


def detect_heavybid_style_export(headers: Iterable[str]) -> bool:
    """Return True only when the supported hierarchy/resource signature is clear."""
    mapped = map_heavybid_style_headers(headers)
    return all(field in mapped for field in DETECTION_REQUIRED_FIELDS)


def adapter_contract() -> dict[str, object]:
    """Machine-readable safety contract for tests and future integrations."""
    return {
        "profile": PROFILE_HEAVYBID_STYLE_RESOURCE_EXPORT,
        "direct_database_access": False,
        "fuzzy_header_matching": False,
        "infers_missing_values": False,
        "validates_company_codebook": False,
        "converts_units": False,
        "operational_fields_optional_explicit_only": True,
        "required_detection_fields": list(DETECTION_REQUIRED_FIELDS),
    }
