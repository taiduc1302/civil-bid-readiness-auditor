"""Compact presentation-only summaries for grouped review rows."""
from __future__ import annotations

from collections import Counter
from typing import Any

_SEVERITIES = ("Critical", "High", "Medium", "Low")
_REFERENCE_STATUSES = ("NO_MATCH", "UNIT_MISMATCH", "NOT_CHECKED", "MATCH")


def findings_group_details(
    findings: list[dict[str, Any]], dispositions: dict[int, dict[str, str]]
) -> str:
    """Return severity/attention composition without repeating the group row count."""
    severity_counts = Counter(str(item.get("severity", "")) for item in findings)
    status_counts = Counter(
        str(dispositions.get(int(item["id"]), {"status": "Open"}).get("status", "Open"))
        for item in findings
    )
    parts = [f"{severity} {severity_counts[severity]}" for severity in _SEVERITIES if severity_counts[severity]]
    if status_counts["Open"]:
        parts.append(f"Open {status_counts['Open']}")
    if status_counts["Needs correction"]:
        parts.append(f"Needs correction {status_counts['Needs correction']}")
    return " · ".join(parts)


def findings_group_summary(
    findings: list[dict[str, Any]], dispositions: dict[int, dict[str, str]]
) -> str:
    """Return total count plus compact severity/attention composition."""
    total = f"{len(findings)} finding{'s' if len(findings) != 1 else ''}"
    details = findings_group_details(findings, dispositions)
    return total if not details else f"{total} · {details}"


def reference_group_details(items: list[dict[str, Any]]) -> str:
    """Return status composition without repeating the group row count."""
    counts = Counter(str(item.get("status", "")) for item in items)
    return " · ".join(f"{status} {counts[status]}" for status in _REFERENCE_STATUSES if counts[status])


def reference_group_summary(items: list[dict[str, Any]]) -> str:
    """Return total count plus compact status composition for reference rows."""
    total = f"{len(items)} check{'s' if len(items) != 1 else ''}"
    details = reference_group_details(items)
    return total if not details else f"{total} · {details}"
