"""Public server entrypoint with Civil Estimate Review Auditor review UX.

The tested runtime remains in ``server_legacy``. This wrapper adds the public
product title plus presentation-only results filtering/navigation without
changing deterministic findings or review-state semantics.
"""
from __future__ import annotations

import html
from http import HTTPStatus
from urllib.parse import parse_qs, urlencode, urlparse

import server_legacy as _server
from server_legacy import *  # noqa: F401,F403 - compatibility re-export
from review_filters import SEVERITY_FILTERS, filter_findings, filter_options

_LEGACY_TITLE = b"Civil Bid Readiness Auditor"
_PUBLIC_TITLE = b"Civil Estimate Review Auditor"
_original_home = _server.home


def home(message: str = "") -> bytes:
    return _original_home(message).replace(_LEGACY_TITLE, _PUBLIC_TITLE)


_server.home = home


def _selected(value: str, current: str) -> str:
    return " selected" if value == current else ""


def _result_url(token: str, **params: str) -> str:
    query = {"token": token}
    query.update({key: value for key, value in params.items() if value})
    return "/results?" + urlencode(query)


def _filter_controls(token: str, result: dict, filters: dict[str, str], visible: int) -> str:
    options = filter_options(result)
    severity_options = "".join(
        f"<option value='{html.escape(value, quote=True)}'{_selected(value, filters['severity'])}>{html.escape(value or 'All severities')}</option>"
        for value in SEVERITY_FILTERS
    )
    review_options = "<option value=''>All review states</option>" + "".join(
        f"<option value='{html.escape(value, quote=True)}'{_selected(value, filters['review_status'])}>{html.escape(value)}</option>"
        for value in REVIEW_STATUSES
    )
    rule_options = "<option value=''>All rules</option>" + "".join(
        f"<option value='{html.escape(value, quote=True)}'{_selected(value, filters['rule_id'])}>{html.escape(value)}</option>"
        for value in options["rules"]
    )
    sheet_options = "<option value=''>All sheets</option>" + "".join(
        f"<option value='{html.escape(value, quote=True)}'{_selected(value, filters['sheet'])}>{html.escape(value)}</option>"
        for value in options["sheets"]
    )
    quick = " ".join(
        [
            f"<a href='{_result_url(token)}'>All</a>",
            f"<a href='{_result_url(token, severity='Priority')}'>Priority</a>",
            f"<a href='{_result_url(token, review_status='Open')}'>Open</a>",
            f"<a href='{_result_url(token, review_status='Needs correction')}'>Needs correction</a>",
            f"<a href='{_result_url(token, review_status='Suppressed')}'>Suppressed</a>",
        ]
    )
    total = len(result.get("findings", []))
    return f"""<section class='card' id='filters'><h2>Review filters</h2><p><strong>Visible:</strong> {visible} of {total} findings. Filtering changes only this view; findings and saved review state are unchanged.</p><p><strong>Quick views:</strong> {quick}</p><form action='/results' method='get'><input type='hidden' name='token' value='{html.escape(token, quote=True)}'><div style='display:flex;gap:1rem;flex-wrap:wrap'><label>Severity<br><select name='severity'>{severity_options}</select></label><label>Review status<br><select name='review_status'>{review_options}</select></label><label>Rule<br><select name='rule_id'>{rule_options}</select></label><label>Sheet<br><select name='sheet'>{sheet_options}</select></label><label>Search<br><input type='search' name='q' value='{html.escape(filters['q'], quote=True)}' placeholder='message, evidence, row, note'></label></div><p><button type='submit'>Apply filters</button> <a href='{_result_url(token)}'>Clear</a></p></form></section>"""


