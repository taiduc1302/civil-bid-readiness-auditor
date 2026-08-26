"""Presentation-only filtering, sorting, and grouping for review findings."""
from __future__ import annotations

from collections import OrderedDict
from typing import Any

SEVERITY_FILTERS = ("", "Priority", "Critical", "High", "Medium", "Low")
SORT_OPTIONS = ("priority", "source", "rule", "sheet", "review_status")
GROUP_OPTIONS = ("", "sheet", "rule", "review_status")
_SEVERITY_RANK = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
_REVIEW_RANK = {"Needs correction": 0, "Open": 1, "Reviewed": 2, "Accepted": 3, "Suppressed": 4}


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


def _row_number(finding: dict[str, Any]) -> tuple[int, str]:
    value = str(finding.get("row", "") or "").strip()
    try:
        return int(value), value
    except ValueError:
        return 10**12, value.casefold()


def sort_findings(
    findings: list[dict[str, Any]],
    dispositions: dict[int, dict[str, str]],
    sort_by: str = "priority",
) -> list[dict[str, Any]]:
    """Return a deterministic sorted copy with finding id as final tie-breaker."""
    sort_by = normalize_filter(sort_by) or "priority"
    if sort_by not in SORT_OPTIONS:
        sort_by = "priority"

    def review_status(finding: dict[str, Any]) -> str:
        return dispositions.get(int(finding["id"]), {"status": "Open"}).get("status", "Open")

    def key(finding: dict[str, Any]):
        fid = int(finding.get("id", 0) or 0)
        severity = str(finding.get("severity", ""))
        sheet = str(finding.get("sheet", "")).casefold()
        rule = str(finding.get("rule_id", "")).casefold()
        row = _row_number(finding)
        status = review_status(finding)
        if sort_by == "source":
            return (sheet, row, rule, fid)
        if sort_by == "rule":
            return (rule, sheet, row, fid)
        if sort_by == "sheet":
            return (sheet, row, rule, fid)
        if sort_by == "review_status":
            return (_REVIEW_RANK.get(status, 99), status.casefold(), _SEVERITY_RANK.get(severity, 99), sheet, row, fid)
        return (_SEVERITY_RANK.get(severity, 99), sheet, row, rule, fid)

    return sorted(list(findings), key=key)


def group_findings(
    findings: list[dict[str, Any]],
    dispositions: dict[int, dict[str, str]],
    group_by: str = "",
) -> list[tuple[str, list[dict[str, Any]]]]:
    """Return ordered display groups without changing the finding order inside each group."""
    group_by = normalize_filter(group_by)
    if group_by not in GROUP_OPTIONS or not group_by:
        return [("", list(findings))]

    groups: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    for finding in findings:
        if group_by == "sheet":
            label = str(finding.get("sheet", "") or "(no sheet)")
        elif group_by == "rule":
            label = str(finding.get("rule_id", "") or "(no rule)")
        else:
            label = str(dispositions.get(int(finding["id"]), {"status": "Open"}).get("status", "Open") or "Open")
        groups.setdefault(label, []).append(finding)
    return list(groups.items())


def filter_options(result: dict[str, Any]) -> dict[str, list[str]]:
    findings = result.get("findings", [])
    return {
        "rules": sorted({str(item.get("rule_id", "")) for item in findings if item.get("rule_id")}),
        "sheets": sorted({str(item.get("sheet", "")) for item in findings if item.get("sheet")}),
    }
