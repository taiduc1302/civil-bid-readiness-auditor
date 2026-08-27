"""Two-step explicit-selection browser flow for bulk human finding dispositions.

The installer augments the existing public review page without changing
`server.py` or `server_legacy.py`. Bulk review remains explicit and two-step:
checked rows -> preview (no disposition mutation) -> one-time confirmed apply.
"""
from __future__ import annotations

import html
import secrets
from http import HTTPStatus
from urllib.parse import parse_qs, quote, urlparse

import server_legacy as _server
from bulk_review import apply_bulk_review_plan, build_bulk_review_plan
from finding_review import REVIEW_STATUSES

_MAX_FORM_BYTES = 512 * 1024


def _bulk_controls() -> str:
    options = "".join(
        f"<option value='{html.escape(status, quote=True)}'{' selected' if status == 'Reviewed' else ''}>"
        f"{html.escape(status)}</option>"
        for status in REVIEW_STATUSES
    )
    return f"""
<fieldset id='bulk-review-controls'>
<legend>Bulk review explicitly selected findings</legend>
<p class='visually-helpful'>Only rows you check in the Select for bulk column are targeted. Current filters, grouping, or hidden rows never select findings automatically.</p>
<div style='display:flex;gap:1rem;flex-wrap:wrap'>
<label>Target review status<br><select name='bulk_status'>{options}</select></label>
<label>Bulk review reason / note<br><input type='text' name='bulk_reason' maxlength='500' placeholder='Required for Suppressed'></label>
</div>
<p><label><input type='checkbox' name='bulk_ownership' value='yes'> I am explicitly choosing the checked findings and own this human review action.</label></p>
<p><button type='submit' formaction='/bulk-review/preview' formmethod='post'>Preview bulk action</button></p>
</fieldset>
"""


def _inject_bulk_controls(body: str) -> str:
    if "id='findings-caption'" not in body:
        return body
    body = body.replace(
        "<th>Reason / note</th></tr>",
        "<th>Reason / note</th><th>Select for bulk</th></tr>",
        1,
    )
    body = body.replace("<tr class='group-row'><th colspan='10'", "<tr class='group-row'><th colspan='11'")
    body = body.replace(
        "<tr><td colspan='10'>No findings match the current filters.",
        "<tr><td colspan='11'>No findings match the current filters.",
    )
    marker = "<p><button type='submit'>Save visible review states</button>"
    if marker in body:
        body = body.replace(marker, _bulk_controls() + marker, 1)
    return body


def _read_form(handler: _server.BaseHTTPRequestHandler) -> dict[str, list[str]]:
    content_type = handler.headers.get("Content-Type", "")
    if not content_type.startswith("application/x-www-form-urlencoded"):
        raise _server.InputError("Bulk review request must use URL-encoded form data.")
    try:
        length = int(handler.headers.get("Content-Length", "0") or "0")
    except ValueError as exc:
        raise _server.InputError("Bulk review request has an invalid content length.") from exc
    if length <= 0 or length > _MAX_FORM_BYTES:
        raise _server.InputError("Bulk review request is empty or exceeds the local form limit.")
    try:
        payload = handler.rfile.read(length).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise _server.InputError("Bulk review form data is not valid UTF-8.") from exc
    return parse_qs(payload, keep_blank_values=True)


def _one(form: dict[str, list[str]], key: str) -> str:
    values = form.get(key, [])
    return values[0] if values else ""


def _session(token: str) -> dict:
    session = _server.SESSIONS.get(token)
    if not session or "result" not in session:
        raise _server.InputError("This temporary audit session expired. Upload the estimate again.")
    return session


def _preview_page(token: str, plan_token: str, session: dict, plan: dict) -> bytes:
    findings = {int(item["id"]): item for item in session["result"].get("findings", [])}
    current = {item["id"]: item for item in plan["expected_current_states"]}
    rows = "".join(
        "<tr>"
        f"<td>{finding_id}</td>"
        f"<td>{html.escape(str(findings[finding_id].get('severity', '')))}</td>"
        f"<td>{html.escape(str(findings[finding_id].get('rule_id', '')))}</td>"
        f"<td>{html.escape(str(findings[finding_id].get('sheet', '')))}</td>"
        f"<td>{html.escape(str(findings[finding_id].get('row', '')))}</td>"
        f"<td>{html.escape(str(findings[finding_id].get('message', '')))}</td>"
        f"<td>{html.escape(str(current[finding_id]['status']))}</td>"
        f"<td>{html.escape(str(plan['target_status']))}</td>"
        "</tr>"
        for finding_id in plan["target_ids"]
    )
    reason = html.escape(str(plan.get("reason", ""))) or "(blank)"
    return _server.page(
        "Bulk review preview",
        f"""
<div class='notice'><strong>No review state has changed.</strong> Verify the exact selected findings below before applying.</div>
<section class='card'>
<h2>Explicit bulk action</h2>
<p><strong>Selected findings:</strong> {plan['target_count']}<br>
<strong>Target status:</strong> {html.escape(str(plan['target_status']))}<br>
<strong>Reason / note:</strong> {reason}<br>
<strong>Plan fingerprint:</strong> <code>{html.escape(str(plan['plan_sha256']))}</code></p>
<div style='overflow:auto'><table><caption>Exact findings selected for this one-time bulk action</caption>
<thead><tr><th>ID</th><th>Severity</th><th>Rule</th><th>Sheet</th><th>Row</th><th>Finding</th><th>Current state</th><th>Target state</th></tr></thead>
<tbody>{rows}</tbody></table></div>
<form action='/bulk-review/apply' method='post'>
<input type='hidden' name='token' value='{html.escape(token, quote=True)}'>
<input type='hidden' name='plan_token' value='{html.escape(plan_token, quote=True)}'>
<p><label><input type='checkbox' name='confirm_bulk_apply' value='yes'> Confirm applying this one-time plan to exactly these {plan['target_count']} finding(s).</label></p>
<p><button type='submit'>Apply bulk review action</button> <a href='/results?token={quote(token, safe='')}#findings'>Cancel and return to findings</a></p>
</form>
<p class='visually-helpful'>Application revalidates the plan digest, finding fingerprints, target IDs, and expected current states immediately before one atomic session assignment. A stale or replayed plan is rejected.</p>
</section>
""",
    )


