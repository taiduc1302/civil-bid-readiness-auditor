"""Loopback-only interface for the Civil Bid Readiness Auditor."""
from __future__ import annotations

import html
import io
import re
import secrets
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

from audit_engine import ALIASES, REQUIRED_FIELDS, InputError, audit, column_map, findings_csv, management_summary_html, parse_upload


ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "samples" / "synthetic_civil_estimate.csv"
SESSIONS: dict[str, dict] = {}
SESSION_TTL_SECONDS = 30 * 60
MAX_REQUEST_BYTES = 25 * 1024 * 1024


def expire_sessions() -> None:
    cutoff = time.monotonic() - SESSION_TTL_SECONDS
    for token in [key for key, value in SESSIONS.items() if value.get("created", 0) < cutoff]:
        del SESSIONS[token]


def read_uploaded_file(handler: BaseHTTPRequestHandler) -> tuple[str, bytes]:
    """Read one multipart estimate upload without deprecated/removed cgi support."""
    content_type = handler.headers.get("Content-Type", "")
    try:
        length = int(handler.headers.get("Content-Length", "0"))
    except ValueError as exc:
        raise InputError("Upload has an invalid size.") from exc
    if length <= 0 or length > MAX_REQUEST_BYTES:
        raise InputError("Upload exceeds the 25 MB local processing limit.")
    payload = handler.rfile.read(length)
    match = re.search(r"boundary=(?:\"([^\"]+)\"|([^;\s]+))", content_type, re.IGNORECASE)
    if not match:
        raise InputError("Upload must use multipart form data.")
    boundary = (match.group(1) or match.group(2)).encode("ascii", "strict")
    for part in payload.split(b"--" + boundary)[1:]:
        if part.startswith(b"--"):
            break
        part = part.lstrip(b"\r\n")
        header_blob, separator, value = part.partition(b"\r\n\r\n")
        if not separator:
            continue
        headers = header_blob.decode("utf-8", "replace")
        disposition = re.search(r'Content-Disposition:\s*form-data;[^\r\n]*name="estimate"[^\r\n]*filename="([^\"]*)"', headers, re.IGNORECASE)
        if disposition:
            if value.endswith(b"\r\n"):
                value = value[:-2]
            return disposition.group(1), value
    raise InputError("Choose a CSV or XLSX file before continuing.")


def page(title: str, body: str) -> bytes:
    return f"""<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{html.escape(title)}</title><style>body{{font:16px system-ui,sans-serif;max-width:1160px;margin:2rem auto;padding:0 1rem;color:#18212b;background:#fafcfd}}h1{{margin-bottom:.3rem}}.card{{background:#fff;border:1px solid #d5e0e8;border-radius:9px;padding:1.2rem;margin:1rem 0}}.notice{{background:#fff8df;border-left:4px solid #ba7b09;padding:.9rem}}.error{{background:#fff0f0;border-left:4px solid #b42318;padding:.9rem}}button,.button{{background:#075985;color:white;padding:.65rem 1rem;border:0;border-radius:5px;text-decoration:none;font-weight:600;cursor:pointer}}table{{width:100%;border-collapse:collapse;font-size:.88rem}}th,td{{padding:.5rem;border-bottom:1px solid #d5e0e8;vertical-align:top;text-align:left}}th{{background:#eaf3f8}}select,input{{padding:.35rem;max-width:100%}}.Critical{{color:#991b1b;font-weight:700}}.High{{color:#b45309;font-weight:700}}.Medium{{color:#1d4ed8;font-weight:700}}.Low{{color:#475569;font-weight:700}}code{{background:#eef2f4;padding:.1rem .3rem}}</style></head><body><h1>Civil Bid Readiness Auditor</h1><p>Local, deterministic pre-submit estimate QA.</p>{body}</body></html>""".encode("utf-8")


def home(error: str = "") -> bytes:
    message = f"<div class='error'>{html.escape(error)}</div>" if error else ""
    return page("Civil Bid Readiness Auditor", f"""<div class='notice'><strong>Human review required.</strong> This tool flags deterministic data-quality prompts. It does not validate prices, quantities, scope, profitability, compliance, or a bid decision. Files are processed only in this browser session on your computer.</div>{message}<section class='card'><h2>Start an audit</h2><form action='/prepare' method='post' enctype='multipart/form-data'><label>CSV or XLSX estimate export<br><input type='file' name='estimate' accept='.csv,.xlsx' required></label><p><button type='submit'>Review file and map columns</button></p></form><p>or <form action='/sample' method='post'><button type='submit'>Load synthetic sample project</button></form></p></section><section class='card'><h2>Supported fields</h2><p>Required: Description, Quantity, Unit, Rate. Optional: Amount, Category, Markup %, Margin %. Common aliases are detected automatically.</p><p>Unsupported: legacy XLS, password-protected files, macros, PDF/images, formula evaluation, cloud storage, and integrations.</p></section>""")


