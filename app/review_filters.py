"""Presentation-only filtering for deterministic findings and human review state."""
from __future__ import annotations

from typing import Any

SEVERITY_FILTERS = ("", "Priority", "Critical", "High", "Medium", "Low")


def normalize_filter(value: Any) -> str:
    return str(value or "").strip()


def filter_findings(
    result: dict[str, Any],
    dispositions: dict[int, dict[str, str]],
    *,
    severity: str = "",
    review_status: str = "",
    rule_id: str = "",
    sheet: str = "",
    text: str = "",
) -> list[dict[str, Any]]:
    """Return a filtered view without mutating findings or dispositions."""
    severity = normalize_filter(severity)
    review_status = normalize_filter(review_status)
    rule_id = normalize_filter(rule_id)
    sheet = normalize_filter(sheet)
    text_key = normalize_filter(text).casefold()

    findings = result.get("findings", [])
    filtered: list[dict[str, Any]] = []
    for finding in findings:
        if severity == "Priority":
            if finding.get("severity") not in ("Critical", "High"):
                continue
        elif severity and finding.get("severity") != severity:
            continue

        state = dispositions.get(int(finding["id"]), {"status": "Open", "reason": ""})
        if review_status and state.get("status") != review_status:
            continue
        if rule_id and finding.get("rule_id") != rule_id:
            continue
        if sheet and finding.get("sheet") != sheet:
            continue

        if text_key:
            haystack = " ".join(
                str(finding.get(field, ""))
                for field in (
                    "severity", "rule_id", "sheet", "row", "field", "message",
                    "evidence", "recommended_action",
                )
            )
            haystack += " " + str(state.get("reason", ""))
            if text_key not in haystack.casefold():
                continue
        filtered.append(finding)
    return filtered


def filter_options(result: dict[str, Any]) -> dict[str, list[str]]:
    findings = result.get("findings", [])
    return {
        "rules": sorted({str(item.get("rule_id", "")) for item in findings if item.get("rule_id")}),
        "sheets": sorted({str(item.get("sheet", "")) for item in findings if item.get("sheet")}),
    }
