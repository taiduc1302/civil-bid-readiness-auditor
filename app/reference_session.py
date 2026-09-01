"""Temporary-session governed reference upload metadata and rendering."""
from __future__ import annotations

from collections import Counter
import html
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

from audit_engine import InputError
from operational_reference import (
    OPERATIONAL_STATUSES,
    build_activity_operational_index,
    build_operational_reference_metadata,
    parse_operational_reference_csv,
    validate_operational_export_rows,
)
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
    "operational_reference": "operational_activity",
}
_REVISION_FIELDS = {
    "activity_revision": "activity",
    "resource_revision": "resource",
    "operational_revision": "operational_activity",
}
_REGULAR_FILE_FIELDS = ("activity_reference", "resource_reference")
_OPERATIONAL_FIELDS = ("crew_code", "production_rate")


def parse_reference_multipart(message: Any) -> tuple[dict[str, tuple[str, bytes]], dict[str, str]]:
    """Read reference files plus optional revision labels from one multipart message."""
    uploads: dict[str, tuple[str, bytes]] = {}
    revisions: dict[str, str] = {"activity": "", "resource": "", "operational_activity": ""}
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
    """Validate a regular Activity/Resource rerun before returning an atomic update."""
    uploads = {key: value for key, value in uploads.items() if key in _REGULAR_FILE_FIELDS}
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


def _source_operational_fields(session: dict[str, Any]) -> tuple[str, ...]:
    fields: set[str] = set()
    for mapping in session.get("mappings", {}).values():
        if not mapping.get("activity"):
            continue
        fields.update(field for field in _OPERATIONAL_FIELDS if mapping.get(field))
    return tuple(field for field in _OPERATIONAL_FIELDS if field in fields)


