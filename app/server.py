from __future__ import annotations

import html
import secrets
import time
from email import policy
from email.parser import BytesParser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from audit_engine import InputError, OPTIONAL_FIELDS, REQUIRED_FIELDS, audit, column_map, findings_csv, management_summary_html, parse_upload
from finding_review import REVIEW_STATUSES, default_dispositions, findings_review_csv, review_metrics, set_disposition
from heavybid_adapter import PROFILE_HEAVYBID_STYLE_RESOURCE_EXPORT, detect_heavybid_style_export, map_heavybid_style_headers


HOST = "127.0.0.1"
PORT = 8765
ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "samples" / "synthetic_civil_estimate.csv"
SESSION_TTL_SECONDS = 30 * 60
SESSIONS: dict[str, dict] = {}


STYLE = """
body{font-family:Arial,sans-serif;margin:0;background:#f4f7f9;color:#17212b}main{max-width:1180px;margin:0 auto;padding:28px}.card{background:white;border:1px solid #d7e0e7;border-radius:8px;padding:18px;margin:16px 0}h1{margin-top:0}.notice{background:#fff7e1;border-left:4px solid #b7791f;padding:12px}.error{background:#ffe9e7;border-left:4px solid #c53030;padding:12px}table{border-collapse:collapse;width:100%;font-size:13px}th,td{border:1px solid #d7e0e7;padding:7px;text-align:left;vertical-align:top}th{background:#e8f0f5}input,select,button{font:inherit;padding:7px}button,.button{background:#145a7a;color:white;border:0;border-radius:4px;padding:9px 14px;text-decoration:none;display:inline-block}.Critical{background:#ffd7d2}.High{background:#ffe8cf}.Medium{background:#fff5bf}.Low{background:#eaf4ff}.metrics{display:flex;gap:12px;flex-wrap:wrap}.metric{border:1px solid #d7e0e7;border-radius:6px;padding:10px 14px;min-width:145px}.metric strong{font-size:18px}.review-control{min-width:140px}.reason{min-width:220px}
"""


def expire_sessions() -> None:
    now = time.monotonic()
    for token in [key for key, value in SESSIONS.items() if now - value["created"] > SESSION_TTL_SECONDS]:
        SESSIONS.pop(token, None)


def page(title: str, body: str) -> bytes:
    return f"<!doctype html><html><head><meta charset='utf-8'><title>{html.escape(title)}</title><style>{STYLE}</style></head><body><main><h1>{html.escape(title)}</h1>{body}</main></body></html>".encode("utf-8")


def home(message: str = "") -> bytes:
    alert = f"<div class='error'>{html.escape(message)}</div>" if message else ""
    return page("Civil Bid Readiness Auditor", f"""{alert}<div class='notice'><strong>Required human review.</strong> This tool flags deterministic data-quality prompts only. It does not validate price, quantity, scope, profitability, contract compliance, or a bid decision.</div><section class='card'><h2>Audit an estimate export</h2><p><strong>Local, deterministic review.</strong> Upload a local CSV or XLSX file. Data is held temporarily in this local process memory and is not written to disk or transmitted externally by this app.</p><form action='/prepare' method='post' enctype='multipart/form-data'><input type='file' name='estimate' accept='.csv,.xlsx' required> <button type='submit'>Prepare audit</button></form><p>Or <form action='/sample' method='post' style='display:inline'><button type='submit'>Run synthetic sample</button></form></p></section>""")


