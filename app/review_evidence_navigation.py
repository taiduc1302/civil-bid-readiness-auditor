"""Read-only cross-navigation for Review Delta evidence views.

Navigation deliberately carries no upload bytes, verification result, lineage state,
or review session state between routes. Users must re-select evidence on each page,
and each destination independently performs its own verification contract.
"""
from __future__ import annotations

import html
from typing import Callable

import server_legacy as _server

EVIDENCE_PAGE_TITLES = {
    "Review Delta": "/compare-review-packages",
    "Verify Review Delta evidence": "/verify-review-delta",
    "Review Timeline": "/review-timeline",
}


def review_evidence_navigation(current_title: str) -> str:
    links: list[str] = []
    labels = (
        ("Review Delta", "/compare-review-packages"),
        ("Verify one Delta bundle", "/verify-review-delta"),
        ("Review Timeline", "/review-timeline"),
    )
    current_path = EVIDENCE_PAGE_TITLES.get(current_title, "")
    for label, path in labels:
        if path == current_path:
            links.append(f"<strong aria-current='page'>{html.escape(label)}</strong>")
        else:
            links.append(f"<a href='{path}'>{html.escape(label)}</a>")
    return (
        "<nav class='card' aria-label='Review evidence navigation'>"
        "<h2>Review evidence views</h2>"
        f"<p>{' | '.join(links)}</p>"
        "<p class='visually-helpful'><strong>No evidence is carried between these pages.</strong> "
        "Navigation does not persist or transfer uploaded ZIP bytes, verification state, or lineage state. "
        "Re-select evidence at the destination; that route verifies its own inputs independently before use.</p>"
        "</nav>"
    )


def install_review_evidence_navigation() -> None:
    if getattr(_server, "_review_evidence_navigation_installed", False):
        return
    original_page: Callable[[str, str], bytes] = _server.page

    def page(title: str, body: str) -> bytes:
        if title in EVIDENCE_PAGE_TITLES:
            body = review_evidence_navigation(title) + body
        return original_page(title, body)

    _server.page = page
    _server._review_evidence_navigation_installed = True
