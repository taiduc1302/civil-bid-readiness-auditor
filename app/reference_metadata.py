"""Evidence metadata for explicitly supplied governed reference inputs."""
from __future__ import annotations

import csv
import hashlib
import io
from typing import Any

REFERENCE_ROLES = ("activity", "resource")


def build_reference_metadata(role: str, filename: str, data: bytes, revision: str = "") -> dict[str, Any]:
    role = str(role or "").strip().casefold()
    if role not in REFERENCE_ROLES:
        raise ValueError(f"Unsupported reference role: {role}")
    filename = str(filename or "").strip()
    if not filename:
        raise ValueError("Reference filename is required.")
    revision = str(revision or "").strip()
    if len(revision) > 200:
        raise ValueError("Reference revision/label must be 200 characters or fewer.")
    payload = bytes(data)
    return {
        "role": role,
        "filename": filename,
        "revision": revision,
        "size_bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "authority_status": "NOT_ESTABLISHED_BY_APP",
    }


def metadata_by_role(metadata: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in metadata or []:
        role = str(item.get("role", "")).strip().casefold()
        if role in REFERENCE_ROLES:
            result[role] = item
    return result


def reference_review_csv(reference_results: list[dict[str, Any]], metadata: list[dict[str, Any]] | None = None) -> bytes:
    """Export reference checks with the evidence metadata used for each role."""
    fields = [
        "source_row", "reference_type", "status", "code", "reference_code", "reference_unit", "message",
        "reference_filename", "reference_revision", "reference_size_bytes", "reference_sha256", "authority_status",
    ]
    by_role = metadata_by_role(metadata)
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for check in reference_results:
        role = str(check.get("reference_type", "")).strip().casefold()
        meta = by_role.get(role, {})
        row = {field: check.get(field, "") for field in fields}
        row.update({
            "reference_filename": meta.get("filename", ""),
            "reference_revision": meta.get("revision", ""),
            "reference_size_bytes": meta.get("size_bytes", ""),
            "reference_sha256": meta.get("sha256", ""),
            "authority_status": meta.get("authority_status", ""),
        })
        writer.writerow(row)
    return output.getvalue().encode("utf-8")
