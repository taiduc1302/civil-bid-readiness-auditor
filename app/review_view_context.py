"""Preserve presentation-only review view context across POST actions.

The browser may echo its current query string in a hidden field. Only the
explicitly supported findings/reference view keys are accepted; callers never
supply a redirect URL. The server always constructs a local `/results` URL for
the current session token.
"""
from __future__ import annotations

import html
from http import HTTPStatus
from urllib.parse import parse_qs, quote, urlencode

import server_legacy as _server

FINDING_VIEW_KEYS = (
    "severity",
    "review_status",
    "rule_id",
    "sheet",
    "q",
    "sort_by",
    "group_by",
)
REFERENCE_VIEW_KEYS = (
    "ref_status",
    "ref_type",
    "ref_q",
    "ref_sort",
    "ref_group",
)
VIEW_KEYS = FINDING_VIEW_KEYS + REFERENCE_VIEW_KEYS
_MAX_QUERY_CHARS = 8192
_MAX_VALUE_CHARS = 1000


def sanitize_view_query(raw: str) -> str:
    """Return a canonical query containing only supported presentation keys."""
    raw = str(raw or "")[:_MAX_QUERY_CHARS]
    parsed = parse_qs(raw, keep_blank_values=True)
    pairs: list[tuple[str, str]] = []
    for key in VIEW_KEYS:
        if key not in parsed:
            continue
        value = str(parsed[key][0] if parsed[key] else "")[:_MAX_VALUE_CHARS]
        pairs.append((key, value))
    return urlencode(pairs)


def view_filters(raw: str) -> dict[str, str]:
    """Convert a sanitized view query into the public findings-page filter dict."""
    query = parse_qs(sanitize_view_query(raw), keep_blank_values=True)
    return {key: query.get(key, [""])[0] for key in VIEW_KEYS if key in query}


def results_return_url(token: str, raw: str = "", anchor: str = "findings") -> str:
    """Build a same-application results URL; arbitrary redirect targets are impossible."""
    pairs = [("token", str(token or ""))]
    sanitized = parse_qs(sanitize_view_query(raw), keep_blank_values=True)
    for key in VIEW_KEYS:
        if key in sanitized:
            pairs.append((key, sanitized[key][0]))
    suffix = f"#{quote(anchor, safe='')}" if anchor else ""
    return "/results?" + urlencode(pairs) + suffix


def _view_context_markup() -> str:
    return """
<input type='hidden' name='view_query' id='review-view-query' value=''>
<script>(function(){var e=document.getElementById('review-view-query');if(e){var q=window.location.search;e.value=q.charAt(0)==='?'?q.slice(1):q;}})();</script>
"""


def _inject_view_context(body: str) -> str:
    """Add one hidden presentation-context field to the findings review form."""
    if "id='findings-caption'" not in body or "name='view_query'" in body:
        return body
    marker = "<form action='/review' method='post'><input type='hidden' name='token'"
    index = body.find(marker)
    if index < 0:
        return body
    token_end = body.find(">", index + len(marker))
    if token_end < 0:
        return body
    return body[: token_end + 1] + _view_context_markup() + body[token_end + 1 :]


def _review_error_page(message: str, token: str = "", raw_view: str = "") -> bytes:
    back = results_return_url(token, raw_view) if token else "/"
    return _server.page(
        "Review states not saved",
        f"<div class='error'>{html.escape(message)}</div>"
        f"<p><a href='{html.escape(back, quote=True)}'>Return to review</a></p>",
    )


def _handle_review(handler: _server.BaseHTTPRequestHandler, form: dict[str, list[str]]) -> None:
    token = form.get("token", [""])[0]
    raw_view = form.get("view_query", [""])[0]
    with _server.session_scope(token) as session:
        if not session or "result" not in session:
            raise _server.InputError("This temporary audit session expired. Upload the file again.")

        current = session.setdefault("dispositions", _server.default_dispositions(session["result"]))
        pending = {finding_id: dict(state) for finding_id, state in current.items()}
        for finding in session["result"]["findings"]:
            finding_id = int(finding["id"])
            _server.set_disposition(
                pending,
                finding_id,
                form.get(f"status__{finding_id}", [pending[finding_id]["status"]])[0],
                form.get(f"reason__{finding_id}", [pending[finding_id]["reason"]])[0],
            )

        session["dispositions"] = pending
        rendered = _server.findings_page(
            token,
            session,
            "Review states saved for this temporary local session.",
            filters=view_filters(raw_view),
        )
    handler.send_html(rendered)


def install_review_view_context() -> None:
    """Install idempotent page/POST hooks after the existing review UX installers."""
    if getattr(_server, "_review_view_context_installed", False):
        return

    original_page = _server.page
    original_do_post = _server.Handler.do_POST

    def contextual_page(title: str, body: str) -> bytes:
        if title in ("Audit results", "Archived review snapshot"):
            body = _inject_view_context(body)
        return original_page(title, body)

    def contextual_do_post(self: _server.BaseHTTPRequestHandler) -> None:
        if self.path.split("?", 1)[0] != "/review":
            original_do_post(self)
            return
        token = ""
        raw_view = ""
        try:
            _server.expire_sessions()
            form = self._form()
            token = form.get("token", [""])[0]
            raw_view = form.get("view_query", [""])[0]
            _handle_review(self, form)
        except (_server.InputError, ValueError) as exc:
            self.send_html(_review_error_page(str(exc), token, raw_view), HTTPStatus.BAD_REQUEST)

    _server.page = contextual_page
    _server.Handler.do_POST = contextual_do_post
    _server._review_view_context_installed = True
