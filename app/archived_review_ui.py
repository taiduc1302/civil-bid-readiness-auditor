"""Explicit browser flow for continuing human review from an archived package.

This installer keeps package verification read-only. Starting an archived review
is a separate upload + acknowledgement action that creates a temporary review
session from verified snapshot evidence only. It never restores source estimate
or reference bytes and never enables re-audit/reference rerun behavior.
"""
from __future__ import annotations

import html
from http import HTTPStatus
from typing import Any
from urllib.parse import urlparse

import package_verification as _package_verification
import reference_session as _reference_session
import review_package as _review_package
import server_legacy as _server
from archived_review import (
    ARCHIVED_REVIEW_SESSION_MODE,
    archived_session_context,
    build_archived_review_session,
)


def _acknowledged(message: Any) -> bool:
    for part in message.iter_parts():
        if part.get_content_disposition() != "form-data":
            continue
        if part.get_param("name", header="content-disposition") != "archived_review_ack":
            continue
        value = part.get_content()
        if isinstance(value, bytes):
            value = value.decode(part.get_content_charset() or "utf-8", errors="replace")
        return str(value or "").strip().casefold() == "yes"
    return False


def continuation_page_body(error: str = "") -> str:
    alert = f"<div class='error'><strong>Archived review was not opened.</strong> {html.escape(error)}</div>" if error else ""
    return f"""{alert}
<section class='card'>
<h2>Review-package re-open contract</h2>
<div class='notice'><strong>A review package is archived review evidence, not a restorable estimate-audit workspace.</strong> Review-package ZIPs intentionally exclude the original estimate and reference file bytes.</div>
<h3>1. Verify package — read-only</h3>
<p>Verification checks the package structure, SHA-256 integrity, and semantic consistency. It does not create or restore a review session and does not retain the uploaded ZIP.</p>
<h3>2. Continue archived human review — snapshot continuation</h3>
<p>This flow creates a temporary <code>archived_review_snapshot</code> session from verified archived findings, human dispositions, and recorded reference evidence only. Human dispositions may continue to change; the archived deterministic findings/reference checks remain evidence from the prior snapshot.</p>
<h3>3. True estimate re-audit — new source-backed audit</h3>
<p>A true re-audit is not available from a review-package ZIP. It requires the original estimate bytes to be supplied again through the normal audit flow, plus any governed reference bytes required for reference validation. That creates a new source-backed audit; it is not restoration of this archived session.</p>
<h3>Available in archived continuation</h3>
<ul>
<li>filter, sort, group, and inspect archived findings/reference checks;</li>
<li>change human finding dispositions, including the existing explicit two-step bulk flow;</li>
<li>export findings/review/reference evidence and a new review-package snapshot with continuation provenance.</li>
</ul>
<h3>Unavailable in archived continuation</h3>
<ul>
<li>column remapping or deterministic estimate re-audit;</li>
<li>replacement/rerun of governed Activity/Resource references;</li>
<li>proof that the archived source estimate or reference files still match any current project files;</li>
<li>editable restoration of the original estimate/audit workspace.</li>
</ul>
<form action='/continue-review-package' method='post' enctype='multipart/form-data'>
<p><label>Verified review-package ZIP <input type='file' name='review_package' accept='.zip,application/zip' required></label></p>
<p><label><input type='checkbox' name='archived_review_ack' value='yes' required> I understand this continues human review of archived evidence only and does not restore or re-audit the original estimate.</label></p>
<p><button type='submit'>Open archived review continuation</button> <a href='/verify-package'>Verify package first</a> <a href='/'>Start a new source-backed audit</a></p>
</form>
<p class='visually-helpful'>The ZIP is re-verified for structure, SHA-256 integrity, and semantic consistency before the temporary continuation session is created. The package bytes themselves are not retained in the session.</p>
</section>"""