def _error_page(message: str, token: str = "") -> bytes:
    back = f"/results?token={quote(token, safe='')}#findings" if token else "/"
    return _server.page(
        "Bulk review not applied",
        f"<div class='error'>{html.escape(message)}</div><p><a href='{back}'>Return to review</a></p>",
    )


def _handle_preview(handler: _server.BaseHTTPRequestHandler) -> None:
    _server.expire_sessions()
    form = _read_form(handler)
    token = _one(form, "token")
    session = _session(token)
    selected = form.get("bulk_id", [])
    status = _one(form, "bulk_status")
    reason = _one(form, "bulk_reason")
    ownership = _one(form, "bulk_ownership") == "yes"
    dispositions = session.setdefault("dispositions", _server.default_dispositions(session["result"]))
    plan = build_bulk_review_plan(
        session["result"],
        dispositions,
        selected,
        status,
        reason,
        ownership_acknowledged=ownership,
    )
    plan_token = secrets.token_urlsafe(18)
    # One current preview per review session. A new preview invalidates any older plan.
    session["bulk_review_plans"] = {plan_token: plan}
    handler.send_html(_preview_page(token, plan_token, session, plan))


def _handle_apply(handler: _server.BaseHTTPRequestHandler) -> None:
    _server.expire_sessions()
    form = _read_form(handler)
    token = _one(form, "token")
    session = _session(token)
    if _one(form, "confirm_bulk_apply") != "yes":
        raise _server.InputError("Bulk review apply requires explicit confirmation of the previewed one-time plan.")
    plan_token = _one(form, "plan_token")
    plans = session.get("bulk_review_plans", {})
    plan = plans.get(plan_token)
    if not plan:
        raise _server.InputError("Bulk review plan is missing, expired, replaced, or already used. Preview the selection again.")

    dispositions = session.setdefault("dispositions", _server.default_dispositions(session["result"]))
    try:
        pending = apply_bulk_review_plan(session["result"], dispositions, plan)
    except ValueError:
        plans.pop(plan_token, None)
        raise

    plans.pop(plan_token, None)
    session["dispositions"] = pending
    message = (
        f"Bulk review applied to {plan['target_count']} explicitly selected finding(s): "
        f"{plan['target_status']}."
    )
    handler.send_html(_server.findings_page(token, session, message))


def install_bulk_review_ui() -> None:
    """Install idempotent row/page/POST hooks for the public server import path."""
    if getattr(_server, "_bulk_review_ui_installed", False):
        return

    original_row = _server._review_row
    original_page = _server.page
    original_do_post = _server.Handler.do_POST

    def bulk_row(finding: dict, state: dict[str, str]) -> str:
        rendered = original_row(finding, state)
        finding_id = int(finding["id"])
        cell = (
            f"<td><input type='checkbox' name='bulk_id' value='{finding_id}' "
            f"aria-label='Select finding {finding_id} for bulk review'></td>"
        )
        return rendered.replace("</tr>", cell + "</tr>", 1)

    def bulk_page(title: str, body: str) -> bytes:
        if title == "Audit results":
            body = _inject_bulk_controls(body)
        return original_page(title, body)

    def bulk_do_post(self: _server.BaseHTTPRequestHandler) -> None:
        path = urlparse(self.path).path
        if path not in ("/bulk-review/preview", "/bulk-review/apply"):
            original_do_post(self)
            return
        token = ""
        try:
            if path == "/bulk-review/preview":
                _handle_preview(self)
            else:
                _handle_apply(self)
        except (_server.InputError, ValueError) as exc:
            # Best-effort token recovery only for the return link; never changes review state.
            try:
                token = token or ""
            except Exception:
                token = ""
            self.send_html(_error_page(str(exc), token), HTTPStatus.BAD_REQUEST)

    _server._review_row = bulk_row
    _server.page = bulk_page
    _server.Handler.do_POST = bulk_do_post
    _server._bulk_review_ui_installed = True
