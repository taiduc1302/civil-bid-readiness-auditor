"""Read-only local UI for a verified linear chain of Review Delta evidence bundles."""
from __future__ import annotations

import html
from http import HTTPStatus
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import server_legacy as _server
from review_timeline import MAX_TIMELINE_DELTAS, MIN_TIMELINE_DELTAS, build_review_timeline


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
        uploads.append((safe_name, bytes(payload)))
    if len(uploads) < MIN_TIMELINE_DELTAS:
        raise _server.InputError(f"Choose at least {MIN_TIMELINE_DELTAS} Review Delta evidence ZIPs.")
    if len(uploads) > MAX_TIMELINE_DELTAS:
        raise _server.InputError(f"Choose at most {MAX_TIMELINE_DELTAS} Review Delta evidence ZIPs.")
    return uploads


def _counts(counts: dict[str, Any], keys: tuple[str, ...]) -> str:
    return " | ".join(f"{key}: {int(counts.get(key, 0))}" for key in keys)


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
<p class='visually-helpful'>Every input Delta bundle was independently verified before chain construction. The model creates no review session, reruns no audit/reference logic, and does not reconstruct session-only Operational Crew/Production evidence.</p>
</section>"""

    return f"""{alert}{output}
<section class='card'>
<h2>Build Review Timeline</h2>
<p>Select {MIN_TIMELINE_DELTAS}–{MAX_TIMELINE_DELTAS} portable Review Delta evidence ZIPs. Upload order does not control the result: the app verifies every bundle and reconstructs one linear chain only from exact Earlier/Later review-package SHA-256 continuity.</p>
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
            message = _server._multipart_message(self)
            uploads = _read_delta_exports(message)
            result = build_review_timeline(uploads)
            self.send_html(_server.page("Review Timeline", timeline_page_body(result=result)))
        except (_server.InputError, ValueError) as exc:
            self.send_html(_server.page("Review Timeline", timeline_page_body(error=str(exc))), HTTPStatus.BAD_REQUEST)

    _server.home = home
    _server.Handler.do_GET = do_get
    _server.Handler.do_POST = do_post
    _server._review_timeline_ui_installed = True
