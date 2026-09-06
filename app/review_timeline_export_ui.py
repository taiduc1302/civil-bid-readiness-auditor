"""Request-local browser distribution for verified Review Timeline evidence exports."""
from __future__ import annotations

import html
from http import HTTPStatus
from urllib.parse import urlparse

import server_legacy as _server
from review_delta_export import MAX_DELTA_EXPORT_BYTES
from review_timeline import MAX_TIMELINE_DELTAS, MIN_TIMELINE_DELTAS
from review_timeline_export import build_review_timeline_export, verify_review_timeline_export
from review_timeline_ui import TIMELINE_MAX_REQUEST_BYTES, _read_delta_exports, _timeline_multipart_message

EXPORT_ROUTE = "/export-review-timeline"


def timeline_export_page_body(error: str = "") -> str:
    alert = (
        f"<div class='error'><strong>Timeline export failed.</strong> {html.escape(error)}</div>"
        if error
        else ""
    )
    per_bundle_mib = MAX_DELTA_EXPORT_BYTES // (1024 * 1024)
    aggregate_mib = TIMELINE_MAX_REQUEST_BYTES // (1024 * 1024)
    return f"""{alert}
<section class='card'>
<h2>Download Review Timeline evidence export</h2>
<div class='notice'><strong>Fresh verification required.</strong> Select the Delta evidence ZIPs again on this page. No uploads, verified flags, preview model, package identity, or lineage state are carried from Review Timeline or another route.</div>
<p>The browser sends the selected {MIN_TIMELINE_DELTAS}–{MAX_TIMELINE_DELTAS} Delta v1 ZIPs only for this request. Every Delta is independently verified, one connected acyclic package-SHA-256 chain is reconstructed, the deterministic Timeline export is built, and that generated ZIP is independently verified again before download.</p>
<form action='{EXPORT_ROUTE}' method='post' enctype='multipart/form-data'>
<p><label>Review Delta evidence ZIPs <input type='file' name='delta_export' accept='.zip,application/zip' multiple required></label></p>
<p><button type='submit'>Download verified Timeline evidence ZIP</button> <a href='/review-timeline'>Back to Review Timeline</a></p>
</form>
<p class='visually-helpful'>Choose {MIN_TIMELINE_DELTAS}–{MAX_TIMELINE_DELTAS} Delta evidence ZIPs. Each Delta remains limited to {per_bundle_mib} MB compressed and this dedicated multipart request is limited to {aggregate_mib} MB including form overhead.</p>
<p class='visually-helpful'>Evidence chronology only. This route creates no review session or persistent timeline, restores no source files, reruns no audit/reference logic, reconstructs no Operational Crew/Production evidence, generates no narrative or trend/readiness score, performs no HeavyBid write/import action, and preserves HEAVYBID_IMPORT_VALIDATED=false.</p>
</section>"""


def install_review_timeline_export_ui() -> None:
    if getattr(_server, "_review_timeline_export_ui_installed", False):
        return

    original_home = _server.home
    original_get = _server.Handler.do_GET
    original_post = _server.Handler.do_POST

    def home(message: str = "") -> bytes:
        content = original_home(message)
        extra = b"""
<section class='card'><h2>Review Timeline evidence export</h2><p>Build a deterministic portable Timeline evidence ZIP from freshly re-selected and independently verified Review Delta bundles. No Timeline preview state is carried into export creation.</p><p><a class='button' href='/export-review-timeline'>Open Timeline export</a></p></section>
"""
        return content.replace(b"</main>", extra + b"</main>", 1)

    def do_get(self: _server.BaseHTTPRequestHandler) -> None:
        if urlparse(self.path).path == EXPORT_ROUTE:
            self.send_html(_server.page("Review Timeline export", timeline_export_page_body()))
            return
        original_get(self)

    def do_post(self: _server.BaseHTTPRequestHandler) -> None:
        if urlparse(self.path).path != EXPORT_ROUTE:
            original_post(self)
            return
        try:
            message = _timeline_multipart_message(self)
            uploads = _read_delta_exports(message)
            content, filename = build_review_timeline_export(uploads)
            verified = verify_review_timeline_export(content)
            if verified.get("valid") is not True or verified.get("heavybid_import_validated") is not False:
                raise ValueError("Generated Review Timeline export failed the distribution safety gate.")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except (_server.InputError, ValueError) as exc:
            self.send_html(
                _server.page("Review Timeline export", timeline_export_page_body(error=str(exc))),
                HTTPStatus.BAD_REQUEST,
            )

    _server.home = home
    _server.Handler.do_GET = do_get
    _server.Handler.do_POST = do_post
    _server._review_timeline_export_ui_installed = True
