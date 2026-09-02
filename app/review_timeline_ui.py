"""Read-only local UI for a verified linear chain of Review Delta evidence bundles."""
from __future__ import annotations

import html
from email import policy
from email.parser import BytesParser
from http import HTTPStatus
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import server_legacy as _server
from review_delta_export import MAX_DELTA_EXPORT_BYTES
from review_timeline import MAX_TIMELINE_DELTAS, MIN_TIMELINE_DELTAS, build_review_timeline

TIMELINE_MULTIPART_OVERHEAD_BYTES = 2 * 1024 * 1024
TIMELINE_MAX_REQUEST_BYTES = (
    MAX_TIMELINE_DELTAS * MAX_DELTA_EXPORT_BYTES + TIMELINE_MULTIPART_OVERHEAD_BYTES
)
MAX_TIMELINE_DETAIL_CELL_CHARS = 500


def _timeline_multipart_message(handler: Any):
    """Parse a bounded multi-bundle request without inheriting the legacy 26 MB cap."""
    content_type = handler.headers.get("Content-Type", "")
    if not content_type.startswith("multipart/form-data"):
        raise _server.InputError("Upload request must use multipart form data.")
    try:
        length = int(handler.headers.get("Content-Length", "0") or "0")
    except (TypeError, ValueError) as exc:
        raise _server.InputError("Upload request has an invalid Content-Length.") from exc
    if length <= 0 or length > TIMELINE_MAX_REQUEST_BYTES:
        max_mib = TIMELINE_MAX_REQUEST_BYTES // (1024 * 1024)
        raise _server.InputError(
            f"Review Timeline upload request is empty or exceeds the local {max_mib} MB aggregate request limit."
        )
    raw = handler.rfile.read(length)
    if len(raw) != length:
        raise _server.InputError("Review Timeline upload request ended before its declared Content-Length.")
    try:
        message = BytesParser(policy=policy.default).parsebytes(
            f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode() + raw
        )
    except Exception as exc:
        raise _server.InputError("Upload request contains malformed multipart form data.") from exc
    if not message.is_multipart():
        raise _server.InputError("Upload request contains malformed multipart form data.")
    return message


def _read_delta_exports(message: Any) -> list[tuple[str, bytes]]:
    uploads: list[tuple[str, bytes]] = []
    for part in message.iter_parts():
        if part.get_content_disposition() != "form-data":
            continue
        if part.get_param("name", header="content-disposition") != "delta_export":
            continue
        filename = part.get_filename()
        if not filename:
            continue
        safe_name = Path(filename).name
        if Path(safe_name).suffix.casefold() != ".zip":
            raise _server.InputError("Every Review Timeline input must be a Delta evidence ZIP.")
        payload = part.get_payload(decode=True)
        if payload is None:
            content = part.get_content()
            payload = content.encode(part.get_content_charset() or "utf-8") if isinstance(content, str) else bytes(content)
        if not payload:
            raise _server.InputError("Review Timeline Delta evidence ZIPs cannot be blank.")
        if len(payload) > MAX_DELTA_EXPORT_BYTES:
            max_mib = MAX_DELTA_EXPORT_BYTES // (1024 * 1024)
            raise _server.InputError(
                f"Each Review Timeline Delta evidence ZIP must be at most {max_mib} MB."
            )
        uploads.append((safe_name, bytes(payload)))
    if len(uploads) < MIN_TIMELINE_DELTAS:
        raise _server.InputError(f"Choose at least {MIN_TIMELINE_DELTAS} Review Delta evidence ZIPs.")
    if len(uploads) > MAX_TIMELINE_DELTAS:
        raise _server.InputError(f"Choose at most {MAX_TIMELINE_DELTAS} Review Delta evidence ZIPs.")
    return uploads


def _counts(counts: dict[str, Any], keys: tuple[str, ...]) -> str:
    return " | ".join(f"{key}: {int(counts.get(key, 0))}" for key in keys)