def read_uploaded_file(handler: BaseHTTPRequestHandler) -> tuple[str, bytes]:
    content_type = handler.headers.get("Content-Type", "")
    if not content_type.startswith("multipart/form-data"):
        raise InputError("Upload request must use multipart form data.")
    length = int(handler.headers.get("Content-Length", "0") or "0")
    if length <= 0 or length > 26 * 1024 * 1024:
        raise InputError("Upload request is empty or exceeds the local 26 MB request limit.")

    raw_body = handler.rfile.read(length)
    message_bytes = (
        f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8")
        + raw_body
    )
    try:
        message = BytesParser(policy=policy.default).parsebytes(message_bytes)
    except Exception as exc:
        raise InputError("Upload request contains malformed multipart form data.") from exc
    if not message.is_multipart():
        raise InputError("Upload request contains malformed multipart form data.")

    for part in message.iter_parts():
        if part.get_content_disposition() != "form-data":
            continue
        if part.get_param("name", header="content-disposition") != "estimate":
            continue
        filename = part.get_filename()
        if not filename:
            raise InputError("Choose a CSV or XLSX file before continuing.")
        payload = part.get_payload(decode=True)
        if payload is None:
            content = part.get_content()
            payload = content.encode(part.get_content_charset() or "utf-8") if isinstance(content, str) else bytes(content)
        return Path(filename).name, payload

    raise InputError("Choose a CSV or XLSX file before continuing.")


def detected_mapping(headers: list[str]) -> tuple[dict[str, str], str | None]:
    generic = column_map(headers)
    if not detect_heavybid_style_export(headers):
        return generic, None
    profile_mapping = map_heavybid_style_headers(headers)
    merged = dict(generic)
    merged.update(profile_mapping)
    return merged, PROFILE_HEAVYBID_STYLE_RESOURCE_EXPORT


def mapping_page(token: str, session: dict) -> bytes:
    blocks: list[str] = []
    for sheet, rows in session["sheets"].items():
        headers = [header for header in rows[0] if not header.startswith("__")]
        detected, profile = detected_mapping(headers)
        can_auto_include = all(detected.get(field) for field in REQUIRED_FIELDS)
        sample_rows = rows[:3]
        selects: list[str] = []
        for field in (*REQUIRED_FIELDS, *OPTIONAL_FIELDS):
            options = ["<option value=''>— not mapped —</option>"] + [f"<option value='{html.escape(header, quote=True)}'{' selected' if detected.get(field) == header else ''}>{html.escape(header)}</option>" for header in headers]
            selects.append(f"<label>{html.escape(field)}{' *' if field in REQUIRED_FIELDS else ''}<br><select name='map__{quote(sheet, safe='')}__{field}'>{''.join(options)}</select></label>")
        preview_head = "".join(f"<th>{html.escape(header)}</th>" for header in headers)
        preview_rows = "".join("<tr>" + "".join(f"<td>{html.escape(row.get(header, ''))}</td>" for header in headers) + "</tr>" for row in sample_rows)
        include = " checked" if can_auto_include else ""
        profile_note = ""
        if profile:
            profile_note = "<div class='notice'><strong>Structured resource-export profile recognized.</strong> HeavyBid-style header mapping was preselected using exact supported aliases only. Review or override every mapping before audit.</div>"
        blocks.append(f"<section class='card'><h2>Sheet: {html.escape(sheet)}</h2>{profile_note}<p><label><input type='checkbox' name='include__{quote(sheet, safe='')}' value='1'{include}> Include this sheet in the audit</label></p><p>Map fields marked * for each included sheet. Sheets such as cover pages can remain excluded. Detected columns are preselected and remain editable.</p><div style='display:flex;gap:1rem;flex-wrap:wrap'>{''.join(selects)}</div><h3>Preview (first {len(sample_rows)} rows)</h3><div style='overflow:auto'><table><thead><tr>{preview_head}</tr></thead><tbody>{preview_rows}</tbody></table></div></section>")
    return page("Map columns", f"<form action='/audit' method='post'><input type='hidden' name='token' value='{token}'>{''.join(blocks)}<p><button type='submit'>Run deterministic audit</button> <a href='/'>Cancel</a></p></form>")


def _review_row(finding: dict, state: dict[str, str]) -> str:
    finding_id = int(finding["id"])
    status_options = "".join(
        f"<option value='{html.escape(status, quote=True)}'{' selected' if state['status'] == status else ''}>{html.escape(status)}</option>"
        for status in REVIEW_STATUSES
    )
    cells = "".join(
        f"<td>{html.escape(str(finding[key]))}</td>" if key != "severity" else f"<td class='{html.escape(str(finding[key]))}'>{html.escape(str(finding[key]))}</td>"
        for key in ("severity", "rule_id", "sheet", "row", "field", "message", "evidence", "recommended_action")
    )
    return (
        "<tr>" + cells
        + f"<td><select class='review-control' name='status__{finding_id}'>{status_options}</select></td>"
        + f"<td><input class='reason' type='text' name='reason__{finding_id}' value='{html.escape(state['reason'], quote=True)}' placeholder='Reason / review note'></td>"
        + "</tr>"
    )


