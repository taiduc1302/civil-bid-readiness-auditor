"""Compare two verified archived review snapshots without re-auditing either source."""
from __future__ import annotations

from collections import Counter
from typing import Any, Callable

from archived_review import build_archived_review_session

FINDING_CHANGE_TYPES = (
    "UNCHANGED",
    "REVIEW_CHANGED",
    "EVIDENCE_CHANGED",
    "EVIDENCE_AND_REVIEW_CHANGED",
    "ADDED",
    "REMOVED",
)
REFERENCE_CHANGE_TYPES = ("UNCHANGED", "CHANGED", "ADDED", "REMOVED")
METADATA_CHANGE_TYPES = ("UNCHANGED", "CHANGED", "ADDED", "REMOVED")

_FINDING_EVIDENCE_FIELDS = ("severity", "message", "evidence", "recommended_action")
_REVIEW_FIELDS = ("status", "reason")
_REFERENCE_COMPARE_FIELDS = ("status", "reference_code", "reference_unit", "message")
_METADATA_FIELDS = ("filename", "revision", "size_bytes", "sha256", "authority_status")


def _finding_anchor(row: dict[str, Any]) -> tuple[str, int, str, str]:
    return (
        str(row.get("sheet", "")),
        int(row.get("row", 0)),
        str(row.get("rule_id", "")),
        str(row.get("field", "")),
    )


def _reference_anchor(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row.get("reference_type", "")),
        str(row.get("sheet", "")),
        str(row.get("source_row", "")),
        str(row.get("code", "")),
    )


def _unique_index(
    rows: list[dict[str, Any]],
    anchor: Callable[[dict[str, Any]], tuple[Any, ...]],
    label: str,
) -> dict[tuple[Any, ...], dict[str, Any]]:
    indexed: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        key = anchor(row)
        if key in indexed:
            raise ValueError(f"Review Delta cannot compare ambiguous {label}: duplicate anchor {key!r}.")
        indexed[key] = row
    return indexed


def _finding_state(session: dict[str, Any], row: dict[str, Any]) -> dict[str, str]:
    finding_id = int(row["id"])
    state = session.get("dispositions", {}).get(finding_id, {})
    return {
        "status": str(state.get("status", "")),
        "reason": str(state.get("reason", "")),
    }


def _changed_fields(before: dict[str, Any], after: dict[str, Any], fields: tuple[str, ...]) -> list[str]:
    return [field for field in fields if str(before.get(field, "")) != str(after.get(field, ""))]


