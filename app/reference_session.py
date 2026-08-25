"""Temporary-session governed reference upload metadata and rendering."""
from __future__ import annotations

import html
from pathlib import Path
from typing import Any
from urllib.parse import quote

from audit_engine import InputError
from reference_metadata import build_reference_metadata
from reference_validation import (
    REFERENCE_STATUSES,
    build_reference_index,
    canonicalize_export_rows,
    parse_reference_csv,
    validate_export_rows,
)

_FILE_FIELDS = {
    "activity_reference": "activity",
    "resource_reference": "resource",
}
_REVISION_FIELDS = {
    "activity_revision": "activity",
    "resource_revision": "resource",
}


def parse_reference_multipart(message: Any) -> tuple[dict[str, tuple[str, bytes]], dict[str, str]]:
    """Read reference files plus optional revision labels from one multipart message."""
    uploads: dict[str, tuple[str, bytes]] = {}
    revisions: dict[str, str] = {"activity": "", "resource": ""}
    for part in message.iter_parts():
        if part.get_content_disposition() != "form-data":
            continue
        field_name = part.get_param("name", header="content-disposition")
        if field_name in _FILE_FIELDS:
            filename = part.get_filename()
            if not filename:
                continue
            payload = part.get_payload(decode=True)
            if payload is None:
                content = part.get_content()
                payload = content.encode(part.get_content_charset() or "utf-8") if isinstance(content, str) else bytes(content)
            uploads[field_name] = (Path(filename).name, bytes(payload))
            continue
        if field_name in _REVISION_FIELDS:
            content = part.get_content()
            if isinstance(content, bytes):
                content = content.decode(part.get_content_charset() or "utf-8", errors="replace")
            revisions[_REVISION_FIELDS[field_name]] = str(content or "").strip()
    return uploads, revisions


