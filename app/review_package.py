"""Deterministic in-memory ZIP export and integrity verification for review sessions."""
from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any

from audit_engine import findings_csv, management_summary_html
from finding_review import findings_review_csv, review_metrics
from reference_metadata import reference_review_csv

PACKAGE_FORMAT = "civil-estimate-review-package"
PACKAGE_VERSION = 1
INTEGRITY_FORMAT = "civil-estimate-review-package-integrity"
INTEGRITY_VERSION = 1
_FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)
_REQUIRED_MEMBERS = {"README.txt", "findings.csv", "manifest.json", "review.csv", "summary.html", "integrity.json"}
_ALLOWED_MEMBERS = _REQUIRED_MEMBERS | {"references.csv"}
MAX_PACKAGE_BYTES = 50 * 1024 * 1024
MAX_MEMBER_BYTES = 25 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED_BYTES = 75 * 1024 * 1024


def _safe_stem(filename: str) -> str:
    stem = Path(str(filename or "review")).stem or "review"
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._-")
    return cleaned or "review"


def package_filename(source_filename: str) -> str:
    return f"{_safe_stem(source_filename)}_review_package_v{PACKAGE_VERSION}.zip"


def package_manifest(session: dict[str, Any]) -> dict[str, Any]:
    result = session["result"]
    dispositions = session.get("dispositions", {})
    reference_results = session.get("reference_results", [])
    reference_metadata = [dict(item) for item in session.get("reference_metadata", [])] if reference_results else []
    reference_sources = list(session.get("reference_sources", [])) if reference_results else []
    return {
        "package_format": PACKAGE_FORMAT,
        "package_version": PACKAGE_VERSION,
        "source_filename": str(session.get("filename", "")),
        "rows_reviewed": result.get("rows_reviewed", 0),
        "sheets_reviewed": list(result.get("sheets_reviewed", [])),
        "mappings": session.get("mappings", {}),
        "finding_counts": result.get("counts", {}),
        "review_metrics": result.get("review_metrics", {}),
        "review_status_counts": review_metrics(result, dispositions),
        "reference_status_counts": dict(sorted(Counter(item.get("status", "") for item in reference_results if item.get("status")).items())),
        "reference_sources": reference_sources,
        "reference_metadata": reference_metadata,
        "contents": {
            "original_estimate_bytes_included": False,
            "original_reference_bytes_included": False,
            "reference_checks_included": bool(reference_results),
            "reference_metadata_included": bool(reference_metadata),
            "integrity_metadata_included": True,
        },
        "safety": {
            "human_review_required": True,
            "bid_certified": False,
            "reference_authority_established_by_app": False,
            "heavybid_import_attempted": False,
            "NOT_PRODUCTION_READY": True,
            "NOT_ESTIMATOR_VALIDATED": True,
            "HEAVYBID_IMPORT_VALIDATED": False,
        },
    }


