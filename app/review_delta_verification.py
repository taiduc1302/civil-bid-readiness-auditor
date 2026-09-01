"""Read-only local verification UI for portable Review Delta evidence bundles."""
from __future__ import annotations

import html
from http import HTTPStatus
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import server_legacy as _server
from review_delta_export import verify_review_delta_export


def _read_delta_export(message: Any) -> tuple[str, bytes]:
    found: tuple[str, bytes] | None = None
    for part in message.iter_parts():
        if part.get_content_disposition() != "form-data":
            continue
        if part.get_param("name", header="content-disposition") != "delta_export":
            continue
        filename = part.get_filename()
        if not filename:
            continue
        if found is not None:
            raise _server.InputError("Choose exactly one Review Delta evidence ZIP.")
        safe_name = Path(filename).name
        if Path(safe_name).suffix.casefold() != ".zip":
            raise _server.InputError("Review Delta evidence export must be a ZIP file.")
        payload = part.get_payload(decode=True)
        if payload is None:
            content = part.get_content()
            payload = content.encode(part.get_content_charset() or "utf-8") if isinstance(content, str) else bytes(content)
        if not payload:
            raise _server.InputError("Review Delta evidence export cannot be blank.")
        found = (safe_name, bytes(payload))
    if found is None:
        raise _server.InputError("Choose one Review Delta evidence ZIP.")
    return found


def _finding_rows(items: list[dict[str, Any]]) -> str:
    rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(item.get('change_type', '')))}</td>"
        f"<td>{html.escape(str((item.get('anchor') or {}).get('sheet', '')))}</td>"
        f"<td>{html.escape(str((item.get('anchor') or {}).get('row', '')))}</td>"
        f"<td>{html.escape(str((item.get('anchor') or {}).get('rule_id', '')))}</td>"
        f"<td>{html.escape(str((item.get('anchor') or {}).get('field', '')))}</td>"
        f"<td>{html.escape(', '.join(item.get('evidence_fields_changed', [])) or '—')}</td>"
        f"<td>{html.escape(', '.join(item.get('review_fields_changed', [])) or '—')}</td>"
        "</tr>"
        for item in items
    )
    return rows or "<tr><td colspan='7'>No changed finding anchors in the bounded preview.</td></tr>"


def _reference_rows(items: list[dict[str, Any]]) -> str:
    rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(item.get('change_type', '')))}</td>"
        f"<td>{html.escape(str((item.get('anchor') or {}).get('reference_type', '')))}</td>"
        f"<td>{html.escape(str((item.get('anchor') or {}).get('sheet', '')))}</td>"
        f"<td>{html.escape(str((item.get('anchor') or {}).get('source_row', '')))}</td>"
        f"<td>{html.escape(str((item.get('anchor') or {}).get('code', '')))}</td>"
        f"<td>{html.escape(', '.join(item.get('fields_changed', [])) or '—')}</td>"
        "</tr>"
        for item in items
    )
    return rows or "<tr><td colspan='6'>No changed reference-check anchors in the bounded preview.</td></tr>"


def _metadata_rows(items: list[dict[str, Any]]) -> str:
    rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(item.get('change_type', '')))}</td>"
        f"<td>{html.escape(str(item.get('role', '')))}</td>"
        f"<td>{html.escape(', '.join(item.get('fields_changed', [])) or '—')}</td>"
        "</tr>"
        for item in items
    )
    return rows or "<tr><td colspan='3'>No reference metadata drift in the bounded preview.</td></tr>"


