"""Human review/disposition controls for deterministic audit findings."""
from __future__ import annotations

import csv
import io
from typing import Any

REVIEW_STATUSES = (
    "Open",
    "Reviewed",
    "Accepted",
    "Needs correction",
    "Suppressed",
)


def default_dispositions(result: dict[str, Any]) -> dict[int, dict[str, str]]:
    return {int(f["id"]): {"status": "Open", "reason": ""} for f in result.get("findings", [])}


def validate_disposition(status: str, reason: str = "") -> tuple[str, str]:
    status = str(status or "").strip()
    reason = str(reason or "").strip()
    if status not in REVIEW_STATUSES:
        raise ValueError(f"Unsupported review status: {status}")
    if status == "Suppressed" and not reason:
        raise ValueError("Suppressed findings require a review reason.")
    return status, reason


def set_disposition(dispositions: dict[int, dict[str, str]], finding_id: int, status: str, reason: str = "") -> None:
    finding_id = int(finding_id)
    if finding_id not in dispositions:
        raise ValueError(f"Unknown finding id: {finding_id}")
    status, reason = validate_disposition(status, reason)
    dispositions[finding_id] = {"status": status, "reason": reason}


def review_metrics(result: dict[str, Any], dispositions: dict[int, dict[str, str]]) -> dict[str, int]:
    counts = {status: 0 for status in REVIEW_STATUSES}
    for finding in result.get("findings", []):
        state = dispositions.get(int(finding["id"]), {"status": "Open", "reason": ""})
        counts[state["status"]] += 1
    return counts


def findings_review_csv(result: dict[str, Any], dispositions: dict[int, dict[str, str]]) -> bytes:
    def safe(value: Any) -> str:
        text = str(value)
        return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text

    fields = [
        "id", "severity", "rule_id", "sheet", "row", "field", "message",
        "evidence", "recommended_action", "review_status", "review_reason",
    ]
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=fields)
    writer.writeheader()
    for finding in result.get("findings", []):
        state = dispositions.get(int(finding["id"]), {"status": "Open", "reason": ""})
        row = {key: finding.get(key, "") for key in fields if key in finding}
        row["review_status"] = state["status"]
        row["review_reason"] = state["reason"]
        writer.writerow({field: safe(row.get(field, "")) for field in fields})
    return out.getvalue().encode("utf-8")
