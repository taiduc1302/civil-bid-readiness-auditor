"""Read-only cross-navigation for Review Delta evidence views.

Navigation deliberately carries no upload bytes, verification result, lineage state,
or review session state between routes. Users must re-select evidence on each page,
and each destination independently performs its own verification contract.
"""
from __future__ import annotations

import html
from urllib.parse import urlparse

import server_legacy as _server

EVIDENCE_ROUTES = {
    "/compare-review-packages",
    "/verify-review-delta",
    "/review-timeline",
}


def review_evidence_navigation(current_path: str) -> str:
    links: list[str] = []
    labels = (
        ("Review Delta", "/compare-review-packages"),
        ("Verify one Delta bundle", "/verify-review-delta"),
        ("Review Timeline", "/review-timeline"),
    )
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
    original_send_html = _server.Handler.send_html

    def send_html(self: _server.BaseHTTPRequestHandler, content: bytes, status: int = 200) -> None:
        current_path = urlparse(self.path).path
        if current_path in EVIDENCE_ROUTES:
            nav = review_evidence_navigation(current_path).encode("utf-8")
            content = content.replace(b"</main>", nav + b"</main>", 1)
        original_send_html(self, content, status)

    _server.Handler.send_html = send_html
    _server._review_evidence_navigation_installed = True
