"""Build a neutral multi-snapshot evidence chain from verified Review Delta exports."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Iterable

from review_delta_export import verify_review_delta_export

TIMELINE_FORMAT = "civil-estimate-review-timeline"
TIMELINE_VERSION = 1
MIN_TIMELINE_DELTAS = 2
MAX_TIMELINE_DELTAS = 10
_PACKAGE_FORMAT = "civil-estimate-review-package"
_PACKAGE_VERSION = 1
_INTEGRITY_VERSION = 1


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _snapshot_identity(snapshot: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(snapshot, dict):
        raise ValueError("Review Timeline snapshot lineage must be an object.")
    package_sha256 = snapshot.get("package_sha256")
    if not isinstance(package_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", package_sha256):
        raise ValueError("Review Timeline requires a valid review-package SHA-256 for every snapshot.")
    if snapshot.get("package_format") != _PACKAGE_FORMAT:
        raise ValueError("Review Timeline requires the supported review-package format for every snapshot.")
    package_version = snapshot.get("package_version")
    integrity_version = snapshot.get("integrity_version")
    rows_reviewed = snapshot.get("rows_reviewed")
    if package_version != _PACKAGE_VERSION or isinstance(package_version, bool):
        raise ValueError("Review Timeline requires supported review-package version 1 lineage.")
    if integrity_version != _INTEGRITY_VERSION or isinstance(integrity_version, bool):
        raise ValueError("Review Timeline requires supported review-package integrity version 1 lineage.")
    if not isinstance(rows_reviewed, int) or isinstance(rows_reviewed, bool) or rows_reviewed < 0:
        raise ValueError("Review Timeline snapshot rows_reviewed must be a nonnegative integer.")
    source_session_mode = snapshot.get("source_session_mode")
    source_filename = snapshot.get("source_filename")
    if not isinstance(source_session_mode, str) or not source_session_mode:
        raise ValueError("Review Timeline snapshot source_session_mode is required.")
    if not isinstance(source_filename, str):
        raise ValueError("Review Timeline snapshot source_filename must be text.")
    return {
        "package_sha256": package_sha256,
        "package_format": _PACKAGE_FORMAT,
        "package_version": _PACKAGE_VERSION,
        "integrity_version": _INTEGRITY_VERSION,
        "source_session_mode": source_session_mode,
        "source_filename": source_filename,
        "rows_reviewed": rows_reviewed,
    }


def _register_snapshot(registry: dict[str, dict[str, Any]], snapshot: dict[str, Any]) -> str:
    identity = _snapshot_identity(snapshot)
    package_sha = identity["package_sha256"]
    alias = str(snapshot.get("package_filename", "") or "")
    existing = registry.get(package_sha)
    if existing is None:
        registry[package_sha] = {**identity, "package_filename_aliases": sorted({alias} - {""})}
        return package_sha
    for field, value in identity.items():
        if existing.get(field) != value:
            raise ValueError(
                f"Review Timeline found conflicting snapshot lineage for package SHA-256 {package_sha}: {field}."
            )
    if alias and alias not in existing["package_filename_aliases"]:
        existing["package_filename_aliases"] = sorted([*existing["package_filename_aliases"], alias])
    return package_sha


def _edge_record(filename: str, data: bytes, verified: dict[str, Any], earlier_sha: str, later_sha: str) -> dict[str, Any]:
    return {
        "delta_filename": Path(str(filename or "review_delta.zip")).name or "review_delta.zip",
        "delta_sha256": _sha256(data),
        "earlier_package_sha256": earlier_sha,
        "later_package_sha256": later_sha,
        "finding_counts": dict(verified.get("finding_counts", {})),
        "reference_counts": dict(verified.get("reference_counts", {})),
        "reference_metadata_counts": dict(verified.get("reference_metadata_counts", {})),
    }


def build_review_timeline(delta_exports: Iterable[tuple[str, bytes]]) -> dict[str, Any]:
    """Verify and structurally order a connected linear chain of Delta exports.

    Ordering is derived only from exact review-package SHA-256 continuity. No date,
    quality, readiness, or improvement/regression inference is performed.
    """
    uploads = [(str(name or "review_delta.zip"), bytes(data)) for name, data in delta_exports]
    if len(uploads) < MIN_TIMELINE_DELTAS:
        raise ValueError(f"Review Timeline requires at least {MIN_TIMELINE_DELTAS} Delta evidence bundles.")
    if len(uploads) > MAX_TIMELINE_DELTAS:
        raise ValueError(f"Review Timeline accepts at most {MAX_TIMELINE_DELTAS} Delta evidence bundles per request.")

    snapshots: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    bundle_shas: set[str] = set()
    edge_keys: set[tuple[str, str]] = set()

    for filename, data in uploads:
        verified = verify_review_delta_export(data)
        bundle_sha = _sha256(data)
        if bundle_sha in bundle_shas:
            raise ValueError("Review Timeline contains the same Delta evidence bundle more than once.")
        bundle_shas.add(bundle_sha)
        earlier_sha = _register_snapshot(snapshots, verified.get("earlier", {}))
        later_sha = _register_snapshot(snapshots, verified.get("later", {}))
        if earlier_sha == later_sha:
            raise ValueError("Review Timeline cannot use a self-transition where Earlier and Later are the same review package.")
        edge_key = (earlier_sha, later_sha)
        if edge_key in edge_keys:
            raise ValueError("Review Timeline contains duplicate review-package transition edges.")
        edge_keys.add(edge_key)
        edges.append(_edge_record(filename, data, verified, earlier_sha, later_sha))

    incoming: dict[str, list[dict[str, Any]]] = {sha: [] for sha in snapshots}
    outgoing: dict[str, list[dict[str, Any]]] = {sha: [] for sha in snapshots}
    for edge in edges:
        outgoing[edge["earlier_package_sha256"]].append(edge)
        incoming[edge["later_package_sha256"]].append(edge)
    for package_sha, items in outgoing.items():
        if len(items) > 1:
            raise ValueError(f"Review Timeline is branching at review-package SHA-256 {package_sha}.")
    for package_sha, items in incoming.items():
        if len(items) > 1:
            raise ValueError(f"Review Timeline is merging at review-package SHA-256 {package_sha}.")

    starts = [sha for sha in snapshots if not incoming[sha] and outgoing[sha]]
    ends = [sha for sha in snapshots if incoming[sha] and not outgoing[sha]]
    if len(starts) != 1 or len(ends) != 1:
        raise ValueError("Review Timeline Delta bundles must form one connected acyclic linear chain.")

    ordered_edges: list[dict[str, Any]] = []
    ordered_snapshot_shas: list[str] = [starts[0]]
    visited_edges: set[str] = set()
    current = starts[0]
    while outgoing[current]:
        edge = outgoing[current][0]
        edge_identity = edge["delta_sha256"]
        if edge_identity in visited_edges:
            raise ValueError("Review Timeline contains a cycle.")
        visited_edges.add(edge_identity)
        ordered_edges.append(edge)
        current = edge["later_package_sha256"]
        if current in ordered_snapshot_shas:
            raise ValueError("Review Timeline contains a cycle.")
        ordered_snapshot_shas.append(current)

    if len(ordered_edges) != len(edges) or len(ordered_snapshot_shas) != len(snapshots):
        raise ValueError("Review Timeline Delta bundles are disconnected and cannot form one evidence chain.")
    if current != ends[0]:
        raise ValueError("Review Timeline could not resolve one linear end snapshot.")

    ordered_snapshots = [dict(snapshots[sha]) for sha in ordered_snapshot_shas]
    same_source_filename = len({item["source_filename"] for item in ordered_snapshots}) <= 1
    return {
        "timeline_format": TIMELINE_FORMAT,
        "timeline_version": TIMELINE_VERSION,
        "delta_bundle_count": len(ordered_edges),
        "snapshot_count": len(ordered_snapshots),
        "snapshots": ordered_snapshots,
        "transitions": ordered_edges,
        "same_source_filename_across_chain": same_source_filename,
        "continuity_verified_by_package_sha256": True,
        "session_created": False,
        "re_audit_performed": False,
        "source_currency_inferred": False,
        "quality_trend_inferred": False,
        "improvement_regression_inferred": False,
        "readiness_inferred": False,
        "heavybid_import_validated": False,
    }
