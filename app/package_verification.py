"""Read-only local UI helpers for review-package integrity verification."""
from __future__ import annotations

import html
from pathlib import Path
from typing import Any

from audit_engine import InputError
from package_preview import snapshot_preview_body

MAX_UI_PACKAGE_UPLOAD_BYTES = 26 * 1024 * 1024


def read_package_upload(message: Any) -> tuple[str, bytes]:
    """Read exactly one package upload from a parsed multipart message."""
    selected: tuple[str, bytes] | None = None
    for part in message.iter_parts():
        if part.get_content_disposition() != "form-data":
            continue
        if part.get_param("name", header="content-disposition") != "review_package":
            continue
        filename = part.get_filename()
        if not filename:
            continue
        payload = part.get_payload(decode=True)
        if payload is None:
            content = part.get_content()
            payload = content.encode(part.get_content_charset() or "utf-8") if isinstance(content, str) else bytes(content)
        if selected is not None:
            raise InputError("Choose exactly one review-package ZIP.")
        selected = (Path(filename).name, bytes(payload))

    if selected is None:
        raise InputError("Choose a review-package ZIP before verifying.")
    filename, payload = selected
    if Path(filename).suffix.casefold() != ".zip":
        raise InputError("Review package must be a ZIP file.")
    if not payload:
        raise InputError("Review-package ZIP is blank.")
    if len(payload) > MAX_UI_PACKAGE_UPLOAD_BYTES:
        raise InputError("Review-package ZIP exceeds the local 26 MB upload limit.")
    return filename, payload


def verification_page_body(
    result: dict[str, Any] | None = None,
    filename: str = "",
    error: str = "",
    preview: dict[str, Any] | None = None,
) -> str:
    """Render verifier + optional read-only snapshot preview; never offer restoration controls."""
    alert = f"<div class='error'><strong>Verification failed.</strong> {html.escape(error)}</div>" if error else ""
    verified = ""
    if result:
        verified = f"""<section class='card' id='verification-result'>
<h2>Integrity verification passed</h2>
<p><strong>Uploaded file:</strong> {html.escape(filename)}</p>
<div class='metrics'>
<div class='metric'><strong>{html.escape(str(result.get('members_verified', '')))}</strong><br>Members verified</div>
<div class='metric'><strong>v{html.escape(str(result.get('package_version', '')))}</strong><br>Package version</div>
<div class='metric'><strong>v{html.escape(str(result.get('integrity_version', '')))}</strong><br>Integrity version</div>
</div>
<p><strong>Package format:</strong> <code>{html.escape(str(result.get('package_format', '')))}</code><br>
<strong>Reference checks included:</strong> {'yes' if result.get('reference_checks_included') else 'no'}</p>
<div class='notice'><strong>Integrity only.</strong> This proves only that the ZIP matches its recorded structure and member hashes. No review session was restored. It does not establish estimate correctness, estimator approval, reference authority, bid readiness, or HeavyBid import validity.</div>
</section>"""

    resolved_preview = preview or (result.get("snapshot_preview") if result else None)
    preview_html = snapshot_preview_body(resolved_preview) if resolved_preview else ""
    return f"""{alert}{verified}{preview_html}
<section class='card'>
<h2>Verify a review package</h2>
<p>Select a review-package ZIP created by this app. Verification and read-only snapshot inspection run locally in memory. Uploaded package bytes are not added to a review session and are not written to disk by this application.</p>
<form action='/verify-package' method='post' enctype='multipart/form-data'>
<label>Review package ZIP <input type='file' name='review_package' accept='.zip,application/zip' required></label>
<p><button type='submit'>Verify and preview package</button> <a href='/'>Back to home</a></p>
</form>
<p class='visually-helpful'>The local browser upload route accepts packages up to 26 MB. A successful integrity/semantic preview never restores findings, dispositions, mappings, references, source files, or approvals.</p>
</section>"""