def _write_member(book: zipfile.ZipFile, name: str, data: bytes) -> None:
    info = zipfile.ZipInfo(name, date_time=_FIXED_ZIP_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    book.writestr(info, data)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def integrity_manifest(members: dict[str, bytes]) -> dict[str, Any]:
    """Describe every non-integrity package member without creating a recursive hash."""
    return {
        "integrity_format": INTEGRITY_FORMAT,
        "integrity_version": INTEGRITY_VERSION,
        "package_format": PACKAGE_FORMAT,
        "package_version": PACKAGE_VERSION,
        "members": {
            name: {"size_bytes": len(data), "sha256": _sha256(data)}
            for name, data in sorted(members.items())
        },
    }


def build_review_package(session: dict[str, Any]) -> tuple[bytes, str]:
    """Return deterministic ZIP bytes and a safe download filename."""
    if "result" not in session:
        raise ValueError("A completed audit result is required before exporting a review package.")

    result = session["result"]
    dispositions = session.get("dispositions", {})
    manifest = package_manifest(session)
    members: dict[str, bytes] = {
        "manifest.json": (json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8"),
        "findings.csv": findings_csv(result),
        "review.csv": findings_review_csv(result, dispositions),
        "summary.html": management_summary_html(result, str(session.get("filename", "review"))),
        "README.txt": (
            "Civil Estimate Review Auditor review package\n\n"
            "This package is a local review snapshot. It does not certify estimate correctness, bid readiness, reference authority, or HeavyBid import validity.\n"
            "Original estimate/reference file bytes are intentionally not included.\n"
            "integrity.json records SHA-256 and byte size for every other package member; integrity verification does not restore a review session or establish approval.\n"
        ).encode("utf-8"),
    }
    if session.get("reference_results"):
        members["references.csv"] = reference_review_csv(
            session["reference_results"], session.get("reference_metadata", [])
        )

    integrity = integrity_manifest(members)
    members["integrity.json"] = (
        json.dumps(integrity, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as book:
        for name in sorted(members):
            _write_member(book, name, members[name])
    return output.getvalue(), package_filename(str(session.get("filename", "review")))


def _validate_member_name(name: str) -> None:
    if not name or "\\" in name:
        raise ValueError("Review package contains an invalid member name.")
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or len(path.parts) != 1:
        raise ValueError(f"Review package contains an unsafe member path: {name}")


def _read_member(book: zipfile.ZipFile, name: str) -> bytes:
    """Read one ZIP member while converting corruption/codec errors to a controlled failure."""
    try:
        return book.read(name)
    except (zipfile.BadZipFile, RuntimeError, KeyError, NotImplementedError, OSError) as exc:
        raise ValueError(f"Review package member could not be read safely: {name}") from exc


def _read_json(book: zipfile.ZipFile, name: str) -> dict[str, Any]:
    try:
        value = json.loads(_read_member(book, name).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Review package contains invalid {name}.") from exc
    if not isinstance(value, dict):
        raise ValueError(f"Review package {name} must contain a JSON object.")
    return value


def verify_review_package(data: bytes) -> dict[str, Any]:
    """Verify package hashes plus semantic snapshot consistency entirely in memory."""
    payload = bytes(data)
    if not payload:
        raise ValueError("Review package is blank.")
    if len(payload) > MAX_PACKAGE_BYTES:
        raise ValueError("Review package exceeds the 50 MB verification limit.")

    try:
        book = zipfile.ZipFile(io.BytesIO(payload), "r")
    except zipfile.BadZipFile as exc:
        raise ValueError("Review package is not a readable ZIP archive.") from exc

    with book:
        infos = [info for info in book.infolist() if not info.is_dir()]
        names = [info.filename for info in infos]
        for name in names:
            _validate_member_name(name)
        if len(names) != len(set(names)):
            raise ValueError("Review package contains duplicate member names.")
        member_set = set(names)
        missing = sorted(_REQUIRED_MEMBERS - member_set)
        if missing:
            raise ValueError(f"Review package is missing required members: {', '.join(missing)}")
        unexpected = sorted(member_set - _ALLOWED_MEMBERS)
        if unexpected:
            raise ValueError(f"Review package contains unexpected members: {', '.join(unexpected)}")

        total_uncompressed = 0
        for info in infos:
            if info.file_size > MAX_MEMBER_BYTES:
                raise ValueError(f"Review package member exceeds the 25 MB verification limit: {info.filename}")
            total_uncompressed += info.file_size
        if total_uncompressed > MAX_TOTAL_UNCOMPRESSED_BYTES:
            raise ValueError("Review package exceeds the 75 MB uncompressed verification limit.")

        integrity = _read_json(book, "integrity.json")
        if integrity.get("integrity_format") != INTEGRITY_FORMAT or integrity.get("integrity_version") != INTEGRITY_VERSION:
            raise ValueError("Review package integrity contract is unsupported.")
        if integrity.get("package_format") != PACKAGE_FORMAT or integrity.get("package_version") != PACKAGE_VERSION:
            raise ValueError("Review package integrity metadata does not match the supported package identity.")
        expected = integrity.get("members")
        if not isinstance(expected, dict):
            raise ValueError("Review package integrity metadata is missing member checksums.")

        actual_names = member_set - {"integrity.json"}
        if set(expected) != actual_names:
            raise ValueError("Review package integrity member list does not match archive contents.")

        for name in sorted(actual_names):
            entry = expected.get(name)
            if not isinstance(entry, dict):
                raise ValueError(f"Review package integrity entry is invalid: {name}")
            expected_sha = str(entry.get("sha256", ""))
            expected_size = entry.get("size_bytes")
            if not re.fullmatch(r"[0-9a-f]{64}", expected_sha):
                raise ValueError(f"Review package integrity SHA-256 is invalid: {name}")
            if not isinstance(expected_size, int) or expected_size < 0:
                raise ValueError(f"Review package integrity size is invalid: {name}")
            member_data = _read_member(book, name)
            if len(member_data) != expected_size:
                raise ValueError(f"Review package member size does not match integrity metadata: {name}")
            if _sha256(member_data) != expected_sha:
                raise ValueError(f"Review package member SHA-256 does not match integrity metadata: {name}")

        manifest = _read_json(book, "manifest.json")
        if manifest.get("package_format") != PACKAGE_FORMAT or manifest.get("package_version") != PACKAGE_VERSION:
            raise ValueError("Review package manifest identity is unsupported.")

    verified = {
        "valid": True,
        "package_format": PACKAGE_FORMAT,
        "package_version": PACKAGE_VERSION,
        "integrity_version": INTEGRITY_VERSION,
        "members_verified": len(actual_names),
        "reference_checks_included": "references.csv" in actual_names,
        "session_restored": False,
        "approval_inferred": False,
        "heavybid_import_validated": False,
    }
    # Lazy import avoids a module cycle while ensuring semantic inspection can
    # never run before structure/hash verification succeeds.
    from package_preview import inspect_review_package_members

    verified["snapshot_preview"] = inspect_review_package_members(payload, verified)
    return verified