def _cell(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        text = ", ".join(str(item) for item in value)
    elif value is None:
        text = ""
    else:
        text = str(value)
    if len(text) > MAX_TIMELINE_DETAIL_CELL_CHARS:
        text = text[: MAX_TIMELINE_DETAIL_CELL_CHARS - 1] + "…"
    return html.escape(text)


def _pair_summary(value: Any, fields: tuple[str, ...]) -> str:
    item = value if isinstance(value, dict) else {}
    parts = [f"{field}={item.get(field, '')}" for field in fields if item.get(field, "") not in (None, "")]
    return _cell("; ".join(parts) or "—")


def _detail_note(category: dict[str, Any], label: str) -> str:
    shown = int(category.get("shown", 0))
    total = int(category.get("changed_total", 0))
    omitted = int(category.get("omitted", 0))
    if omitted:
        return (
            f"<p class='visually-helpful'>Showing {shown} of {total} verified changed {html.escape(label)} rows; "
            f"{omitted} additional verified changed rows are omitted from this browser preview.</p>"
        )
    return f"<p class='visually-helpful'>Showing all {shown} verified changed {html.escape(label)} rows.</p>"


def _finding_detail_table(category: dict[str, Any]) -> str:
    rows = category.get("rows", [])
    if not rows:
        table = "<p>No changed finding rows are present in this verified transition.</p>"
    else:
        body = "".join(
            "<tr>"
            f"<td>{_cell(item.get('change_type', ''))}</td>"
            f"<td>{_cell((item.get('anchor') or {}).get('sheet', ''))}</td>"
            f"<td>{_cell((item.get('anchor') or {}).get('row', ''))}</td>"
            f"<td>{_cell((item.get('anchor') or {}).get('rule_id', ''))}</td>"
            f"<td>{_cell((item.get('anchor') or {}).get('field', ''))}</td>"
            f"<td>{_cell(item.get('evidence_fields_changed', []))}</td>"
            f"<td>{_cell(item.get('review_fields_changed', []))}</td>"
            f"<td>{_pair_summary(item.get('before'), ('severity', 'evidence', 'message'))}</td>"
            f"<td>{_pair_summary(item.get('after'), ('severity', 'evidence', 'message'))}</td>"
            f"<td>{_pair_summary(item.get('before_review'), ('status', 'reason'))}</td>"
            f"<td>{_pair_summary(item.get('after_review'), ('status', 'reason'))}</td>"
            "</tr>"
            for item in rows
        )
        table = (
            "<div style='overflow:auto'><table><caption>Changed finding evidence from the verified Delta bundle</caption>"
            "<thead><tr><th>Change</th><th>Sheet</th><th>Row</th><th>Rule</th><th>Field</th>"
            "<th>Evidence fields changed</th><th>Review fields changed</th><th>Before evidence</th><th>After evidence</th>"
            f"<th>Before review</th><th>After review</th></tr></thead><tbody>{body}</tbody></table></div>"
        )
    return table + _detail_note(category, "finding")


def _reference_detail_table(category: dict[str, Any]) -> str:
    rows = category.get("rows", [])
    if not rows:
        table = "<p>No changed governed-reference rows are present in this verified transition.</p>"
    else:
        body = "".join(
            "<tr>"
            f"<td>{_cell(item.get('change_type', ''))}</td>"
            f"<td>{_cell((item.get('anchor') or {}).get('reference_type', ''))}</td>"
            f"<td>{_cell((item.get('anchor') or {}).get('sheet', ''))}</td>"
            f"<td>{_cell((item.get('anchor') or {}).get('source_row', ''))}</td>"
            f"<td>{_cell((item.get('anchor') or {}).get('code', ''))}</td>"
            f"<td>{_cell(item.get('fields_changed', []))}</td>"
            f"<td>{_pair_summary(item.get('before'), ('status', 'reference_code', 'reference_unit', 'message'))}</td>"
            f"<td>{_pair_summary(item.get('after'), ('status', 'reference_code', 'reference_unit', 'message'))}</td>"
            "</tr>"
            for item in rows
        )
        table = (
            "<div style='overflow:auto'><table><caption>Changed governed-reference evidence from the verified Delta bundle</caption>"
            "<thead><tr><th>Change</th><th>Type</th><th>Sheet</th><th>Row</th><th>Code</th><th>Fields changed</th>"
            f"<th>Before</th><th>After</th></tr></thead><tbody>{body}</tbody></table></div>"
        )
    return table + _detail_note(category, "reference")


def _metadata_detail_table(category: dict[str, Any]) -> str:
    rows = category.get("rows", [])
    if not rows:
        table = "<p>No changed reference-metadata rows are present in this verified transition.</p>"
    else:
        body = "".join(
            "<tr>"
            f"<td>{_cell(item.get('change_type', ''))}</td>"
            f"<td>{_cell(item.get('role', ''))}</td>"
            f"<td>{_cell(item.get('fields_changed', []))}</td>"
            f"<td>{_pair_summary(item.get('before'), ('filename', 'revision', 'size_bytes', 'sha256', 'authority_status'))}</td>"
            f"<td>{_pair_summary(item.get('after'), ('filename', 'revision', 'size_bytes', 'sha256', 'authority_status'))}</td>"
            "</tr>"
            for item in rows
        )
        table = (
            "<div style='overflow:auto'><table><caption>Changed reference metadata from the verified Delta bundle</caption>"
            "<thead><tr><th>Change</th><th>Role</th><th>Fields changed</th><th>Before</th><th>After</th></tr></thead>"
            f"<tbody>{body}</tbody></table></div>"
        )
    return table + _detail_note(category, "reference metadata")


def _transition_details(item: dict[str, Any], index: int) -> str:
    preview = item.get("detail_preview") if isinstance(item.get("detail_preview"), dict) else {}
    return f"""<details class='card'>
<summary><strong>Transition {index}</strong> — {_cell(item.get('delta_filename', ''))} — bounded verified evidence details</summary>
<div class='notice'><strong>Evidence details only.</strong> Rows below come only from the already verified Delta preview. They do not imply improvement, regression, correctness, approval, bid readiness, or HeavyBid import validity.</div>
<h4>Finding changes</h4>
{_finding_detail_table(preview.get('finding_changes', {}))}
<h4>Governed-reference changes</h4>
{_reference_detail_table(preview.get('reference_changes', {}))}
<h4>Reference-metadata changes</h4>
{_metadata_detail_table(preview.get('reference_metadata_changes', {}))}
</details>"""


def timeline_page_body(result: dict[str, Any] | None = None, error: str = "") -> str:
    alert = f"<div class='error'><strong>Timeline failed.</strong> {html.escape(error)}</div>" if error else ""
    output = ""
    if result:
        snapshot_rows = "".join(
            "<tr>"
            f"<td>{index}</td>"
            f"<td><code>{html.escape(str(item['package_sha256']))}</code></td>"
            f"<td>{html.escape(', '.join(item.get('package_filename_aliases', [])) or '(no recorded alias)')}</td>"
            f"<td>{html.escape(str(item.get('source_filename', '')))}</td>"
            f"<td>{html.escape(str(item.get('rows_reviewed', '')))}</td>"
            f"<td>{html.escape(str(item.get('source_session_mode', '')))}</td>"
            "</tr>"
            for index, item in enumerate(result["snapshots"], start=1)
        )
        transition_rows = "".join(
            "<tr>"
            f"<td>{index}</td>"
            f"<td>{html.escape(str(item.get('delta_filename', '')))}</td>"
            f"<td><code>{html.escape(str(item.get('delta_sha256', '')))}</code></td>"
            f"<td>{html.escape(_counts(item.get('finding_counts', {}), ('ADDED','REMOVED','EVIDENCE_CHANGED','REVIEW_CHANGED','EVIDENCE_AND_REVIEW_CHANGED','UNCHANGED')))}</td>"
            f"<td>{html.escape(_counts(item.get('reference_counts', {}), ('ADDED','REMOVED','CHANGED','UNCHANGED')))}</td>"
            f"<td>{html.escape(_counts(item.get('reference_metadata_counts', {}), ('ADDED','REMOVED','CHANGED','UNCHANGED')))}</td>"
            "</tr>"
            for index, item in enumerate(result["transitions"], start=1)
        )
        detail_blocks = "".join(
            _transition_details(item, index)
            for index, item in enumerate(result["transitions"], start=1)
        )
        source_notice = ""
        if not result.get("same_source_filename_across_chain"):
            source_notice = (
                "<div class='notice'><strong>Source filenames differ across snapshots.</strong> "
                "Package-SHA continuity is still structurally verified, but the timeline does not infer why source naming changed.</div>"
            )
        output = f"""<section class='card' id='review-timeline-result'>
<h2>Review Timeline evidence chain</h2>
<div class='notice'><strong>Transition chronology only.</strong> The chain is ordered by exact review-package SHA-256 continuity. It does not infer calendar dates, source currency, estimate quality, improvement/regression, approval, bid readiness, or HeavyBid import validity.</div>
{source_notice}
<p><strong>Snapshots:</strong> {result['snapshot_count']} | <strong>Transitions:</strong> {result['delta_bundle_count']} | <strong>Continuity:</strong> exact package SHA-256 chain verified</p>
<h3>Ordered snapshots</h3>
<div style='overflow:auto'><table><caption>Structurally ordered review-package snapshot chain</caption><thead><tr><th>#</th><th>Package SHA-256</th><th>Recorded package filename alias(es)</th><th>Source filename</th><th>Rows reviewed</th><th>Source session mode</th></tr></thead><tbody>{snapshot_rows}</tbody></table></div>
<h3>Ordered evidence transitions</h3>
<div style='overflow:auto'><table><caption>Per-transition archived evidence counts; counts are descriptive, not a trend score</caption><thead><tr><th>#</th><th>Delta bundle</th><th>Delta SHA-256</th><th>Finding changes</th><th>Reference changes</th><th>Reference metadata changes</th></tr></thead><tbody>{transition_rows}</tbody></table></div>
<h3>Bounded transition evidence details</h3>
<p class='visually-helpful'>UNCHANGED rows remain represented in the verified count table above but are intentionally omitted from the detail previews below. Omission is a display choice only and is not an improvement judgement.</p>
{detail_blocks}
<p class='visually-helpful'>Every input Delta bundle was independently verified before chain construction. The model creates no review session, reruns no audit/reference logic, and does not reconstruct session-only Operational Crew/Production evidence.</p>
</section>"""

    max_bundle_mib = MAX_DELTA_EXPORT_BYTES // (1024 * 1024)
    max_request_mib = TIMELINE_MAX_REQUEST_BYTES // (1024 * 1024)
    return f"""{alert}{output}
<section class='card'>
<h2>Build Review Timeline</h2>
<p>Select {MIN_TIMELINE_DELTAS}–{MAX_TIMELINE_DELTAS} portable Review Delta evidence ZIPs. Upload order does not control the result: the app verifies every bundle and reconstructs one linear chain only from exact Earlier/Later review-package SHA-256 continuity.</p>
<p class='visually-helpful'>Each Delta evidence ZIP is limited to {max_bundle_mib} MB. The full multipart request is bounded to {max_request_mib} MB including form overhead.</p>
<form action='/review-timeline' method='post' enctype='multipart/form-data'>
<p><label>Review Delta evidence ZIPs <input type='file' name='delta_export' accept='.zip,application/zip' multiple required></label></p>
<p><button type='submit'>Build evidence timeline</button> <a href='/verify-review-delta'>Verify one Delta bundle</a> <a href='/compare-review-packages'>Review Delta</a> <a href='/'>Home</a></p>
</form>
<p class='visually-helpful'>This is not a quality trend. Branching, merging, cyclic, duplicate, disconnected, or semantically conflicting lineage fails closed.</p>
</section>"""


def install_review_timeline_ui() -> None:
    if getattr(_server, "_review_timeline_ui_installed", False):
        return
    original_home = _server.home
    original_get = _server.Handler.do_GET
    original_post = _server.Handler.do_POST

    def home(message: str = "") -> bytes:
        content = original_home(message)
        extra = b"""
<section class='card'><h2>Review Timeline</h2><p>Build a neutral multi-snapshot evidence chain from 2-10 independently verified Review Delta bundles. Ordering uses exact review-package SHA-256 continuity, not inferred dates or quality.</p><p><a class='button' href='/review-timeline'>Open Review Timeline</a></p></section>
"""
        return content.replace(b"</main>", extra + b"</main>", 1)

    def do_get(self: _server.BaseHTTPRequestHandler) -> None:
        if urlparse(self.path).path == "/review-timeline":
            self.send_html(_server.page("Review Timeline", timeline_page_body()))
            return
        original_get(self)

    def do_post(self: _server.BaseHTTPRequestHandler) -> None:
        if urlparse(self.path).path != "/review-timeline":
            original_post(self)
            return
        try:
            message = _timeline_multipart_message(self)
            uploads = _read_delta_exports(message)
            result = build_review_timeline(uploads)
            self.send_html(_server.page("Review Timeline", timeline_page_body(result=result)))
        except (_server.InputError, ValueError) as exc:
            self.send_html(_server.page("Review Timeline", timeline_page_body(error=str(exc))), HTTPStatus.BAD_REQUEST)

    _server.home = home
    _server.Handler.do_GET = do_get
    _server.Handler.do_POST = do_post
    _server._review_timeline_ui_installed = True
