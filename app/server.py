from __future__ import annotations

import cgi
import html
import secrets
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

from audit_engine import InputError, OPTIONAL_FIELDS, REQUIRED_FIELDS, audit, column_map, findings_csv, management_summary_html, parse_upload


HOST = "127.0.0.1"
PORT = 8765
ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "samples" / "synthetic_civil_estimate.csv"
SESSION_TTL_SECONDS = 30 * 60
SESSIONS: dict[str, dict] = {}


STYLE = """
body{font-family:Arial,sans-serif;margin:0;background:#f4f7f9;color:#17212b}main{max-width:1180px;margin:0 auto;padding:28px}.card{background:white;border:1px solid #d7e0e7;border-radius:8px;padding:18px;margin:16px 0}h1{margin-top:0}.notice{background:#fff7e1;border-left:4px solid #b7791f;padding:12px}.error{background:#ffe9e7;border-left:4px solid #c53030;padding:12px}table{border-collapse:collapse;width:100%;font-size:13px}th,td{border:1px solid #d7e0e7;padding:7px;text-align:left;vertical-align:top}th{background:#e8f0f5}input,select,button{font:inherit;padding:7px}button,.button{background:#145a7a;color:white;border:0;border-radius:4px;padding:9px 14px;text-decoration:none;display:inline-block}.Critical{background:#ffd7d2}.High{background:#ffe8cf}.Medium{background:#fff5bf}.Low{background:#eaf4ff}.metrics{display:flex;gap:12px;flex-wrap:wrap}.metric{border:1px solid #d7e0e7;border-radius:6px;padding:10px 14px;min-width:145px}.metric strong{font-size:18px}
"""


def expire_sessions() -> None:
    now = time.monotonic()
    for token in [key for key, value in SESSIONS.items() if now - value["created"] > SESSION_TTL_SECONDS]:
        SESSIONS.pop(token, None)


def page(title: str, body: str) -> bytes:
    return f"<!doctype html><html><head><meta charset='utf-8'><title>{html.escape(title)}</title><style>{STYLE}</style></head><body><main><h1>{html.escape(title)}</h1>{body}</main></body></html>".encode("utf-8")


def home(message: str = "") -> bytes:
    alert = f"<div class='error'>{html.escape(message)}</div>" if message else ""
    return page("Civil Bid Readiness Auditor", f"""{alert}<div class='notice'><strong>Required human review.</strong> This tool flags deterministic data-quality prompts only. It does not validate price, quantity, scope, profitability, contract compliance, or a bid decision.</div><section class='card'><h2>Audit an estimate export</h2><p>Upload a local CSV or XLSX file. Data is held temporarily in this local process memory and is not written to disk or transmitted externally by this app.</p><form action='/prepare' method='post' enctype='multipart/form-data'><input type='file' name='estimate' accept='.csv,.xlsx' required> <button type='submit'>Prepare audit</button></form><p>Or <form action='/sample' method='post' style='display:inline'><button type='submit'>Run synthetic sample</button></form></p></section>""")


def read_uploaded_file(handler: BaseHTTPRequestHandler) -> tuple[str, bytes]:
    content_type = handler.headers.get("Content-Type", "")
    if not content_type.startswith("multipart/form-data"):
        raise InputError("Upload request must use multipart/form-data.")
    length = int(handler.headers.get("Content-Length", "0") or "0")
    if length <= 0 or length > 26 * 1024 * 1024:
        raise InputError("Upload request is empty or exceeds the local 26 MB request limit.")
    form = cgi.FieldStorage(fp=handler.rfile, headers=handler.headers, environ={"REQUEST_METHOD": "POST", "CONTENT_TYPE": content_type, "CONTENT_LENGTH": str(length)})
    field = form["estimate"] if "estimate" in form else None
    if field is None or not getattr(field, "filename", ""):
        raise InputError("Choose a CSV or XLSX file before continuing.")
    return Path(field.filename).name, field.file.read()