def verification_page_body(result: dict[str, Any] | None = None, error: str = "") -> str:
    alert = (
        f"<div class='error'><strong>Verification failed.</strong> {html.escape(error)}</div>"
        if error else ""
    )
    output = ""
    if result:
        fc = result["finding_counts"]
        rc = result["reference_counts"]
        mc = result["reference_metadata_counts"]
        preview = result["preview"]
        output = f"""<section class='card' id='delta-verification-result'>
<h2>Review Delta export verified</h2>
<div class='notice'><strong>Integrity and internal consistency only.</strong> Verification does not prove either estimate is correct/current, does not judge change as improvement or regression, and does not establish estimator approval, reference authority, bid readiness, or HeavyBid import validity.</div>
<p><strong>Format:</strong> {html.escape(result['export_format'])} v{result['export_version']}<br>
<strong>Comparison:</strong> {html.escape(result['comparison_format'])} v{result['comparison_version']}<br>
<strong>Members verified:</strong> {result['members_verified']}</p>
<p><strong>Earlier package:</strong> {html.escape(str(result['earlier'].get('package_filename', '')))} — source {html.escape(str(result['earlier'].get('source_filename', '')))}<br>
<strong>Later package:</strong> {html.escape(str(result['later'].get('package_filename', '')))} — source {html.escape(str(result['later'].get('source_filename', '')))}</p>
<h3>Finding counts</h3><p>Added {fc.get('ADDED', 0)} | Removed {fc.get('REMOVED', 0)} | Evidence changed {fc.get('EVIDENCE_CHANGED', 0)} | Review changed {fc.get('REVIEW_CHANGED', 0)} | Both changed {fc.get('EVIDENCE_AND_REVIEW_CHANGED', 0)} | Unchanged {fc.get('UNCHANGED', 0)}</p>
<div style='overflow:auto'><table><caption>Bounded changed-finding preview</caption><thead><tr><th>Change</th><th>Sheet</th><th>Row</th><th>Rule</th><th>Field</th><th>Evidence fields</th><th>Review fields</th></tr></thead><tbody>{_finding_rows(preview['finding_changes'])}</tbody></table></div>
<h3>Reference-check counts</h3><p>Added {rc.get('ADDED', 0)} | Removed {rc.get('REMOVED', 0)} | Changed {rc.get('CHANGED', 0)} | Unchanged {rc.get('UNCHANGED', 0)}</p>
<div style='overflow:auto'><table><caption>Bounded changed-reference preview</caption><thead><tr><th>Change</th><th>Type</th><th>Sheet</th><th>Row</th><th>Code</th><th>Fields</th></tr></thead><tbody>{_reference_rows(preview['reference_changes'])}</tbody></table></div>
<h3>Reference metadata counts</h3><p>Added {mc.get('ADDED', 0)} | Removed {mc.get('REMOVED', 0)} | Changed {mc.get('CHANGED', 0)} | Unchanged {mc.get('UNCHANGED', 0)}</p>
<div style='overflow:auto'><table><caption>Bounded reference-metadata preview</caption><thead><tr><th>Change</th><th>Role</th><th>Fields</th></tr></thead><tbody>{_metadata_rows(preview['reference_metadata_changes'])}</tbody></table></div>
<p class='visually-helpful'>At most 100 changed findings, 100 changed reference checks, and 20 metadata changes are rendered. The full evidence remains inside the verified ZIP; verification creates no review session.</p>
</section>"""

    return f"""{alert}{output}
<section class='card'>
<h2>Verify Review Delta evidence bundle</h2>
<p>Upload one <code>civil-estimate-review-delta-export</code> v1 ZIP. The app checks strict ZIP structure, integrity hashes, manifest/JSON safety semantics, and deterministic CSV agreement entirely in memory.</p>
<form action='/verify-review-delta' method='post' enctype='multipart/form-data'>
<p><label>Review Delta evidence ZIP <input type='file' name='delta_export' accept='.zip,application/zip' required></label></p>
<p><button type='submit'>Verify evidence bundle</button> <a href='/compare-review-packages'>Review Delta</a> <a href='/'>Home</a></p>
</form>
</section>"""


def install_review_delta_verification_ui() -> None:
    if getattr(_server, "_review_delta_verification_ui_installed", False):
        return
    original_home = _server.home
    original_get = _server.Handler.do_GET
    original_post = _server.Handler.do_POST

    def home(message: str = "") -> bytes:
        content = original_home(message)
        extra = b"""
<section class='card'><h2>Verify Review Delta evidence</h2><p>Strictly verify a portable Review Delta evidence ZIP for structure, integrity, and internal semantic consistency without creating a review session.</p><p><a class='button' href='/verify-review-delta'>Verify Delta evidence bundle</a></p></section>
"""
        return content.replace(b"</main>", extra + b"</main>", 1)

    def do_get(self: _server.BaseHTTPRequestHandler) -> None:
        if urlparse(self.path).path == "/verify-review-delta":
            self.send_html(_server.page("Verify Review Delta evidence", verification_page_body()))
            return
        original_get(self)

    def do_post(self: _server.BaseHTTPRequestHandler) -> None:
        if urlparse(self.path).path != "/verify-review-delta":
            original_post(self)
            return
        try:
            message = _server._multipart_message(self)
            _filename, payload = _read_delta_export(message)
            result = verify_review_delta_export(payload)
            self.send_html(_server.page("Verify Review Delta evidence", verification_page_body(result=result)))
        except (_server.InputError, ValueError) as exc:
            self.send_html(
                _server.page("Verify Review Delta evidence", verification_page_body(error=str(exc))),
                HTTPStatus.BAD_REQUEST,
            )

    _server.home = home
    _server.Handler.do_GET = do_get
    _server.Handler.do_POST = do_post
    _server._review_delta_verification_ui_installed = True