def findings_page(token: str, session: dict, message: str = "") -> bytes:
    result = session["result"]
    counts = result["counts"]
    metrics = result["review_metrics"]
    dispositions = session.setdefault("dispositions", default_dispositions(result))
    disposition_counts = review_metrics(result, dispositions)
    rows = "".join(
        _review_row(finding, dispositions.get(int(finding["id"]), {"status": "Open", "reason": ""}))
        for finding in result["findings"]
    ) or "<tr><td colspan='10'>No deterministic findings.</td></tr>"
    alert = f"<div class='notice'>{html.escape(message)}</div>" if message else ""
    review_summary = " | ".join(f"{html.escape(status)}: {disposition_counts[status]}" for status in REVIEW_STATUSES)
    return page("Audit results", f"""{alert}<div class='notice'><strong>{html.escape(metrics['status'])}.</strong> Deterministic review prompts only; this is not a bid certification.</div><section class='card'><div class='metrics'><div class='metric'><strong>{metrics['affected_rows']} / {result['rows_reviewed']}</strong><br>Affected rows ({metrics['affected_row_percent']}%)</div><div class='metric'><strong>{metrics['priority_rows']}</strong><br>Critical/high-priority rows</div><div class='metric'><strong>{metrics['finding_count']}</strong><br>Total findings</div><div class='metric'><strong>{result['score']}/100</strong><br>Legacy score</div></div><p><strong>Rows reviewed:</strong> {result['rows_reviewed']} &nbsp; <strong>Review-status score:</strong> {result['score']}/100 (legacy) &nbsp; <strong>Sheets:</strong> {html.escape(', '.join(result['sheets_reviewed']))}</p><p>Critical: {counts['Critical']} | High: {counts['High']} | Medium: {counts['Medium']} | Low: {counts['Low']}</p><p><strong>Human review:</strong> {review_summary}</p><p>{html.escape(result['score_explanation'])}</p><p><a class='button' href='/export/findings?token={token}'>Download findings CSV</a> <a class='button' href='/export/review?token={token}'>Download review CSV</a> <a class='button' href='/export/summary?token={token}'>Download management summary HTML</a> <a href='/'>Start another audit</a></p></section><section class='card'><h2>Findings review</h2><p>Review state is temporary and local to this session. It does not alter the original estimate, deterministic findings, severity, or score. Suppressed findings require a reason.</p><form action='/review' method='post'><input type='hidden' name='token' value='{html.escape(token, quote=True)}'><div style='overflow:auto'><table><thead><tr><th>Severity</th><th>Rule</th><th>Sheet</th><th>Row</th><th>Field</th><th>Finding</th><th>Evidence</th><th>Recommended action</th><th>Review status</th><th>Reason / note</th></tr></thead><tbody>{rows}</tbody></table></div><p><button type='submit'>Save review states</button></p></form></section>""")


