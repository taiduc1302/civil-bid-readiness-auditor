"""Local read-only UI for comparing two verified review-package snapshots."""
from __future__ import annotations

import html
from http import HTTPStatus
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import server_legacy as _server
from review_delta import compare_review_packages
from review_delta_export import build_review_delta_export

MAX_DETAIL_ROWS = 200


def _read_pair(message: Any) -> tuple[tuple[str, bytes], tuple[str, bytes]]:
    found: dict[str, tuple[str, bytes]] = {}
    for part in message.iter_parts():
        if part.get_content_disposition() != "form-data":
            continue
        field = part.get_param("name", header="content-disposition")
        if field not in ("earlier_package", "later_package"):
            continue
        filename = part.get_filename()
        if not filename:
            continue
        if field in found:
            raise _server.InputError(f"Choose exactly one {field.replace('_', ' ')} ZIP.")
        payload = part.get_payload(decode=True)
        if payload is None:
            content = part.get_content()
            payload = content.encode(part.get_content_charset() or "utf-8") if isinstance(content, str) else bytes(content)
        safe_name = Path(filename).name
        if Path(safe_name).suffix.casefold() != ".zip":
            raise _server.InputError("Both Review Delta inputs must be ZIP files.")
        if not payload:
            raise _server.InputError("Review Delta package uploads cannot be blank.")
        found[field] = (safe_name, bytes(payload))
    if "earlier_package" not in found or "later_package" not in found:
        raise _server.InputError("Choose both an Earlier and a Later review-package ZIP.")
    return found["earlier_package"], found["later_package"]


def delta_page_body(result: dict[str, Any] | None = None, error: str = "") -> str:
    alert = f"<div class='error'><strong>Comparison failed.</strong> {html.escape(error)}</div>" if error else ""
    output = ""
    if result:
        fc = result["finding_counts"]
        rc = result["reference_counts"]
        mc = result["reference_metadata_counts"]
        source_notice = ""
        if not result.get("same_source_filename"):
            source_notice = "<div class='notice'><strong>Different source filenames.</strong> These snapshots may represent different estimate sources. The comparison remains descriptive only.</div>"

        finding_changes = [item for item in result["finding_changes"] if item["change_type"] != "UNCHANGED"][:MAX_DETAIL_ROWS]
        finding_rows = "".join(
            "<tr>"
            f"<td>{html.escape(item['change_type'])}</td>"
            f"<td>{html.escape(str(item['anchor']['sheet']))}</td>"
            f"<td>{html.escape(str(item['anchor']['row']))}</td>"
            f"<td>{html.escape(str(item['anchor']['rule_id']))}</td>"
            f"<td>{html.escape(str(item['anchor']['field']))}</td>"
            f"<td>{html.escape(', '.join(item['evidence_fields_changed']) or '—')}</td>"
            f"<td>{html.escape(', '.join(item['review_fields_changed']) or '—')}</td>"
            f"<td>{html.escape(str((item.get('before_review') or {}).get('status', '—')))} → {html.escape(str((item.get('after_review') or {}).get('status', '—')))}</td>"
            "</tr>" for item in finding_changes
        ) or "<tr><td colspan='8'>No changed finding anchors.</td></tr>"

        reference_changes = [item for item in result["reference_changes"] if item["change_type"] != "UNCHANGED"][:MAX_DETAIL_ROWS]
        reference_rows = "".join(
            "<tr>"
            f"<td>{html.escape(item['change_type'])}</td>"
            f"<td>{html.escape(str(item['anchor']['reference_type']))}</td>"
            f"<td>{html.escape(str(item['anchor']['sheet']))}</td>"
            f"<td>{html.escape(str(item['anchor']['source_row']))}</td>"
            f"<td>{html.escape(str(item['anchor']['code']))}</td>"
            f"<td>{html.escape(', '.join(item['fields_changed']) or '—')}</td>"
            f"<td>{html.escape(str((item.get('before') or {}).get('status', '—')))} → {html.escape(str((item.get('after') or {}).get('status', '—')))}</td>"
            "</tr>" for item in reference_changes
        ) or "<tr><td colspan='7'>No changed reference-check anchors.</td></tr>"

        metadata_changes = [item for item in result["reference_metadata_changes"] if item["change_type"] != "UNCHANGED"]
        metadata_rows = "".join(
            "<tr>"
            f"<td>{html.escape(item['change_type'])}</td>"
            f"<td>{html.escape(item['role'])}</td>"
            f"<td>{html.escape(', '.join(item['fields_changed']) or '—')}</td>"
            f"<td>{html.escape(str((item.get('before') or {}).get('revision', '—')))}</td>"
            f"<td>{html.escape(str((item.get('after') or {}).get('revision', '—')))}</td>"
            "</tr>" for item in metadata_changes
        ) or "<tr><td colspan='5'>No reference metadata drift.</td></tr>"

        output = f"""<section class='card' id='delta-result'>
<h2>Review Delta result</h2>
<div class='notice'><strong>Evidence drift only.</strong> Fewer findings, different review states, or different reference checks do not establish improvement, correctness, approval, bid readiness, or HeavyBid import validity.</div>
{source_notice}
<p><strong>Earlier:</strong> {html.escape(result['earlier']['package_filename'])} — source {html.escape(result['earlier']['source_filename'])}<br>
<strong>Later:</strong> {html.escape(result['later']['package_filename'])} — source {html.escape(result['later']['source_filename'])}</p>
<h3>Finding delta</h3><p>Added {fc['ADDED']} | Removed {fc['REMOVED']} | Evidence changed {fc['EVIDENCE_CHANGED']} | Review changed {fc['REVIEW_CHANGED']} | Both changed {fc['EVIDENCE_AND_REVIEW_CHANGED']} | Unchanged {fc['UNCHANGED']}</p>
<div style='overflow:auto'><table><thead><tr><th>Change</th><th>Sheet</th><th>Row</th><th>Rule</th><th>Field</th><th>Evidence fields</th><th>Review fields</th><th>Review status</th></tr></thead><tbody>{finding_rows}</tbody></table></div>
<h3>Reference-check delta</h3><p>Added {rc['ADDED']} | Removed {rc['REMOVED']} | Changed {rc['CHANGED']} | Unchanged {rc['UNCHANGED']}</p>
<div style='overflow:auto'><table><thead><tr><th>Change</th><th>Type</th><th>Sheet</th><th>Row</th><th>Code</th><th>Fields</th><th>Status</th></tr></thead><tbody>{reference_rows}</tbody></table></div>
<h3>Reference snapshot metadata drift</h3><p>Added {mc['ADDED']} | Removed {mc['REMOVED']} | Changed {mc['CHANGED']} | Unchanged {mc['UNCHANGED']}</p>
<div style='overflow:auto'><table><thead><tr><th>Change</th><th>Role</th><th>Fields</th><th>Earlier revision</th><th>Later revision</th></tr></thead><tbody>{metadata_rows}</tbody></table></div>
<p class='visually-helpful'>Detail tables show at most {MAX_DETAIL_ROWS} changed rows per section. Comparison runs in memory and creates no review session. The portable evidence export re-verifies the two package uploads again and remains evidence-drift-only.</p>
</section>"""

    return f"""{alert}{output}
<section class='card'>
<h2>Compare two review snapshots</h2>
<p>Choose an earlier and later review-package ZIP. Both packages are independently re-verified before comparison or export. Review Delta compares archived evidence only; it does not rerun estimate rules.</p>
<form action='/compare-review-packages' method='post' enctype='multipart/form-data'>
<p><label>Earlier review-package ZIP <input type='file' name='earlier_package' accept='.zip,application/zip' required></label></p>
<p><label>Later review-package ZIP <input type='file' name='later_package' accept='.zip,application/zip' required></label></p>
<p><button type='submit'>Compare review snapshots</button> <button type='submit' formaction='/export-review-delta'>Download evidence bundle</button> <a href='/'>Back to home</a></p>
</form>
<p class='visually-helpful'>The evidence bundle is a separate deterministic Review Delta export, not a review package and not a restorable audit session.</p>
</section>"""