def findings_page(token: str, session: dict, message: str = "", filters: dict[str, str] | None = None) -> bytes:
    result = session["result"]
    dispositions = session.setdefault("dispositions", _server.default_dispositions(result))
    filters = {
        "severity": str((filters or {}).get("severity", "") or ""),
        "review_status": str((filters or {}).get("review_status", "") or ""),
        "rule_id": str((filters or {}).get("rule_id", "") or ""),
        "sheet": str((filters or {}).get("sheet", "") or ""),
        "q": str((filters or {}).get("q", "") or ""),
    }
    visible_findings = filter_findings(
        result,
        dispositions,
        severity=filters["severity"],
        review_status=filters["review_status"],
        rule_id=filters["rule_id"],
        sheet=filters["sheet"],
        text=filters["q"],
    )

    counts = result["counts"]
    metrics = result["review_metrics"]
    disposition_counts = _server.review_metrics(result, dispositions)
    rows = "".join(
        _server._review_row(finding, dispositions.get(int(finding["id"]), {"status": "Open", "reason": ""})).replace(
            "<tr>", f"<tr id='finding-{int(finding['id'])}'>", 1
        )
        for finding in visible_findings
    ) or "<tr><td colspan='10'>No findings match the current filters.</td></tr>"
    alert = f"<div class='notice'>{html.escape(message)}</div>" if message else ""
    review_summary = " | ".join(f"{html.escape(status)}: {disposition_counts[status]}" for status in REVIEW_STATUSES)
    controls = _filter_controls(token, result, filters, len(visible_findings))
    return _server.page("Audit results", f"""{alert}<div class='notice'><strong>{html.escape(metrics['status'])}.</strong> Deterministic review prompts only; this is not a bid certification.</div><section class='card'><div class='metrics'><div class='metric'><strong>{metrics['affected_rows']} / {result['rows_reviewed']}</strong><br>Affected rows ({metrics['affected_row_percent']}%)</div><div class='metric'><strong>{metrics['priority_rows']}</strong><br>Critical/high-priority rows</div><div class='metric'><strong>{metrics['finding_count']}</strong><br>Total findings</div><div class='metric'><strong>{result['score']}/100</strong><br>Legacy score</div></div><p><strong>Rows reviewed:</strong> {result['rows_reviewed']} &nbsp; <strong>Review-status score:</strong> {result['score']}/100 (legacy) &nbsp; <strong>Sheets:</strong> {html.escape(', '.join(result['sheets_reviewed']))}</p><p>Critical: {counts['Critical']} | High: {counts['High']} | Medium: {counts['Medium']} | Low: {counts['Low']}</p><p><strong>Human review:</strong> {review_summary}</p><p>{html.escape(result['score_explanation'])}</p><p><a class='button' href='/export/findings?token={token}'>Download findings CSV</a> <a class='button' href='/export/review?token={token}'>Download review CSV</a> <a class='button' href='/export/summary?token={token}'>Download management summary HTML</a> <a href='/'>Start another audit</a></p></section>{controls}<section class='card' id='findings'><h2>Findings review</h2><p>Review state is temporary and local to this session. It does not alter the original estimate, deterministic findings, severity, or score. Suppressed findings require a reason.</p><form action='/review' method='post'><input type='hidden' name='token' value='{html.escape(token, quote=True)}'><div style='overflow:auto'><table><thead><tr><th>Severity</th><th>Rule</th><th>Sheet</th><th>Row</th><th>Field</th><th>Finding</th><th>Evidence</th><th>Recommended action</th><th>Review status</th><th>Reason / note</th></tr></thead><tbody>{rows}</tbody></table></div><p><button type='submit'>Save visible review states</button> <a href='#filters'>Back to filters</a></p></form></section>{_server._reference_panel(token, session)}""")


_server.findings_page = findings_page


class Handler(_server.Handler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/results":
            _server.expire_sessions()
            query = parse_qs(parsed.query, keep_blank_values=True)
            token = query.get("token", [""])[0]
            session = SESSIONS.get(token)
            if not session or "result" not in session:
                self.send_html(home("This temporary audit session is no longer available. Upload the file again."), HTTPStatus.NOT_FOUND)
                return
            filters = {
                "severity": query.get("severity", [""])[0],
                "review_status": query.get("review_status", [""])[0],
                "rule_id": query.get("rule_id", [""])[0],
                "sheet": query.get("sheet", [""])[0],
                "q": query.get("q", [""])[0],
            }
            self.send_html(findings_page(token, session, filters=filters))
            return
        super().do_GET()


def run() -> None:
    print(f"Civil Estimate Review Auditor running at http://{HOST}:{PORT}")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


_server.run = run


if __name__ == "__main__":
    run()
