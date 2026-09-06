"""Deterministic Review Timeline evidence export and independent verification."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import zipfile
from collections import Counter
from pathlib import PurePosixPath
from typing import Any, Iterable

from review_delta_export import _validate_comparison_result, verify_review_delta_export
from review_timeline import MAX_TIMELINE_DELTAS, MIN_TIMELINE_DELTAS

TIMELINE_EXPORT_FORMAT = "civil-estimate-review-timeline-export"
TIMELINE_EXPORT_VERSION = 1
TIMELINE_EXPORT_INTEGRITY_FORMAT = "civil-estimate-review-timeline-export-integrity"
TIMELINE_EXPORT_INTEGRITY_VERSION = 1
TIMELINE_CANONICAL_FORMAT = "civil-estimate-review-timeline"
TIMELINE_CANONICAL_VERSION = 1
MAX_TIMELINE_EXPORT_BYTES = 502 * 1024 * 1024
MAX_TIMELINE_EXPORT_MEMBER_BYTES = 250 * 1024 * 1024
MAX_TIMELINE_EXPORT_TOTAL_UNCOMPRESSED_BYTES = 750 * 1024 * 1024
_FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)
_REQUIRED_MEMBERS = {
    "README.txt",
    "finding_changes.csv",
    "integrity.json",
    "manifest.json",
    "reference_changes.csv",
    "reference_metadata_changes.csv",
    "review_timeline.json",
    "snapshots.csv",
    "transitions.csv",
}
_SAFETY = {
    "evidence_chronology_only": True,
    "session_created": False,
    "persistence_created": False,
    "source_restoration_performed": False,
    "re_audit_performed": False,
    "reference_rerun_performed": False,
    "calendar_chronology_inferred": False,
    "source_currency_inferred": False,
    "generated_narrative_included": False,
    "quality_trend_inferred": False,
    "improvement_regression_inferred": False,
    "readiness_inferred": False,
    "operational_evidence_reconstructed": False,
    "heavybid_writer_performed": False,
    "heavybid_import_validated": False,
}
_FINDING_TYPES = (
    "UNCHANGED",
    "REVIEW_CHANGED",
    "EVIDENCE_CHANGED",
    "EVIDENCE_AND_REVIEW_CHANGED",
    "ADDED",
    "REMOVED",
)
_REFERENCE_TYPES = ("UNCHANGED", "CHANGED", "ADDED", "REMOVED")
_METADATA_TYPES = ("UNCHANGED", "CHANGED", "ADDED", "REMOVED")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _compact_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _safe_csv(value: Any) -> str:
    text = "" if value is None else str(value)
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text


def _write_csv(fields: list[str], rows: Iterable[dict[str, Any]]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\r\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: _safe_csv(row.get(field, "")) for field in fields})
    return output.getvalue().encode("utf-8")


def _readme_bytes() -> bytes:
    return (
        "Civil Estimate Review Auditor - Review Timeline evidence export\n\n"
        "This bundle preserves verified archived evidence chronology only. It does not prove source currency, source correctness, estimate correctness, improvement or regression, approval, bid readiness, reference authority, or HeavyBid validity.\n"
        "It contains no original Delta ZIPs, review-package ZIPs, estimate/reference source bytes, or Operational Crew/Production evidence. It contains no generated narrative, timestamp, date, or score.\n"
        "HEAVYBID_IMPORT_VALIDATED=false.\n"
    ).encode("utf-8")


def _counter(rows: list[dict[str, Any]], allowed: tuple[str, ...]) -> dict[str, int]:
    counts = Counter(item.get("change_type") for item in rows)
    unknown = sorted(set(counts) - set(allowed), key=str)
    if unknown:
        raise ValueError(f"Review Timeline export contains unsupported change type: {unknown[0]}")
    return {key: counts.get(key, 0) for key in allowed}


def _snapshot_from_lineage(index: int, lineage: dict[str, Any], aliases: list[str]) -> dict[str, Any]:
    return {
        "snapshot_index": index,
        "package_sha256": lineage["package_sha256"],
        "package_format": lineage["package_format"],
        "package_version": lineage["package_version"],
        "integrity_version": lineage["integrity_version"],
        "source_session_mode": lineage["source_session_mode"],
        "source_filename": lineage["source_filename"],
        "rows_reviewed": lineage["rows_reviewed"],
        "package_filename_aliases": sorted(set(aliases)),
    }


def _lineage_identity(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "package_sha256": snapshot["package_sha256"],
        "package_format": snapshot["package_format"],
        "package_version": snapshot["package_version"],
        "integrity_version": snapshot["integrity_version"],
        "source_session_mode": snapshot["source_session_mode"],
        "source_filename": snapshot["source_filename"],
        "rows_reviewed": snapshot["rows_reviewed"],
    }


def _build_canonical(delta_exports: Iterable[tuple[str, bytes]]) -> dict[str, Any]:
    uploads = [(str(name or "review_delta.zip"), bytes(data)) for name, data in delta_exports]
    if len(uploads) < MIN_TIMELINE_DELTAS:
        raise ValueError(f"Review Timeline export requires at least {MIN_TIMELINE_DELTAS} Delta evidence bundles.")
    if len(uploads) > MAX_TIMELINE_DELTAS:
        raise ValueError(f"Review Timeline export accepts at most {MAX_TIMELINE_DELTAS} Delta evidence bundles.")

    snapshot_registry: dict[str, dict[str, Any]] = {}
    aliases: dict[str, set[str]] = {}
    edges: list[dict[str, Any]] = []
    seen_delta_sha: set[str] = set()
    seen_edge: set[tuple[str, str]] = set()

    for filename, payload in uploads:
        verified = verify_review_delta_export(payload, include_canonical=True)
        comparison = verified["canonical_comparison"]
        delta_sha = _sha256(payload)
        if delta_sha in seen_delta_sha:
            raise ValueError("Review Timeline export contains the same Delta evidence bundle more than once.")
        seen_delta_sha.add(delta_sha)

        earlier = dict(comparison["earlier"])
        later = dict(comparison["later"])
        earlier_sha = earlier["package_sha256"]
        later_sha = later["package_sha256"]
        if earlier_sha == later_sha:
            raise ValueError("Review Timeline export cannot contain a self-transition.")
        edge_key = (earlier_sha, later_sha)
        if edge_key in seen_edge:
            raise ValueError("Review Timeline export contains duplicate transition edges.")
        seen_edge.add(edge_key)

        for lineage in (earlier, later):
            package_sha = lineage["package_sha256"]
            identity = {k: v for k, v in lineage.items() if k != "package_filename"}
            existing = snapshot_registry.get(package_sha)
            if existing is None:
                snapshot_registry[package_sha] = identity
                aliases[package_sha] = set()
            elif existing != identity:
                raise ValueError(f"Review Timeline export found conflicting snapshot lineage for {package_sha}.")
            alias = str(lineage.get("package_filename", "") or "")
            if alias:
                aliases[package_sha].add(alias)

        edges.append({
            "delta_filename": PurePosixPath(filename.replace("\\", "/")).name or "review_delta.zip",
            "delta_export_sha256": delta_sha,
            "earlier_package_sha256": earlier_sha,
            "later_package_sha256": later_sha,
            "comparison": comparison,
        })

    incoming: dict[str, list[dict[str, Any]]] = {sha: [] for sha in snapshot_registry}
    outgoing: dict[str, list[dict[str, Any]]] = {sha: [] for sha in snapshot_registry}
    for edge in edges:
        outgoing[edge["earlier_package_sha256"]].append(edge)
        incoming[edge["later_package_sha256"]].append(edge)
    if any(len(items) > 1 for items in outgoing.values()):
        raise ValueError("Review Timeline export lineage branches.")
    if any(len(items) > 1 for items in incoming.values()):
        raise ValueError("Review Timeline export lineage merges.")

    starts = [sha for sha in snapshot_registry if not incoming[sha] and outgoing[sha]]
    ends = [sha for sha in snapshot_registry if incoming[sha] and not outgoing[sha]]
    if len(starts) != 1 or len(ends) != 1:
        raise ValueError("Review Timeline export Delta bundles must form one connected acyclic linear chain.")

    ordered_edges: list[dict[str, Any]] = []
    ordered_shas = [starts[0]]
    current = starts[0]
    while outgoing[current]:
        edge = outgoing[current][0]
        ordered_edges.append(edge)
        current = edge["later_package_sha256"]
        if current in ordered_shas:
            raise ValueError("Review Timeline export lineage contains a cycle.")
        ordered_shas.append(current)
    if len(ordered_edges) != len(edges) or len(ordered_shas) != len(snapshot_registry) or current != ends[0]:
        raise ValueError("Review Timeline export Delta bundles are disconnected.")

    snapshots = [
        _snapshot_from_lineage(index, snapshot_registry[sha], sorted(aliases[sha]))
        for index, sha in enumerate(ordered_shas)
    ]
    transitions: list[dict[str, Any]] = []
    for index, edge in enumerate(ordered_edges):
        comparison = edge["comparison"]
        transitions.append({
            "transition_index": index,
            "delta_filename": edge["delta_filename"],
            "delta_export_sha256": edge["delta_export_sha256"],
            "earlier_package_sha256": edge["earlier_package_sha256"],
            "later_package_sha256": edge["later_package_sha256"],
            "finding_counts": dict(comparison["finding_counts"]),
            "reference_counts": dict(comparison["reference_counts"]),
            "reference_metadata_counts": dict(comparison["reference_metadata_counts"]),
            "finding_changes": sorted(
                comparison["finding_changes"],
                key=lambda item: (
                    item["anchor"]["sheet"], item["anchor"]["row"],
                    item["anchor"]["rule_id"], item["anchor"]["field"],
                ),
            ),
            "reference_changes": sorted(
                comparison["reference_changes"],
                key=lambda item: (
                    item["anchor"]["reference_type"], item["anchor"]["sheet"],
                    item["anchor"]["source_row"], item["anchor"]["code"],
                ),
            ),
            "reference_metadata_changes": sorted(
                comparison["reference_metadata_changes"], key=lambda item: item["role"]
            ),
        })
    return {
        "timeline_format": TIMELINE_CANONICAL_FORMAT,
        "timeline_version": TIMELINE_CANONICAL_VERSION,
        "snapshots": snapshots,
        "transitions": transitions,
        "safety": dict(_SAFETY),
    }


def _validate_snapshot(snapshot: Any, index: int) -> None:
    if not isinstance(snapshot, dict) or set(snapshot) != {
        "snapshot_index", "package_sha256", "package_format", "package_version", "integrity_version",
        "source_session_mode", "source_filename", "rows_reviewed", "package_filename_aliases",
    }:
        raise ValueError("Review Timeline export snapshot has unsupported fields.")
    if snapshot["snapshot_index"] != index or isinstance(snapshot["snapshot_index"], bool):
        raise ValueError("Review Timeline export snapshot_index is invalid.")
    if not re.fullmatch(r"[0-9a-f]{64}", str(snapshot["package_sha256"])):
        raise ValueError("Review Timeline export snapshot SHA-256 is invalid.")
    if snapshot["package_format"] != "civil-estimate-review-package" or snapshot["package_version"] != 1 or snapshot["integrity_version"] != 1:
        raise ValueError("Review Timeline export snapshot identity is unsupported.")
    if not isinstance(snapshot["source_session_mode"], str) or not snapshot["source_session_mode"]:
        raise ValueError("Review Timeline export snapshot session mode is invalid.")
    if not isinstance(snapshot["source_filename"], str):
        raise ValueError("Review Timeline export snapshot source filename is invalid.")
    if not isinstance(snapshot["rows_reviewed"], int) or isinstance(snapshot["rows_reviewed"], bool) or snapshot["rows_reviewed"] < 0:
        raise ValueError("Review Timeline export snapshot rows_reviewed is invalid.")
    aliases = snapshot["package_filename_aliases"]
    if not isinstance(aliases, list) or not all(isinstance(item, str) and item for item in aliases):
        raise ValueError("Review Timeline export snapshot aliases are invalid.")
    if aliases != sorted(set(aliases)):
        raise ValueError("Review Timeline export snapshot aliases are not canonical.")


def _validate_transition(transition: Any, index: int, earlier: dict[str, Any], later: dict[str, Any]) -> None:
    required = {
        "transition_index", "delta_filename", "delta_export_sha256", "earlier_package_sha256",
        "later_package_sha256", "finding_counts", "reference_counts", "reference_metadata_counts",
        "finding_changes", "reference_changes", "reference_metadata_changes",
    }
    if not isinstance(transition, dict) or set(transition) != required:
        raise ValueError("Review Timeline export transition has unsupported fields.")
    if transition["transition_index"] != index or isinstance(transition["transition_index"], bool):
        raise ValueError("Review Timeline export transition_index is invalid.")
    if not isinstance(transition["delta_filename"], str) or not transition["delta_filename"]:
        raise ValueError("Review Timeline export Delta filename is invalid.")
    if not re.fullmatch(r"[0-9a-f]{64}", str(transition["delta_export_sha256"])):
        raise ValueError("Review Timeline export Delta SHA-256 is invalid.")
    if transition["earlier_package_sha256"] != earlier["package_sha256"] or transition["later_package_sha256"] != later["package_sha256"]:
        raise ValueError("Review Timeline export transition adjacency is invalid.")

    comparison = {
        "comparison_format": "civil-estimate-review-delta",
        "comparison_version": 1,
        "earlier": {**_lineage_identity(earlier), "package_filename": earlier["package_filename_aliases"][0] if earlier["package_filename_aliases"] else ""},
        "later": {**_lineage_identity(later), "package_filename": later["package_filename_aliases"][0] if later["package_filename_aliases"] else ""},
        "same_source_filename": earlier["source_filename"] == later["source_filename"],
        "same_package_sha256": False,
        "finding_counts": transition["finding_counts"],
        "finding_changes": transition["finding_changes"],
        "reference_counts": transition["reference_counts"],
        "reference_changes": transition["reference_changes"],
        "reference_metadata_counts": transition["reference_metadata_counts"],
        "reference_metadata_changes": transition["reference_metadata_changes"],
        "session_created": False,
        "re_audit_performed": False,
        "correctness_inferred": False,
        "readiness_inferred": False,
        "heavybid_import_validated": False,
    }
    _validate_comparison_result(comparison)
    if transition["finding_counts"] != _counter(transition["finding_changes"], _FINDING_TYPES):
        raise ValueError("Review Timeline export finding counts do not recompute.")
    if transition["reference_counts"] != _counter(transition["reference_changes"], _REFERENCE_TYPES):
        raise ValueError("Review Timeline export reference counts do not recompute.")
    if transition["reference_metadata_counts"] != _counter(transition["reference_metadata_changes"], _METADATA_TYPES):
        raise ValueError("Review Timeline export reference metadata counts do not recompute.")


def _validate_canonical(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"timeline_format", "timeline_version", "snapshots", "transitions", "safety"}:
        raise ValueError("Review Timeline export canonical JSON has unsupported fields.")
    if value["timeline_format"] != TIMELINE_CANONICAL_FORMAT or value["timeline_version"] != TIMELINE_CANONICAL_VERSION:
        raise ValueError("Review Timeline export canonical identity is unsupported.")
    if value["safety"] != _SAFETY or set(value["safety"]) != set(_SAFETY):
        raise ValueError("Review Timeline export safety object is not exact.")
    snapshots = value["snapshots"]
    transitions = value["transitions"]
    if not isinstance(snapshots, list) or not isinstance(transitions, list):
        raise ValueError("Review Timeline export snapshots/transitions must be arrays.")
    if not (MIN_TIMELINE_DELTAS <= len(transitions) <= MAX_TIMELINE_DELTAS) or len(snapshots) != len(transitions) + 1:
        raise ValueError("Review Timeline export chain length is invalid.")
    seen_packages: set[str] = set()
    seen_deltas: set[str] = set()
    for index, snapshot in enumerate(snapshots):
        _validate_snapshot(snapshot, index)
        if snapshot["package_sha256"] in seen_packages:
            raise ValueError("Review Timeline export repeats a snapshot SHA-256.")
        seen_packages.add(snapshot["package_sha256"])
    for index, transition in enumerate(transitions):
        _validate_transition(transition, index, snapshots[index], snapshots[index + 1])
        if transition["delta_export_sha256"] in seen_deltas:
            raise ValueError("Review Timeline export repeats a Delta SHA-256.")
        seen_deltas.add(transition["delta_export_sha256"])
    return value


def _snapshots_csv(canonical: dict[str, Any]) -> bytes:
    fields = ["snapshot_index", "package_sha256", "package_format", "package_version", "integrity_version", "source_session_mode", "source_filename", "rows_reviewed", "package_filename_aliases_json"]
    rows = [{**item, "package_filename_aliases_json": _compact_json(item["package_filename_aliases"])} for item in canonical["snapshots"]]
    for row in rows:
        row.pop("package_filename_aliases", None)
    return _write_csv(fields, rows)


def _transitions_csv(canonical: dict[str, Any]) -> bytes:
    fields = ["transition_index", "delta_filename", "delta_export_sha256", "earlier_package_sha256", "later_package_sha256", "finding_counts_json", "reference_counts_json", "reference_metadata_counts_json"]
    rows = []
    for item in canonical["transitions"]:
        rows.append({
            "transition_index": item["transition_index"],
            "delta_filename": item["delta_filename"],
            "delta_export_sha256": item["delta_export_sha256"],
            "earlier_package_sha256": item["earlier_package_sha256"],
            "later_package_sha256": item["later_package_sha256"],
            "finding_counts_json": _compact_json(item["finding_counts"]),
            "reference_counts_json": _compact_json(item["reference_counts"]),
            "reference_metadata_counts_json": _compact_json(item["reference_metadata_counts"]),
        })
    return _write_csv(fields, rows)


def _finding_changes_csv(canonical: dict[str, Any]) -> bytes:
    fields = ["transition_index", "delta_export_sha256", "change_type", "sheet", "row", "rule_id", "field", "evidence_fields_changed_json", "review_fields_changed_json", "before_json", "after_json", "before_review_json", "after_review_json"]
    rows = []
    for transition in canonical["transitions"]:
        for item in transition["finding_changes"]:
            anchor = item["anchor"]
            rows.append({
                "transition_index": transition["transition_index"], "delta_export_sha256": transition["delta_export_sha256"],
                "change_type": item["change_type"], "sheet": anchor["sheet"], "row": anchor["row"], "rule_id": anchor["rule_id"], "field": anchor["field"],
                "evidence_fields_changed_json": _compact_json(sorted(set(item["evidence_fields_changed"]))),
                "review_fields_changed_json": _compact_json(sorted(set(item["review_fields_changed"]))),
                "before_json": _compact_json(item.get("before")), "after_json": _compact_json(item.get("after")),
                "before_review_json": _compact_json(item.get("before_review")), "after_review_json": _compact_json(item.get("after_review")),
            })
    return _write_csv(fields, rows)


def _reference_changes_csv(canonical: dict[str, Any]) -> bytes:
    fields = ["transition_index", "delta_export_sha256", "change_type", "reference_type", "sheet", "source_row", "code", "fields_changed_json", "before_json", "after_json"]
    rows = []
    for transition in canonical["transitions"]:
        for item in transition["reference_changes"]:
            anchor = item["anchor"]
            rows.append({
                "transition_index": transition["transition_index"], "delta_export_sha256": transition["delta_export_sha256"], "change_type": item["change_type"],
                "reference_type": anchor["reference_type"], "sheet": anchor["sheet"], "source_row": anchor["source_row"], "code": anchor["code"],
                "fields_changed_json": _compact_json(sorted(set(item["fields_changed"]))), "before_json": _compact_json(item.get("before")), "after_json": _compact_json(item.get("after")),
            })
    return _write_csv(fields, rows)


def _metadata_changes_csv(canonical: dict[str, Any]) -> bytes:
    fields = ["transition_index", "delta_export_sha256", "change_type", "role", "fields_changed_json", "before_json", "after_json"]
    rows = []
    for transition in canonical["transitions"]:
        for item in transition["reference_metadata_changes"]:
            rows.append({
                "transition_index": transition["transition_index"], "delta_export_sha256": transition["delta_export_sha256"], "change_type": item["change_type"], "role": item["role"],
                "fields_changed_json": _compact_json(sorted(set(item["fields_changed"]))), "before_json": _compact_json(item.get("before")), "after_json": _compact_json(item.get("after")),
            })
    return _write_csv(fields, rows)


def _manifest(canonical: dict[str, Any]) -> dict[str, Any]:
    transitions = canonical["transitions"]
    snapshots = canonical["snapshots"]
    return {
        "export_format": TIMELINE_EXPORT_FORMAT,
        "export_version": TIMELINE_EXPORT_VERSION,
        "canonical_format": TIMELINE_CANONICAL_FORMAT,
        "canonical_version": TIMELINE_CANONICAL_VERSION,
        "snapshot_count": len(snapshots),
        "transition_count": len(transitions),
        "first_package_sha256": snapshots[0]["package_sha256"],
        "last_package_sha256": snapshots[-1]["package_sha256"],
        "ordered_transition_lineage": [
            {
                "transition_index": item["transition_index"],
                "delta_export_sha256": item["delta_export_sha256"],
                "earlier_package_sha256": item["earlier_package_sha256"],
                "later_package_sha256": item["later_package_sha256"],
                "finding_counts": item["finding_counts"],
                "reference_counts": item["reference_counts"],
                "reference_metadata_counts": item["reference_metadata_counts"],
            }
            for item in transitions
        ],
        "contents": {
            "canonical_evidence": "review_timeline.json",
            "snapshots_csv": "snapshots.csv",
            "transitions_csv": "transitions.csv",
            "finding_changes_csv": "finding_changes.csv",
            "reference_changes_csv": "reference_changes.csv",
            "reference_metadata_changes_csv": "reference_metadata_changes.csv",
            "readme": "README.txt",
            "original_delta_exports_included": False,
            "original_review_packages_included": False,
            "original_estimate_reference_bytes_included": False,
            "operational_session_evidence_included": False,
        },
        "safety": dict(_SAFETY),
    }


def _integrity(members: dict[str, bytes]) -> dict[str, Any]:
    return {
        "integrity_format": TIMELINE_EXPORT_INTEGRITY_FORMAT,
        "integrity_version": TIMELINE_EXPORT_INTEGRITY_VERSION,
        "export_format": TIMELINE_EXPORT_FORMAT,
        "export_version": TIMELINE_EXPORT_VERSION,
        "members": {name: {"size_bytes": len(data), "sha256": _sha256(data)} for name, data in sorted(members.items())},
    }


def _members_from_canonical(canonical: dict[str, Any]) -> dict[str, bytes]:
    _validate_canonical(canonical)
    members = {
        "manifest.json": _json_bytes(_manifest(canonical)),
        "review_timeline.json": _json_bytes(canonical),
        "snapshots.csv": _snapshots_csv(canonical),
        "transitions.csv": _transitions_csv(canonical),
        "finding_changes.csv": _finding_changes_csv(canonical),
        "reference_changes.csv": _reference_changes_csv(canonical),
        "reference_metadata_changes.csv": _metadata_changes_csv(canonical),
        "README.txt": _readme_bytes(),
    }
    return members


def _write_member(book: zipfile.ZipFile, name: str, data: bytes) -> None:
    info = zipfile.ZipInfo(name, date_time=_FIXED_ZIP_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    book.writestr(info, data)


def build_review_timeline_export(delta_exports: Iterable[tuple[str, bytes]]) -> tuple[bytes, str]:
    canonical = _build_canonical(delta_exports)
    members = _members_from_canonical(canonical)
    members["integrity.json"] = _json_bytes(_integrity(members))
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as book:
        for name in sorted(members):
            _write_member(book, name, members[name])
    payload = output.getvalue()
    if len(payload) > MAX_TIMELINE_EXPORT_BYTES:
        raise ValueError("Review Timeline export exceeds the 502 MB compressed limit.")
    return payload, "review_timeline_evidence_v1.zip"


def _validate_member_name(name: str) -> None:
    if not name or "\\" in name:
        raise ValueError("Review Timeline export contains an invalid member name.")
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or len(path.parts) != 1:
        raise ValueError(f"Review Timeline export contains an unsafe member path: {name}")


def _read_member(book: zipfile.ZipFile, name: str) -> bytes:
    try:
        return book.read(name)
    except (zipfile.BadZipFile, RuntimeError, KeyError, NotImplementedError, OSError) as exc:
        raise ValueError(f"Review Timeline export member could not be read safely: {name}") from exc


def _read_json(book: zipfile.ZipFile, name: str) -> dict[str, Any]:
    try:
        value = json.loads(_read_member(book, name).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Review Timeline export contains invalid {name}.") from exc
    if not isinstance(value, dict):
        raise ValueError(f"Review Timeline export {name} must contain a JSON object.")
    return value


def verify_review_timeline_export(data: bytes) -> dict[str, Any]:
    payload = bytes(data)
    if not payload:
        raise ValueError("Review Timeline export is blank.")
    if len(payload) > MAX_TIMELINE_EXPORT_BYTES:
        raise ValueError("Review Timeline export exceeds the 502 MB compressed verification limit.")
    try:
        book = zipfile.ZipFile(io.BytesIO(payload), "r")
    except zipfile.BadZipFile as exc:
        raise ValueError("Review Timeline export is not a readable ZIP archive.") from exc

    with book:
        infos = book.infolist()
        names = []
        total = 0
        for info in infos:
            if info.is_dir():
                raise ValueError("Review Timeline export contains a directory entry.")
            _validate_member_name(info.filename)
            if info.flag_bits & 0x1:
                raise ValueError("Review Timeline export contains encrypted content.")
            if info.file_size > MAX_TIMELINE_EXPORT_MEMBER_BYTES:
                raise ValueError(f"Review Timeline export member exceeds the 250 MB limit: {info.filename}")
            total += info.file_size
            names.append(info.filename)
        if total > MAX_TIMELINE_EXPORT_TOTAL_UNCOMPRESSED_BYTES:
            raise ValueError("Review Timeline export exceeds the 750 MB total uncompressed limit.")
        if len(names) != len(set(names)):
            raise ValueError("Review Timeline export contains duplicate member names.")
        if set(names) != _REQUIRED_MEMBERS:
            raise ValueError("Review Timeline export member set does not match the v1 contract.")

        integrity = _read_json(book, "integrity.json")
        if integrity.get("integrity_format") != TIMELINE_EXPORT_INTEGRITY_FORMAT or integrity.get("integrity_version") != TIMELINE_EXPORT_INTEGRITY_VERSION:
            raise ValueError("Review Timeline export integrity contract is unsupported.")
        if integrity.get("export_format") != TIMELINE_EXPORT_FORMAT or integrity.get("export_version") != TIMELINE_EXPORT_VERSION:
            raise ValueError("Review Timeline export integrity identity is unsupported.")
        expected = integrity.get("members")
        actual_names = set(names) - {"integrity.json"}
        if not isinstance(expected, dict) or set(expected) != actual_names:
            raise ValueError("Review Timeline export integrity member map does not match archive contents.")
        for name in sorted(actual_names):
            entry = expected[name]
            if not isinstance(entry, dict) or set(entry) != {"size_bytes", "sha256"}:
                raise ValueError(f"Review Timeline export integrity entry is invalid: {name}")
            if not isinstance(entry["size_bytes"], int) or isinstance(entry["size_bytes"], bool) or entry["size_bytes"] < 0:
                raise ValueError(f"Review Timeline export integrity size is invalid: {name}")
            if not isinstance(entry["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]):
                raise ValueError(f"Review Timeline export integrity SHA-256 is invalid: {name}")
            member_data = _read_member(book, name)
            if len(member_data) != entry["size_bytes"] or _sha256(member_data) != entry["sha256"]:
                raise ValueError(f"Review Timeline export integrity check failed: {name}")

        canonical = _validate_canonical(_read_json(book, "review_timeline.json"))
        regenerated = _members_from_canonical(canonical)
        for name, expected_bytes in regenerated.items():
            if _read_member(book, name) != expected_bytes:
                raise ValueError(f"Review Timeline export {name} does not match canonical evidence.")

    return {
        "valid": True,
        "export_format": TIMELINE_EXPORT_FORMAT,
        "export_version": TIMELINE_EXPORT_VERSION,
        "snapshot_count": len(canonical["snapshots"]),
        "transition_count": len(canonical["transitions"]),
        "first_package_sha256": canonical["snapshots"][0]["package_sha256"],
        "last_package_sha256": canonical["snapshots"][-1]["package_sha256"],
        "members_verified": len(_REQUIRED_MEMBERS) - 1,
        "safety": dict(_SAFETY),
        "session_created": False,
        "persistence_created": False,
        "re_audit_performed": False,
        "reference_rerun_performed": False,
        "source_restoration_performed": False,
        "heavybid_import_validated": False,
    }
