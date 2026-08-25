"""Deterministic in-memory ZIP export for a completed local review session."""
from __future__ import annotations

import io
import json
import re
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

from audit_engine import findings_csv, management_summary_html
from finding_review import findings_review_csv, review_metrics
from reference_validation import reference_results_csv

PACKAGE_FORMAT = "civil-estimate-review-package"
PACKAGE_VERSION = 1
_FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)


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
        "reference_sources": list(session.get("reference_sources", [])),
        "contents": {
            "original_estimate_bytes_included": False,
            "original_reference_bytes_included": False,
            "reference_checks_included": bool(reference_results),
        },
        "safety": {
            "human_review_required": True,
            "bid_certified": False,
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
            "This package is a local review snapshot. It does not certify estimate correctness, bid readiness, or HeavyBid import validity.\n"
            "Original estimate/reference file bytes are intentionally not included.\n"
        ).encode("utf-8"),
    }
    if session.get("reference_results"):
        members["references.csv"] = reference_results_csv(session["reference_results"])

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as book:
        for name in sorted(members):
            _write_member(book, name, members[name])
    return output.getvalue(), package_filename(str(session.get("filename", "review")))