def install_review_delta_ui() -> None:
    if getattr(_server, "_review_delta_ui_installed", False):
        return
    original_home = _server.home
    original_get = _server.Handler.do_GET
    original_post = _server.Handler.do_POST

    def home(message: str = "") -> bytes:
        content = original_home(message)
        extra = b"""
<section class='card'><h2>Compare review snapshots</h2><p>See what changed between two verified review-package snapshots: deterministic finding evidence, human review states, reference checks, and reference snapshot metadata.</p><p><a class='button' href='/compare-review-packages'>Open Review Delta</a></p></section>
"""
        return content.replace(b"</main>", extra + b"</main>", 1)

    def do_get(self: _server.BaseHTTPRequestHandler) -> None:
        if urlparse(self.path).path == "/compare-review-packages":
            self.send_html(_server.page("Review Delta", delta_page_body()))
            return
        original_get(self)

    def do_post(self: _server.BaseHTTPRequestHandler) -> None:
        path = urlparse(self.path).path
        if path not in ("/compare-review-packages", "/export-review-delta"):
            original_post(self)
            return
        try:
            message = _server._multipart_message(self)
            earlier, later = _read_pair(message)
            result = compare_review_packages(earlier[0], earlier[1], later[0], later[1])
            if path == "/export-review-delta":
                content, filename = build_review_delta_export(result)
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/zip")
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return
            self.send_html(_server.page("Review Delta", delta_page_body(result=result)))
        except (_server.InputError, ValueError) as exc:
            self.send_html(_server.page("Review Delta", delta_page_body(error=str(exc))), HTTPStatus.BAD_REQUEST)

    _server.home = home
    _server.Handler.do_GET = do_get
    _server.Handler.do_POST = do_post
    _server._review_delta_ui_installed = True