def validate_reference_submission(
    session: dict[str, Any],
    uploads: dict[str, tuple[str, bytes]],
    revisions: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Validate an entire reference rerun before returning an atomic session update."""
    if not uploads:
        raise InputError("Choose at least one Activity or Resource reference CSV.")
    if "result" not in session or "audit_sheets" not in session:
        raise InputError("This temporary audit session expired. Upload the estimate again.")

    revisions = revisions or {}
    mappings = session.get("mappings", {})
    activity_index = resource_index = None
    sources: list[str] = []
    metadata: list[dict[str, Any]] = []

    if "activity_reference" in uploads:
        if not any(mapping.get("activity") for mapping in mappings.values()):
            raise InputError("Activity reference was supplied, but no Activity field is mapped in the audited estimate.")
        name, data = uploads["activity_reference"]
        if Path(name).suffix.casefold() != ".csv":
            raise InputError("Activity reference must be a CSV file.")
        activity_index = build_reference_index(parse_reference_csv(data, "activity_code"), "activity_code")
        sources.append(name)
        metadata.append(build_reference_metadata("activity", name, data, revisions.get("activity", "")))

    if "resource_reference" in uploads:
        if not any(mapping.get("resource_code") for mapping in mappings.values()):
            raise InputError("Resource reference was supplied, but no Resource Code field is mapped in the audited estimate.")
        name, data = uploads["resource_reference"]
        if Path(name).suffix.casefold() != ".csv":
            raise InputError("Resource reference must be a CSV file.")
        resource_index = build_reference_index(parse_reference_csv(data, "resource_code"), "resource_code")
        sources.append(name)
        metadata.append(build_reference_metadata("resource", name, data, revisions.get("resource", "")))

    canonical_rows = canonicalize_export_rows(session["audit_sheets"], mappings)
    results = validate_export_rows(canonical_rows, activity_index, resource_index)
    return {
        "reference_results": results,
        "reference_sources": sources,
        "reference_metadata": metadata,
    }


def _metadata_table(metadata: list[dict[str, Any]]) -> str:
    if not metadata:
        return ""
    rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(item.get('role', '')))}</td>"
        f"<td>{html.escape(str(item.get('filename', '')))}</td>"
        f"<td>{html.escape(str(item.get('revision', '')) or '(blank)')}</td>"
        f"<td>{html.escape(str(item.get('size_bytes', '')))}</td>"
        f"<td><code>{html.escape(str(item.get('sha256', '')))}</code></td>"
        f"<td>{html.escape(str(item.get('authority_status', '')))}</td>"
        "</tr>"
        for item in metadata
    )
    return (
        "<h3>Reference evidence metadata</h3>"
        "<p>Filename, revision/label, size and SHA-256 record the supplied evidence only. "
        "They do not establish that a reference is current or approved.</p>"
        "<div style='overflow:auto'><table><thead><tr>"
        "<th>Role</th><th>Filename</th><th>Revision / label</th><th>Size (bytes)</th><th>SHA-256</th><th>Authority</th>"
        f"</tr></thead><tbody>{rows}</tbody></table></div>"
    )


def reference_panel(token: str, session: dict[str, Any]) -> str:
    """Render reference upload/results UI with explicit evidence metadata fields."""
    action = f"/references?token={quote(token, safe='')}"
    metadata = session.get("reference_metadata", [])
    upload_form = f"""<form action='{action}' method='post' enctype='multipart/form-data'>
<p><label>Activity reference CSV <input type='file' name='activity_reference' accept='.csv'></label><br>
<label>Activity revision / label <input type='text' name='activity_revision' maxlength='200' placeholder='Optional; not inferred'></label></p>
<p><label>Resource reference CSV <input type='file' name='resource_reference' accept='.csv'></label><br>
<label>Resource revision / label <input type='text' name='resource_revision' maxlength='200' placeholder='Optional; not inferred'></label></p>
<p><button type='submit'>Validate against supplied references</button></p></form>"""
    results = session.get("reference_results")
    metadata_html = _metadata_table(metadata)
    if not results:
        return (
            "<section class='card'><h2>Governed reference validation</h2>"
            "<p>Optional. Upload an explicitly selected Activity and/or Resource reference CSV. Required columns are "
            "<code>activity_code,unit</code> or <code>resource_code,unit</code>. Revision/label is recorded exactly as supplied and may be blank. "
            "The app does not infer reference authority, replacement codes, or unit conversions.</p>"
            f"{metadata_html}{upload_form}</section>"
        )

    from collections import Counter
    counts = Counter(item["status"] for item in results)
    summary = " | ".join(f"{status}: {counts.get(status, 0)}" for status in REFERENCE_STATUSES)
    exceptions = [item for item in results if item["status"] != "MATCH"]
    rows = "".join(
        "<tr>"
        f"<td class='{html.escape(str(item['status']))}'>{html.escape(str(item['status']))}</td>"
        f"<td>{html.escape(str(item['reference_type']))}</td>"
        f"<td>{html.escape(str(item.get('sheet', '')))}</td>"
        f"<td>{html.escape(str(item['source_row']))}</td>"
        f"<td>{html.escape(str(item['code']))}</td>"
        f"<td>{html.escape(str(item['reference_code']))}</td>"
        f"<td>{html.escape(str(item['reference_unit']))}</td>"
        f"<td>{html.escape(str(item['message']))}</td>"
        "</tr>"
        for item in exceptions
    ) or "<tr><td colspan='8'>No reference exceptions. All checked codes matched the supplied references.</td></tr>"
    return f"""<section class='card'><h2>Governed reference validation</h2>
<p><strong>Results:</strong> {html.escape(summary)}</p>
<p>Checks use only the explicitly uploaded reference files for this temporary session. A match and a recorded hash do not establish authority or HeavyBid import approval.</p>
{metadata_html}
<p><a class='button' href='/export/references?token={html.escape(token, quote=True)}'>Download reference checks CSV</a></p>
<div style='overflow:auto'><table><thead><tr><th>Status</th><th>Type</th><th>Sheet</th><th>Row</th><th>Source code</th><th>Reference code</th><th>Reference unit</th><th>Message</th></tr></thead><tbody>{rows}</tbody></table></div>
<h3>Replace / rerun references</h3>{upload_form}</section>"""