def mapping_page(token: str, session: dict) -> bytes:
    blocks: list[str] = []
    for sheet, rows in session["sheets"].items():
        headers = [header for header in rows[0] if not header.startswith("__")]
        detected = column_map(headers)
        can_auto_include = all(detected.get(field) for field in REQUIRED_FIELDS)
        sample_rows = rows[:3]
        selects: list[str] = []
        for field in (*REQUIRED_FIELDS, "amount", "category", "markup_pct", "margin_pct"):
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
    rows = "".join("<tr>" + "".join(f"<td>{html.escape(str(finding[key]))}</td>" if key != "severity" else f"<td class='{html.escape(str(finding[key]))}'>{html.escape(str(finding[key]))}</td>" for key in ("severity", "rule_id", "sheet", "row", "field", "message", "evidence", "recommended_action")) + "</tr>" for finding in result["findings"]) or "<tr><td colspan='8'>No deterministic findings.</td></tr>"
    return page("Audit results", f"""<div class='notice'><strong>Review-status score: {result['score']}/100.</strong> {html.escape(result['score_explanation'])}</div><section class='card'><p><strong>Rows reviewed:</strong> {result['rows_reviewed']} &nbsp; <strong>Sheets:</strong> {html.escape(', '.join(result['sheets_reviewed']))}</p><p>Critical: {counts['Critical']} | High: {counts['High']} | Medium: {counts['Medium']} | Low: {counts['Low']}</p><p><a class='button' href='/export/findings?token={token}'>Download findings CSV</a> <a class='button' href='/export/summary?token={token}'>Download management summary HTML</a> <a href='/'>Start another audit</a></p></section><section class='card'><h2>Findings</h2><div style='overflow:auto'><table><thead><tr><th>Severity</th><th>Rule</th><th>Sheet</th><th>Row</th><th>Field</th><th>Finding</th><th>Evidence</th><th>Recommended action</th></tr></thead><tbody>{rows}</tbody></table></div></section>""")


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
                length = int(self.headers.get("Content-Length", "0"))
                form = parse_qs(self.rfile.read(length).decode("utf-8"))
                token = form.get("token", [""])[0]
                session = SESSIONS.get(token)
                if not session:
                    raise InputError("The temporary upload session expired. Upload the file again.")
                mappings: dict[str, dict[str, str]] = {}
                for key, values in form.items():
                    if key.startswith("map__"):
                        _, encoded_sheet, field = key.split("__", 2)
                        mappings.setdefault(unquote(encoded_sheet), {})[field] = values[0]
                selected_sheets = [unquote(key.split("__", 1)[1]) for key in form if key.startswith("include__") and form[key][0] == "1"]
                if not selected_sheets:
                    # Allows direct integrations/tests without a browser checkbox while still requiring a complete mapping.
                    selected_sheets = [sheet for sheet in session["sheets"] if all(mappings.get(sheet, {}).get(field) for field in REQUIRED_FIELDS)]
                sheets_to_audit = {sheet: session["sheets"][sheet] for sheet in selected_sheets if sheet in session["sheets"]}
                if not sheets_to_audit:
                    raise InputError("Select at least one sheet with all required mappings.")
                session["result"] = audit(sheets_to_audit, mappings)
                self.send_html(findings_page(token, session))
                return
            self.send_html(home("Page not found."), HTTPStatus.NOT_FOUND)
        except InputError as exc:
            self.send_html(home(str(exc)), HTTPStatus.BAD_REQUEST)
        except Exception:
            self.send_html(home("The file could not be processed safely. Check the format and try again."), HTTPStatus.BAD_REQUEST)


def main() -> None:
    host, port = "127.0.0.1", 8765
    print(f"Civil Bid Readiness Auditor running locally at http://{host}:{port}")
    print("Press Ctrl+C to stop. Uploaded files remain only in process memory.")
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    main()