class Handler(BaseHTTPRequestHandler):
    server_version = "CivilBidAuditor/0.1"

    def log_message(self, fmt: str, *args: object) -> None:
        print("[audit] " + fmt % args)

    def send_html(self, content: bytes, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self) -> None:
        expire_sessions()
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self.send_html(home())
            return
        if parsed.path.startswith("/export/"):
            token = parse_qs(parsed.query).get("token", [""])[0]
            session = SESSIONS.get(token)
            if not session or "result" not in session:
                self.send_html(home("This temporary audit session is no longer available. Upload the file again."), HTTPStatus.NOT_FOUND)
                return
            if parsed.path.endswith("findings"):
                content, filename, ctype = findings_csv(session["result"]), "bid_audit_findings.csv", "text/csv; charset=utf-8"
            elif parsed.path.endswith("review"):
                dispositions = session.setdefault("dispositions", default_dispositions(session["result"]))
                content, filename, ctype = findings_review_csv(session["result"], dispositions), "bid_audit_review.csv", "text/csv; charset=utf-8"
            elif parsed.path.endswith("summary"):
                content, filename, ctype = management_summary_html(session["result"], session["filename"]), "bid_audit_management_summary.html", "text/html; charset=utf-8"
            else:
                self.send_html(home("Unknown export."), HTTPStatus.NOT_FOUND)
                return
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return
        self.send_html(home("Page not found."), HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        expire_sessions()
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/prepare":
                uploaded_name, data = read_uploaded_file(self)
                if not uploaded_name:
                    raise InputError("Choose a CSV or XLSX file before continuing.")
                session = {"filename": Path(uploaded_name).name, "sheets": parse_upload(uploaded_name, data), "created": time.monotonic()}
                token = secrets.token_urlsafe(18)
                SESSIONS[token] = session
                self.send_html(mapping_page(token, session))
                return
            if parsed.path == "/sample":
                session = {"filename": SAMPLE.name, "sheets": parse_upload(SAMPLE.name, SAMPLE.read_bytes()), "created": time.monotonic()}
                token = secrets.token_urlsafe(18)
                SESSIONS[token] = session
                self.send_html(mapping_page(token, session))
                return
            if parsed.path == "/audit":
                length = int(self.headers.get("Content-Length", "0") or "0")
                body = self.rfile.read(length).decode("utf-8")
                form = parse_qs(body, keep_blank_values=True)
                token = form.get("token", [""])[0]
                session = SESSIONS.get(token)
                if not session:
                    raise InputError("This temporary audit session expired. Upload the file again.")
                selected: dict[str, list[dict[str, str]]] = {}
                mappings: dict[str, dict[str, str]] = {}
                for sheet, rows in session["sheets"].items():
                    encoded = quote(sheet, safe="")
                    mappings[sheet] = {}
                    for field in (*REQUIRED_FIELDS, *OPTIONAL_FIELDS):
                        value = form.get(f"map__{encoded}__{field}", [""])[0]
                        if value:
                            mappings[sheet][field] = value
                    if form.get(f"include__{encoded}", [""])[0] == "1":
                        selected[sheet] = rows
                if not selected:
                    selected = {
                        sheet: rows
                        for sheet, rows in session["sheets"].items()
                        if all(mappings.get(sheet, {}).get(field) for field in REQUIRED_FIELDS)
                    }
                if not selected:
                    raise InputError("Select at least one sheet with all required mappings.")
                session["result"] = audit(selected, mappings)
                session["dispositions"] = default_dispositions(session["result"])
                self.send_html(findings_page(token, session))
                return
            if parsed.path == "/review":
                length = int(self.headers.get("Content-Length", "0") or "0")
                body = self.rfile.read(length).decode("utf-8")
                form = parse_qs(body, keep_blank_values=True)
                token = form.get("token", [""])[0]
                session = SESSIONS.get(token)
                if not session or "result" not in session:
                    raise InputError("This temporary audit session expired. Upload the file again.")
                dispositions = session.setdefault("dispositions", default_dispositions(session["result"]))
                pending = {finding_id: dict(state) for finding_id, state in dispositions.items()}
                for finding in session["result"]["findings"]:
                    finding_id = int(finding["id"])
                    status = form.get(f"status__{finding_id}", [pending[finding_id]["status"]])[0]
                    reason = form.get(f"reason__{finding_id}", [pending[finding_id]["reason"]])[0]
                    set_disposition(pending, finding_id, status, reason)
                session["dispositions"] = pending
                self.send_html(findings_page(token, session, "Review states saved for this temporary local session."))
                return
        except (InputError, ValueError) as exc:
            self.send_html(home(str(exc)), HTTPStatus.BAD_REQUEST)
            return
        self.send_html(home("Page not found."), HTTPStatus.NOT_FOUND)


def run() -> None:
    print(f"Civil Bid Readiness Auditor running at http://{HOST}:{PORT}")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    run()