def mapping_page(token: str, session: dict) -> bytes:
    blocks: list[str] = []
    for sheet, rows in session["sheets"].items():
        headers = [header for header in rows[0] if not header.startswith("__")]
        detected = column_map(headers)
        can_auto_include = all(detected.get(field) for field in REQUIRED_FIELDS)
        sample_rows = rows[:3]
        selects: list[str] = []
        for field in (*REQUIRED_FIELDS, *OPTIONAL_FIELDS):
            options = ["<option value=''>— not mapped —</option>"] + [f"<option value='{html.escape(header, quote=True)}'{' selected' if detected.get(field) == header else ''}>{html.escape(header)}</option>" for header in headers]
            selects.append(f"<label>{html.escape(field)}{' *' if field in REQUIRED_FIELDS else ''}<br><select name='map__{quote(sheet, safe='')}__{field}'>{''.join(options)}</select></label>")
        preview_head = "".join(f"<th>{html.escape(header)}</th>" for header in headers)
        preview_rows = "".join("<tr>" + "".join(f"<td>{html.escape(row.get(header, ''))}</td>" for header in headers) + "</tr>" for row in sample_rows)
        include = " checked" if can_auto_include else ""
        blocks.append(f"<section class='card'><h2>Sheet: {html.escape(sheet)}</h2><p><label><input type='checkbox' name='include__{quote(sheet, safe='')}' value='1'{include}> Include this sheet in the audit</label></p><p>Map fields marked * for each included sheet. Sheets such as cover pages can remain excluded. Detected columns are preselected.</p><div style='display:flex;gap:1rem;flex-wrap:wrap'>{''.join(selects)}</div><h3>Preview (first {len(sample_rows)} rows)</h3><div style='overflow:auto'><table><thead><tr>{preview_head}</tr></thead><tbody>{preview_rows}</tbody></table></div></section>")
    return page("Map columns", f"<form action='/audit' method='post'><input type='hidden' name='token' value='{token}'>{''.join(blocks)}<p><button type='submit'>Run deterministic audit</button> <a href='/'>Cancel</a></p></form>")


def findings_page(token: str, session: dict) -> bytes:
    result = session["result"]
    counts = result["counts"]
    metrics = result["review_metrics"]
    rows = "".join("<tr>" + "".join(f"<td>{html.escape(str(finding[key]))}</td>" if key != "severity" else f"<td class='{html.escape(str(finding[key]))}'>{html.escape(str(finding[key]))}</td>" for key in ("severity", "rule_id", "sheet", "row", "field", "message", "evidence", "recommended_action")) + "</tr>" for finding in result["findings"]) or "<tr><td colspan='8'>No deterministic findings.</td></tr>"
    return page("Audit results", f"""<div class='notice'><strong>{html.escape(metrics['status'])}.</strong> Deterministic review prompts only; this is not a bid certification.</div><section class='card'><div class='metrics'><div class='metric'><strong>{metrics['affected_rows']} / {result['rows_reviewed']}</strong><br>Affected rows ({metrics['affected_row_percent']}%)</div><div class='metric'><strong>{metrics['priority_rows']}</strong><br>Critical/high-priority rows</div><div class='metric'><strong>{metrics['finding_count']}</strong><br>Total findings</div><div class='metric'><strong>{result['score']}/100</strong><br>Legacy score</div></div><p><strong>Sheets:</strong> {html.escape(', '.join(result['sheets_reviewed']))}</p><p>Critical: {counts['Critical']} | High: {counts['High']} | Medium: {counts['Medium']} | Low: {counts['Low']}</p><p>{html.escape(result['score_explanation'])}</p><p><a class='button' href='/export/findings?token={token}'>Download findings CSV</a> <a class='button' href='/export/summary?token={token}'>Download management summary HTML</a> <a href='/'>Start another audit</a></p></section><section class='card'><h2>Findings</h2><div style='overflow:auto'><table><thead><tr><th>Severity</th><th>Rule</th><th>Sheet</th><th>Row</th><th>Field</th><th>Finding</th><th>Evidence</th><th>Recommended action</th></tr></thead><tbody>{rows}</tbody></table></div></section>""")


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
                    if form.get(f"include__{encoded}", [""])[0] != "1":
                        continue
                    selected[sheet] = rows
                    mappings[sheet] = {}
                    for field in (*REQUIRED_FIELDS, *OPTIONAL_FIELDS):
                        value = form.get(f"map__{encoded}__{field}", [""])[0]
                        if value:
                            mappings[sheet][field] = value
                if not selected:
                    raise InputError("Include at least one worksheet before running the audit.")
                session["result"] = audit(selected, mappings)
                self.send_html(findings_page(token, session))
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
