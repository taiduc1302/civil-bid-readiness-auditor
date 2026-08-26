"""Presentation-only filtering, sorting, and grouping for governed reference checks."""
from __future__ import annotations

from collections import OrderedDict
from typing import Any

from reference_metadata import metadata_by_role

REFERENCE_STATUS_FILTERS = ("Exceptions", "All", "NO_MATCH", "UNIT_MISMATCH", "NOT_CHECKED", "MATCH")
REFERENCE_TYPE_FILTERS = ("", "activity", "resource")
REFERENCE_SORT_OPTIONS = ("status", "source", "code", "type")
REFERENCE_GROUP_OPTIONS = ("", "status", "type")
_STATUS_RANK = {"NO_MATCH": 0, "UNIT_MISMATCH": 1, "NOT_CHECKED": 2, "MATCH": 3}
_TYPE_RANK = {"activity": 0, "resource": 1}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _source_row(item: dict[str, Any]) -> tuple[int, str]:
    raw = _text(item.get("source_row"))
    try:
        return int(raw), raw
    except ValueError:
        return 10**12, raw.casefold()


def filter_reference_results(
    results: list[dict[str, Any]],
    metadata: list[dict[str, Any]] | None = None,
    *,
    status: str = "Exceptions",
    reference_type: str = "",
    text: str = "",
) -> list[dict[str, Any]]:
    """Return a filtered copy without mutating checks or evidence metadata."""
    status = _text(status) or "Exceptions"
    if status not in REFERENCE_STATUS_FILTERS:
        status = "Exceptions"
    reference_type = _text(reference_type).casefold()
    if reference_type not in REFERENCE_TYPE_FILTERS:
        reference_type = ""
    text_key = _text(text).casefold()
    by_role = metadata_by_role(metadata)

    filtered: list[dict[str, Any]] = []
    for item in results:
        item_status = _text(item.get("status"))
        item_type = _text(item.get("reference_type")).casefold()
        if status == "Exceptions" and item_status == "MATCH":
            continue
        if status not in ("Exceptions", "All") and item_status != status:
            continue
        if reference_type and item_type != reference_type:
            continue
        if text_key:
            meta = by_role.get(item_type, {})
            haystack = " ".join(
                _text(item.get(field))
                for field in (
                    "sheet", "source_row", "reference_type", "status", "code",
                    "reference_code", "reference_unit", "message",
                )
            )
            haystack += " " + " ".join(
                _text(meta.get(field)) for field in ("filename", "revision", "sha256")
            )
            if text_key not in haystack.casefold():
                continue
        filtered.append(item)
    return filtered


def sort_reference_results(results: list[dict[str, Any]], sort_by: str = "status") -> list[dict[str, Any]]:
    """Return a deterministic sorted copy of reference checks."""
    sort_by = _text(sort_by)
    if sort_by not in REFERENCE_SORT_OPTIONS:
        sort_by = "status"

    def key(item: dict[str, Any]):
        status = _text(item.get("status"))
        ref_type = _text(item.get("reference_type")).casefold()
        sheet = _text(item.get("sheet")).casefold()
        row = _source_row(item)
        code = _text(item.get("code")).casefold()
        ref_code = _text(item.get("reference_code")).casefold()
        tie = (sheet, row, ref_type, code, ref_code, status)
        if sort_by == "source":
            return (sheet, row, _TYPE_RANK.get(ref_type, 99), code, status)
        if sort_by == "code":
            return (code, ref_code, sheet, row, _TYPE_RANK.get(ref_type, 99), status)
        if sort_by == "type":
            return (_TYPE_RANK.get(ref_type, 99), ref_type, sheet, row, code, status)
        return (_STATUS_RANK.get(status, 99),) + tie

    return sorted(list(results), key=key)


def group_reference_results(
    results: list[dict[str, Any]], group_by: str = ""
) -> list[tuple[str, list[dict[str, Any]]]]:
    """Group the current ordered view without reordering rows inside groups."""
    group_by = _text(group_by)
    if group_by not in REFERENCE_GROUP_OPTIONS or not group_by:
        return [("", list(results))]
    groups: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    for item in results:
        if group_by == "status":
            label = _text(item.get("status")) or "(no status)"
        else:
            label = _text(item.get("reference_type")) or "(no type)"
        groups.setdefault(label, []).append(item)
    return list(groups.items())
