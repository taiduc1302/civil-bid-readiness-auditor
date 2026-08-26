"""Temporary-session governed reference upload metadata and rendering."""
from __future__ import annotations

from collections import Counter
import html
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

from audit_engine import InputError
from reference_metadata import build_reference_metadata
from reference_validation import (
    REFERENCE_STATUSES,
    build_reference_index,
    canonicalize_export_rows,
    parse_reference_csv,
    validate_export_rows,
)
from reference_views import (
    REFERENCE_GROUP_OPTIONS,
    REFERENCE_SORT_OPTIONS,
    REFERENCE_STATUS_FILTERS,
    REFERENCE_TYPE_FILTERS,
    filter_reference_results,
    group_reference_results,
    sort_reference_results,
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


def _hidden_inputs(values: dict[str, str] | None) -> str:
    return "".join(
        f"<input type='hidden' name='{html.escape(key, quote=True)}' value='{html.escape(str(value), quote=True)}'>"
        for key, value in (values or {}).items()
        if value not in (None, "")
    )


def _reference_url(token: str, preserve: dict[str, str], view: dict[str, str], **overrides: str) -> str:
    query = {"token": token}
    query.update({key: value for key, value in preserve.items() if value})
    query.update({key: value for key, value in view.items() if value})
    for key, value in overrides.items():
        if value:
            query[key] = value
        else:
            query.pop(key, None)
    return "/results?" + urlencode(query)


def _reference_controls(
    token: str,
    results: list[dict[str, Any]],
    view: dict[str, str],
    preserve: dict[str, str],
    visible: int,
) -> str:
    status_options = "".join(
        f"<option value='{status}'{' selected' if view['ref_status'] == status else ''}>{status}</option>"
        for status in REFERENCE_STATUS_FILTERS
    )
    type_labels = {"": "All types", "activity": "Activity", "resource": "Resource"}
    type_options = "".join(
        f"<option value='{value}'{' selected' if view['ref_type'] == value else ''}>{type_labels[value]}</option>"
        for value in REFERENCE_TYPE_FILTERS
    )
    sort_labels = {"status": "Status", "source": "Source sheet / row", "code": "Source code", "type": "Reference type"}
    sort_options = "".join(
        f"<option value='{value}'{' selected' if view['ref_sort'] == value else ''}>{html.escape(sort_labels[value])}</option>"
        for value in REFERENCE_SORT_OPTIONS
    )
    group_labels = {"": "No grouping", "status": "Status", "type": "Reference type"}
    group_options = "".join(
        f"<option value='{value}'{' selected' if view['ref_group'] == value else ''}>{html.escape(group_labels[value])}</option>"
        for value in REFERENCE_GROUP_OPTIONS
    )
    quick = " ".join(
        [
            f"<a href='{_reference_url(token, preserve, view, ref_status='Exceptions')}'>Exceptions</a>",
            f"<a href='{_reference_url(token, preserve, view, ref_status='NO_MATCH')}'>NO_MATCH</a>",
            f"<a href='{_reference_url(token, preserve, view, ref_status='UNIT_MISMATCH')}'>UNIT_MISMATCH</a>",
            f"<a href='{_reference_url(token, preserve, view, ref_status='NOT_CHECKED')}'>NOT_CHECKED</a>",
            f"<a href='{_reference_url(token, preserve, view, ref_status='All')}'>All checks</a>",
        ]
    )
    return f"""<div id='reference-view-controls'><h3>Reference result view</h3>
<p><strong>Visible:</strong> {visible} of {len(results)} checks. Reference view controls never change validation results or evidence metadata.</p>
<p><strong>Quick views:</strong> {quick}</p>
<form action='/results' method='get'><input type='hidden' name='token' value='{html.escape(token, quote=True)}'>{_hidden_inputs(preserve)}
<div style='display:flex;gap:1rem;flex-wrap:wrap'>
<label>Status<br><select name='ref_status'>{status_options}</select></label>
<label>Type<br><select name='ref_type'>{type_options}</select></label>
<label>Search<br><input type='search' name='ref_q' value='{html.escape(view['ref_q'], quote=True)}' placeholder='code, message, filename, revision'></label>
<label>Sort by<br><select name='ref_sort'>{sort_options}</select></label>
<label>Group by<br><select name='ref_group'>{group_options}</select></label>
</div><p><button type='submit'>Apply reference view</button> <a href='{_reference_url(token, preserve, {"ref_status": "Exceptions", "ref_sort": "status"})}'>Reset reference view</a></p></form></div>"""


def _reference_rows(groups: list[tuple[str, list[dict[str, Any]]]]) -> str:
    parts: list[str] = []
    has_grouping = len(groups) > 1 or (groups and groups[0][0])
    for label, items in groups:
        if has_grouping and label:
            parts.append(
                f"<tr class='group-row'><th colspan='8' scope='rowgroup'>{html.escape(label)} "
                f"<span class='visually-helpful'>({len(items)} check{'s' if len(items) != 1 else ''})</span></th></tr>"
            )
        for item in items:
            parts.append(
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
            )
    return "".join(parts) or "<tr><td colspan='8'>No reference checks match the current view.</td></tr>"


def reference_panel(
    token: str,
    session: dict[str, Any],
    view: dict[str, str] | None = None,
    preserve: dict[str, str] | None = None,
) -> str:
    """Render reference upload/results UI with explicit evidence metadata and presentation-only views."""
    action = f"/references?token={quote(token, safe='')}"
    results = session.get("reference_results")
    metadata = session.get("reference_metadata", []) if results else []
    upload_form = f"""<form action='{action}' method='post' enctype='multipart/form-data'>
<p><label>Activity reference CSV <input type='file' name='activity_reference' accept='.csv'></label><br>
<label>Activity revision / label <input type='text' name='activity_revision' maxlength='200' placeholder='Optional; not inferred'></label></p>
<p><label>Resource reference CSV <input type='file' name='resource_reference' accept='.csv'></label><br>
<label>Resource revision / label <input type='text' name='resource_revision' maxlength='200' placeholder='Optional; not inferred'></label></p>
<p><button type='submit'>Validate against supplied references</button></p></form>"""
    metadata_html = _metadata_table(metadata)
    if not results:
        return (
            "<section class='card'><h2>Governed reference validation</h2>"
            "<p>Optional. Upload an explicitly selected Activity and/or Resource reference CSV. Required columns are "
            "<code>activity_code,unit</code> or <code>resource_code,unit</code>. Revision/label is recorded exactly as supplied and may be blank. "
            "The app does not infer reference authority, replacement codes, or unit conversions.</p>"
            f"{upload_form}</section>"
        )

    view = {
        "ref_status": str((view or {}).get("ref_status", "Exceptions") or "Exceptions"),
        "ref_type": str((view or {}).get("ref_type", "") or ""),
        "ref_q": str((view or {}).get("ref_q", "") or ""),
        "ref_sort": str((view or {}).get("ref_sort", "status") or "status"),
        "ref_group": str((view or {}).get("ref_group", "") or ""),
    }
    preserve = {key: str(value) for key, value in (preserve or {}).items() if value not in (None, "")}
    filtered = filter_reference_results(
        results,
        metadata,
        status=view["ref_status"],
        reference_type=view["ref_type"],
        text=view["ref_q"],
    )
    ordered = sort_reference_results(filtered, view["ref_sort"])
    groups = group_reference_results(ordered, view["ref_group"])

    counts = Counter(item["status"] for item in results)
    summary = " | ".join(f"{status}: {counts.get(status, 0)}" for status in REFERENCE_STATUSES)
    rows = _reference_rows(groups)
    controls = _reference_controls(token, results, view, preserve, len(filtered))
    return f"""<section class='card'><h2>Governed reference validation</h2>
<p><strong>Results:</strong> {html.escape(summary)}</p>
<p>Checks use only the explicitly uploaded reference files for this temporary session. A match and a recorded hash do not establish authority or HeavyBid import approval.</p>
{metadata_html}
{controls}
<p><a class='button' href='/export/references?token={html.escape(token, quote=True)}'>Download reference checks CSV</a></p>
<div style='overflow:auto'><table><caption>Visible governed reference checks</caption><thead><tr><th>Status</th><th>Type</th><th>Sheet</th><th>Row</th><th>Source code</th><th>Reference code</th><th>Reference unit</th><th>Message</th></tr></thead><tbody>{rows}</tbody></table></div>
<h3>Replace / rerun references</h3>{upload_form}</section>"""
