"""Presentation-only review attention and empty-state guidance."""
from __future__ import annotations

from collections import Counter
from typing import Any

from finding_review import review_metrics


def review_attention_summary(
    result: dict[str, Any],
    dispositions: dict[int, dict[str, str]],
    reference_results: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Summarize review attention without inferring approval or readiness."""
    status_counts = review_metrics(result, dispositions)
    findings_total = len(result.get("findings", []))
    open_count = status_counts.get("Open", 0)
    needs_correction = status_counts.get("Needs correction", 0)
    finding_attention = open_count + needs_correction

    reference_results = list(reference_results or [])
    reference_counts = Counter(str(item.get("status", "")) for item in reference_results)
    reference_exceptions = sum(
        count for status, count in reference_counts.items() if status and status != "MATCH"
    )

    if findings_total == 0:
        finding_message = (
            "No deterministic findings were produced for the supplied mapping. "
            "This is not proof that the estimate is correct, complete, or commercially ready."
        )
    elif finding_attention:
        finding_message = (
            f"{finding_attention} finding(s) are currently Open or Needs correction and remain human-review attention items."
        )
    else:
        finding_message = (
            "No findings are currently marked Open or Needs correction. This describes human review state only; "
            "it is not estimator approval or bid readiness."
        )

    if not reference_results:
        reference_message = (
            "No governed reference checks are loaded. Reference validation is optional and should use only an explicitly selected snapshot."
        )
    elif reference_exceptions:
        reference_message = (
            f"{reference_exceptions} governed reference check(s) are exceptions to exact matching against the supplied snapshot."
        )
    else:
        reference_message = (
            "No reference exceptions are present in the supplied snapshot checks. Exact matches and recorded hashes do not establish reference authority."
        )

    return {
        "findings_total": findings_total,
        "open_count": open_count,
        "needs_correction_count": needs_correction,
        "finding_attention_count": finding_attention,
        "review_status_counts": status_counts,
        "reference_checks_total": len(reference_results),
        "reference_exception_count": reference_exceptions,
        "reference_status_counts": dict(reference_counts),
        "finding_message": finding_message,
        "reference_message": reference_message,
        "approval_inferred": False,
        "bid_readiness_inferred": False,
        "reference_authority_inferred": False,
    }