def validate_operational_submission(
    session: dict[str, Any],
    upload: tuple[str, bytes],
    revision: str = "",
) -> dict[str, Any]:
    """Validate explicit Crew/Production evidence without changing package-v1 evidence."""
    if "result" not in session or "audit_sheets" not in session:
        raise InputError("Operational reference comparison requires a current source-backed audit session.")
    name, data = upload
    if Path(name).suffix.casefold() != ".csv":
        raise InputError("Operational Activity reference must be a CSV file.")

    mappings = session.get("mappings", {})
    source_fields = set(_source_operational_fields(session))
    if not source_fields:
        raise InputError(
            "Operational reference comparison requires Activity plus Crew Code and/or Production Rate to be explicitly mapped in the audited estimate."
        )

    reference_rows, reference_fields = parse_operational_reference_csv(data)
    overlap = source_fields.intersection(reference_fields)
    if not overlap:
        raise InputError(
            "The operational reference has no Crew Code / Production Rate field that overlaps the explicitly mapped source fields."
        )

    eligible_sheets = {
        sheet
        for sheet, mapping in mappings.items()
        if mapping.get("activity") and any(mapping.get(field) for field in overlap)
    }
    canonical_rows = canonicalize_export_rows(session["audit_sheets"], mappings)
    eligible_rows = [row for row in canonical_rows if row.get("__sheet") in eligible_sheets]
    if not any(str(row.get(field, "") or "").strip() for row in eligible_rows for field in overlap):
        raise InputError("The mapped source rows contain no explicit Crew Code or Production Rate values for the comparable field(s).")
    if not any(str(row.get(field, "") or "").strip() for row in reference_rows for field in overlap):
        raise InputError("The operational reference contains no explicit values for the source-mapped comparable field(s).")

    reference_index = build_activity_operational_index(reference_rows)
    results = validate_operational_export_rows(eligible_rows, reference_index)
    return {
        "operational_reference_results": results,
        "operational_reference_metadata": build_operational_reference_metadata(name, data, revision),
        "operational_reference_fields": list(field for field in _OPERATIONAL_FIELDS if field in overlap),
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


def _operational_panel(token: str, session: dict[str, Any]) -> str:
    if "audit_sheets" not in session:
        return ""
    source_fields = _source_operational_fields(session)
    if not source_fields:
        return (
            "<section class='card' id='operational-references'><h2>Operational Activity evidence</h2>"
            "<p>Not available for this audit. To compare governed Crew Code / Production Rate evidence, the source audit must explicitly map Activity plus Crew Code and/or Production Rate on the same included sheet. No crew or production value is inferred.</p>"
            "</section>"
        )

    action = f"/references?token={quote(token, safe='')}"
    source_label = ", ".join("Crew Code" if field == "crew_code" else "Production Rate" for field in source_fields)
    form = f"""<form action='{action}' method='post' enctype='multipart/form-data'>
<p><label>Operational Activity reference CSV <input type='file' name='operational_reference' accept='.csv' required></label><br>
<label>Operational reference revision / label <input type='text' name='operational_revision' maxlength='200' placeholder='Optional; not inferred'></label></p>
<p><button type='submit'>Compare explicit operational evidence</button></p></form>"""
    results = session.get("operational_reference_results")
    metadata = session.get("operational_reference_metadata")
    if not results:
        return f"""<section class='card' id='operational-references'><h2>Operational Activity evidence</h2>
<p>Optional, evidence-only. This audit explicitly maps <strong>{html.escape(source_label)}</strong> with Activity. Supply a governed Activity CSV containing <code>activity_code</code> plus the corresponding <code>crew_code</code> and/or <code>production_rate</code>. Only fields explicitly present on both sides are compared.</p>
<p>No crew design, production calculation, replacement value, pricing authority, estimator approval, bid-readiness judgement, or HeavyBid import validation is performed.</p>
<div class='notice'><strong>Package boundary:</strong> operational evidence is temporary-session UI evidence only. It is not included in review-package v1, archived continuation, Review Delta, or the existing reference-check CSV.</div>
{form}</section>"""

    counts = Counter(item.get("status", "") for item in results)
    summary = " | ".join(f"{status}: {counts.get(status, 0)}" for status in OPERATIONAL_STATUSES)
    fields = session.get("operational_reference_fields", [])
    field_label = ", ".join("Crew Code" if field == "crew_code" else "Production Rate" for field in fields) or "none"
    rows = "".join(
        "<tr>"
        f"<td class='{html.escape(str(item.get('status', '')))}'>{html.escape(str(item.get('status', '')))}</td>"
        f"<td>{html.escape(str(item.get('sheet', '')))}</td>"
        f"<td>{html.escape(str(item.get('source_row', '')))}</td>"
        f"<td>{html.escape(str(item.get('activity_code', '')))}</td>"
        f"<td>{html.escape(str(item.get('reference_activity_code', '')))}</td>"
        f"<td>{html.escape(str(item.get('crew_code', '')))}</td>"
        f"<td>{html.escape(str(item.get('reference_crew_code', '')))}</td>"
        f"<td>{html.escape(str(item.get('production_rate', '')))}</td>"
        f"<td>{html.escape(str(item.get('reference_production_rate', '')))}</td>"
        f"<td>{html.escape(str(item.get('message', '')))}</td>"
        "</tr>"
        for item in results
    ) or "<tr><td colspan='10'>No operational rows were comparable.</td></tr>"
    metadata_html = _metadata_table([metadata] if isinstance(metadata, dict) else [])
    return f"""<section class='card' id='operational-references'><h2>Operational Activity evidence</h2>
<p><strong>Compared explicit fields:</strong> {html.escape(field_label)}<br><strong>Results:</strong> {html.escape(summary)}</p>
<p>Statuses describe row-linked evidence only. A match does not establish that the reference is approved/current, that the crew or production value is correct, or that the estimate is ready for HeavyBid import.</p>
{metadata_html}
<div class='notice'><strong>Package boundary:</strong> operational evidence is temporary-session UI evidence only. It is not included in review-package v1, archived continuation, Review Delta, or the existing reference-check CSV.</div>
<div style='overflow:auto'><table><caption>Explicit Crew Code / Production Rate evidence</caption><thead><tr><th>Status</th><th>Sheet</th><th>Row</th><th>Activity</th><th>Reference activity</th><th>Source crew</th><th>Reference crew</th><th>Source production</th><th>Reference production</th><th>Message</th></tr></thead><tbody>{rows}</tbody></table></div>
<h3>Replace / rerun operational reference</h3>{form}</section>"""


def reference_panel(
    token: str,
    session: dict[str, Any],
    view: dict[str, str] | None = None,
    preserve: dict[str, str] | None = None,
) -> str:
    """Render code/unit references plus separate session-only operational evidence."""
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
        regular_html = (
            "<section class='card'><h2>Governed reference validation</h2>"
            "<p>Optional. Upload an explicitly selected Activity and/or Resource reference CSV. Required columns are "
            "<code>activity_code,unit</code> or <code>resource_code,unit</code>. Revision/label is recorded exactly as supplied and may be blank. "
            "The app does not infer reference authority, replacement codes, or unit conversions.</p>"
            f"{upload_form}</section>"
        )
        return regular_html + _operational_panel(token, session)

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
    regular_html = f"""<section class='card'><h2>Governed reference validation</h2>
<p><strong>Results:</strong> {html.escape(summary)}</p>
<p>Checks use only the explicitly uploaded reference files for this temporary session. A match and a recorded hash do not establish authority or HeavyBid import approval.</p>
{metadata_html}
{controls}
<p><a class='button' href='/export/references?token={html.escape(token, quote=True)}'>Download reference checks CSV</a></p>
<div style='overflow:auto'><table><caption>Visible governed reference checks</caption><thead><tr><th>Status</th><th>Type</th><th>Sheet</th><th>Row</th><th>Source code</th><th>Reference code</th><th>Reference unit</th><th>Message</th></tr></thead><tbody>{rows}</tbody></table></div>
<h3>Replace / rerun references</h3>{upload_form}</section>"""
    return regular_html + _operational_panel(token, session)