def _finding_deltas(before: dict[str, Any], after: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    before_index = _unique_index(before["result"]["findings"], _finding_anchor, "finding anchors in the earlier snapshot")
    after_index = _unique_index(after["result"]["findings"], _finding_anchor, "finding anchors in the later snapshot")
    rows: list[dict[str, Any]] = []
    counts = Counter()
    for anchor in sorted(set(before_index) | set(after_index)):
        old = before_index.get(anchor)
        new = after_index.get(anchor)
        if old is None:
            change_type = "ADDED"
            old_review = None
            new_review = _finding_state(after, new)
            evidence_changed = list(_FINDING_EVIDENCE_FIELDS)
            review_changed = list(_REVIEW_FIELDS)
        elif new is None:
            change_type = "REMOVED"
            old_review = _finding_state(before, old)
            new_review = None
            evidence_changed = list(_FINDING_EVIDENCE_FIELDS)
            review_changed = list(_REVIEW_FIELDS)
        else:
            old_review = _finding_state(before, old)
            new_review = _finding_state(after, new)
            evidence_changed = _changed_fields(old, new, _FINDING_EVIDENCE_FIELDS)
            review_changed = _changed_fields(old_review, new_review, _REVIEW_FIELDS)
            if evidence_changed and review_changed:
                change_type = "EVIDENCE_AND_REVIEW_CHANGED"
            elif evidence_changed:
                change_type = "EVIDENCE_CHANGED"
            elif review_changed:
                change_type = "REVIEW_CHANGED"
            else:
                change_type = "UNCHANGED"
        counts[change_type] += 1
        rows.append({
            "change_type": change_type,
            "anchor": {
                "sheet": anchor[0],
                "row": anchor[1],
                "rule_id": anchor[2],
                "field": anchor[3],
            },
            "evidence_fields_changed": evidence_changed,
            "review_fields_changed": review_changed,
            "before": old,
            "after": new,
            "before_review": old_review,
            "after_review": new_review,
        })
    return rows, {key: counts.get(key, 0) for key in FINDING_CHANGE_TYPES}


def _reference_deltas(before: dict[str, Any], after: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    before_index = _unique_index(before.get("reference_results", []), _reference_anchor, "reference anchors in the earlier snapshot")
    after_index = _unique_index(after.get("reference_results", []), _reference_anchor, "reference anchors in the later snapshot")
    rows: list[dict[str, Any]] = []
    counts = Counter()
    for anchor in sorted(set(before_index) | set(after_index)):
        old = before_index.get(anchor)
        new = after_index.get(anchor)
        if old is None:
            change_type = "ADDED"
            fields_changed = list(_REFERENCE_COMPARE_FIELDS)
        elif new is None:
            change_type = "REMOVED"
            fields_changed = list(_REFERENCE_COMPARE_FIELDS)
        else:
            fields_changed = _changed_fields(old, new, _REFERENCE_COMPARE_FIELDS)
            change_type = "CHANGED" if fields_changed else "UNCHANGED"
        counts[change_type] += 1
        rows.append({
            "change_type": change_type,
            "anchor": {
                "reference_type": anchor[0],
                "sheet": anchor[1],
                "source_row": anchor[2],
                "code": anchor[3],
            },
            "fields_changed": fields_changed,
            "before": old,
            "after": new,
        })
    return rows, {key: counts.get(key, 0) for key in REFERENCE_CHANGE_TYPES}


def _metadata_index(session: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in session.get("reference_metadata", []) or []:
        role = str(item.get("role", "")).strip().casefold()
        if role not in ("activity", "resource"):
            raise ValueError("Review Delta found unsupported reference metadata role.")
        if role in result:
            raise ValueError(f"Review Delta found duplicate reference metadata for role {role}.")
        result[role] = dict(item)
    return result


def _metadata_deltas(before: dict[str, Any], after: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    old_index = _metadata_index(before)
    new_index = _metadata_index(after)
    rows: list[dict[str, Any]] = []
    counts = Counter()
    for role in sorted(set(old_index) | set(new_index)):
        old = old_index.get(role)
        new = new_index.get(role)
        if old is None:
            change_type = "ADDED"
            fields_changed = list(_METADATA_FIELDS)
        elif new is None:
            change_type = "REMOVED"
            fields_changed = list(_METADATA_FIELDS)
        else:
            fields_changed = _changed_fields(old, new, _METADATA_FIELDS)
            change_type = "CHANGED" if fields_changed else "UNCHANGED"
        counts[change_type] += 1
        rows.append({
            "change_type": change_type,
            "role": role,
            "fields_changed": fields_changed,
            "before": old,
            "after": new,
        })
    return rows, {key: counts.get(key, 0) for key in METADATA_CHANGE_TYPES}


def _lineage(session: dict[str, Any]) -> dict[str, Any]:
    origin = session.get("archived_snapshot_origin", {})
    return {
        "package_filename": str(origin.get("package_filename", "")),
        "package_sha256": str(origin.get("package_sha256", "")),
        "package_format": str(origin.get("package_format", "")),
        "package_version": int(origin.get("package_version", 0)),
        "integrity_version": int(origin.get("integrity_version", 0)),
        "source_session_mode": str(origin.get("source_session_mode", "")),
        "source_filename": str(session.get("filename", "")),
        "rows_reviewed": int(session.get("result", {}).get("rows_reviewed", 0)),
    }


def compare_review_packages(
    earlier_filename: str,
    earlier_data: bytes,
    later_filename: str,
    later_data: bytes,
) -> dict[str, Any]:
    """Compare two verified review snapshots and return evidence drift only."""
    earlier = build_archived_review_session(earlier_filename, earlier_data)
    later = build_archived_review_session(later_filename, later_data)
    finding_rows, finding_counts = _finding_deltas(earlier, later)
    reference_rows, reference_counts = _reference_deltas(earlier, later)
    metadata_rows, metadata_counts = _metadata_deltas(earlier, later)
    earlier_lineage = _lineage(earlier)
    later_lineage = _lineage(later)
    return {
        "comparison_format": "civil-estimate-review-delta",
        "comparison_version": 1,
        "earlier": earlier_lineage,
        "later": later_lineage,
        "same_source_filename": earlier_lineage["source_filename"] == later_lineage["source_filename"],
        "same_package_sha256": earlier_lineage["package_sha256"] == later_lineage["package_sha256"],
        "finding_counts": finding_counts,
        "finding_changes": finding_rows,
        "reference_counts": reference_counts,
        "reference_changes": reference_rows,
        "reference_metadata_counts": metadata_counts,
        "reference_metadata_changes": metadata_rows,
        "session_created": False,
        "re_audit_performed": False,
        "correctness_inferred": False,
        "readiness_inferred": False,
        "heavybid_import_validated": False,
    }
