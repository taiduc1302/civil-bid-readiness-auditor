"""Shared accessibility semantics for the public local browser UI."""
from __future__ import annotations

import server_legacy as _server

_SKIP_STYLE = (
    ".global-skip{position:absolute;left:-10000px;top:auto;width:1px;height:1px;overflow:hidden}"
    ".global-skip:focus{position:static;width:auto;height:auto;display:inline-block;margin:8px;padding:8px;"
    "background:white;border:2px solid currentColor}"
)


def _semantic_body(body: str) -> str:
    """Add roles to shared status/error blocks without changing visible content."""
    body = body.replace(
        "<div class='error'>",
        "<div class='error' role='alert' aria-live='assertive' tabindex='-1'>",
    )
    body = body.replace(
        "<div class='notice'>",
        "<div class='notice' role='status' aria-live='polite'>",
    )
    return body


def install_accessibility_semantics() -> None:
    """Install one idempotent wrapper around the shared page renderer.

    Idempotence is recorded on the shared runtime rather than the current page
    function object because other public features intentionally wrap ``page``
    after accessibility is installed.
    """
    if getattr(_server, "_accessibility_semantics_installed", False):
        return

    original = _server.page
    if _SKIP_STYLE not in _server.STYLE:
        _server.STYLE += _SKIP_STYLE

    def accessible_page(title: str, body: str) -> bytes:
        rendered = original(title, _semantic_body(body)).decode("utf-8")
        rendered = rendered.replace("<html>", "<html lang='en'>", 1)
        rendered = rendered.replace(
            "<body><main>",
            "<body><a class='global-skip' href='#main-content'>Skip to main content</a>"
            "<main id='main-content' tabindex='-1'>",
            1,
        )
        return rendered.encode("utf-8")

    _server.page = accessible_page
    _server._accessibility_semantics_installed = True