def _archived_reference_panel(
    original,
    token: str,
    session: dict[str, Any],
    view: dict[str, str] | None = None,
    preserve: dict[str, str] | None = None,
) -> str:
    if session.get("session_mode") != ARCHIVED_REVIEW_SESSION_MODE:
        return original(token, session, view=view, preserve=preserve)

    results = session.get("reference_results") or []
    notice = (
        "<div class='notice'><strong>Archived reference evidence only.</strong> These checks were recorded in the verified review snapshot. "
        "Replacement/reference rerun is unavailable because the original audited estimate rows and original reference bytes are not present in the package.</div>"
    )
    if not results:
        return (
            "<section class='card'><h2>Governed reference evidence</h2>"
            f"{notice}<p>No governed reference checks were recorded in this archived snapshot.</p></section>"
        )

    rendered = original(token, session, view=view, preserve=preserve)
    marker = "<h3>Replace / rerun references</h3>"
    if marker in rendered:
        rendered = rendered.split(marker, 1)[0] + notice + "</section>"
    else:
        rendered = rendered.replace("</section>", notice + "</section>", 1)
    rendered = rendered.replace(
        "Checks use only the explicitly uploaded reference files for this temporary session.",
        "Checks shown here are archived snapshot evidence from the verified source package.",
    )
    return rendered


def install_archived_review_ui() -> None:
    """Install idempotent route/reference/package-provenance hooks."""
    if getattr(_server, "_archived_review_ui_installed", False):
        return

    original_do_get = _server.Handler.do_GET
    original_do_post = _server.Handler.do_POST
    original_reference_panel = _reference_session.reference_panel
    original_verification_body = _package_verification.verification_page_body
    original_package_manifest = _review_package.package_manifest

    def archived_reference_panel(token, session, view=None, preserve=None):
        return _archived_reference_panel(original_reference_panel, token, session, view=view, preserve=preserve)

    def verification_body(result=None, filename="", error=""):
        body = original_verification_body(result, filename, error)
        if result:
            body += """
<section class='card'>
<h2>Continue this as archived human review?</h2>
<p>The verifier remains read-only and did not retain your ZIP. Continuing human review is a separate snapshot-continuation action, not restoration or re-audit. Select the package again and explicitly acknowledge that boundary.</p>
<p><a class='button' href='/continue-review-package'>Open archived review continuation</a></p>
</section>"""
        return body

    def package_manifest(session):
        manifest = original_package_manifest(session)
        context = archived_session_context(session)
        if context is not None:
            manifest["session_context"] = context
        return manifest

    def archived_do_get(self: _server.BaseHTTPRequestHandler) -> None:
        if urlparse(self.path).path == "/continue-review-package":
            self.send_html(_server.page("Archived review continuation", continuation_page_body()))
            return
        original_do_get(self)

    def archived_do_post(self: _server.BaseHTTPRequestHandler) -> None:
        if urlparse(self.path).path != "/continue-review-package":
            original_do_post(self)
            return
        try:
            message = _server._multipart_message(self)
            if not _acknowledged(message):
                raise _server.InputError(
                    "Explicit acknowledgement is required because archived continuation does not restore or re-audit the original estimate."
                )
            filename, payload = _package_verification.read_package_upload(message)
            session = build_archived_review_session(filename, payload)
            session["created"] = _server.time.monotonic()
            token = _server.secrets.token_urlsafe(18)
            _server.SESSIONS[token] = session
            self.send_html(
                _server.findings_page(
                    token,
                    session,
                    "Archived review snapshot opened for human-review continuation only. No estimate re-audit or reference rerun occurred.",
                )
            )
        except (_server.InputError, ValueError) as exc:
            self.send_html(
                _server.page("Archived review continuation", continuation_page_body(str(exc))),
                HTTPStatus.BAD_REQUEST,
            )

    _reference_session.reference_panel = archived_reference_panel
    _package_verification.verification_page_body = verification_body
    _review_package.package_manifest = package_manifest
    _server.Handler.do_GET = archived_do_get
    _server.Handler.do_POST = archived_do_post
    _server._archived_review_ui_installed = True
