"""Compact presentation-only summaries for grouped review rows."""
from __future__ import annotations

from collections import Counter
from typing import Any

_SEVERITIES = ("Critical", "High", "Medium", "Low")
_REFERENCE_STATUSES = ("NO_MATCH", "UNIT_MISMATCH", "NOT_CHECKED", "MATCH")


def findings_group_summary(
    findings: list[dict[str, Any]], dispositions: dict[int, dict[str, str]]
) -> str:
    """Return compact severity/attention counts without mutating review state."""
    severity_counts = Counter(str(item.get("severity", "")) for item in findings)
    status_counts = Counter(
        str(dispositions.get(int(item["id"]), {"status": "Open"}).get("status", "Open"))
        for item in findings
    )
    parts = [f"{len(findings)} finding{'s' if len(findings) != 1 else ''}"]
    parts.extend(f"{severity} {severity_counts[severity]}" for severity in _SEVERITIES if severity_counts[severity])
    if status_counts["Open"]:
        parts.append(f"Open {status_counts['Open']}")
    if status_counts["Needs correction"]:
        parts.append(f"Needs correction {status_counts['Needs correction']}")
    return " · ".join(parts)


def reference_group_summary(items: list[dict[str, Any]]) -> str:
    """Return compact status counts for the currently visible reference group."""
    counts = Counter(str(item.get("status", "")) for item in items)
    parts = [f"{len(items)} check{'s' if len(items) != 1 else ''}"]
    parts.extend(f"{status} {counts[status]}" for status in _REFERENCE_STATUSES if counts[status])
    return " · ".join(parts)
