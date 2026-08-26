"""Public server entrypoint with Civil Estimate Review Auditor review UX.

The tested runtime remains in ``server_legacy``. This wrapper adds the public
product title, presentation-only finding/reference review views, review
attention guidance, explicit in-memory review-package export, governed
reference evidence metadata, and a fictional onboarding guide without
changing deterministic audit/reference semantics.
"""
from __future__ import annotations

import html
from http import HTTPStatus
from urllib.parse import parse_qs, urlencode, urlparse

import server_legacy as _server
from server_legacy import *  # noqa: F401,F403 - compatibility re-export
from onboarding import guide_body
from reference_metadata import reference_review_csv
from reference_session import parse_reference_multipart, reference_panel, validate_reference_submission
from review_filters import (
    GROUP_OPTIONS,
    SEVERITY_FILTERS,
    SORT_OPTIONS,
    filter_findings,
    filter_options,
    group_findings,
    sort_findings,
)
from review_guidance import review_attention_summary
from review_package import build_review_package

_LEGACY_TITLE = b"Civil Bid Readiness Auditor"
_PUBLIC_TITLE = b"Civil Estimate Review Auditor"
_original_home = _server.home
_FINDING_VIEW_KEYS = ("severity", "review_status", "rule_id", "sheet", "q", "sort_by", "group_by")
_REFERENCE_VIEW_KEYS = ("ref_status", "ref_type", "ref_q", "ref_sort", "ref_group")
_ACCESSIBILITY_STYLE = """
<style>
.skip-links{margin:0 0 12px}.skip-links a{margin-right:12px}
a:focus-visible,button:focus-visible,input:focus-visible,select:focus-visible{outline:3px solid currentColor;outline-offset:2px}
.group-row th{background:#dfe8ee;font-size:14px;padding:9px}.visually-helpful{font-size:12px;color:#4a5560}
caption{text-align:left;font-weight:bold;padding:8px 0}
</style>
"""


def home(message: str = "") -> bytes:
    content = _original_home(message).replace(_LEGACY_TITLE, _PUBLIC_TITLE)
    guide_card = b"<section class='card'><h2>New here?</h2><p>Use a fictional walkthrough to learn mapping, review views, dispositions, governed reference evidence, and review-package export without using live project data.</p><p><a class='button' href='/guide'>Open fictional onboarding walkthrough</a></p></section>"
    return content.replace(b"</main>", guide_card + b"</main>", 1)


def guide_page() -> bytes:
    return _server.page("Fictional onboarding walkthrough", guide_body())


_server.home = home
_server._reference_panel = reference_panel


def _selected(value: str, current: str) -> str:
    return " selected" if value == current else ""


def _hidden_view_inputs(values: dict[str, str], keys: tuple[str, ...]) -> str:
    return "".join(
        f"<input type='hidden' name='{html.escape(key, quote=True)}' value='{html.escape(str(values.get(key, '')), quote=True)}'>"
        for key in keys
        if values.get(key, "") != ""
    )


def _result_url(token: str, current: dict[str, str] | None = None, **overrides: str) -> str:
    query = {"token": token}
    if current:
        query.update({key: value for key, value in current.items() if value})
    for key, value in overrides.items():
        if value:
            query[key] = value
        else:
            query.pop(key, None)
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
    sort_labels = {
        "priority": "Priority / severity",
        "source": "Source sheet / row",
        "rule": "Rule",
        "sheet": "Sheet",
        "review_status": "Review status",
    }
    group_labels = {"": "No grouping", "sheet": "Sheet", "rule": "Rule", "review_status": "Review status"}
    sort_options = "".join(
        f"<option value='{value}'{_selected(value, filters['sort_by'])}>{html.escape(sort_labels[value])}</option>"
        for value in SORT_OPTIONS
    )
    group_options = "".join(
        f"<option value='{value}'{_selected(value, filters['group_by'])}>{html.escape(group_labels[value])}</option>"
        for value in GROUP_OPTIONS
    )
    quick = " ".join(
        [
            f"<a href='{_result_url(token, filters, severity='', review_status='', rule_id='', sheet='', q='')}'>All</a>",
            f"<a href='{_result_url(token, filters, severity='Priority', review_status='', rule_id='', sheet='', q='')}'>Priority</a>",
            f"<a href='{_result_url(token, filters, severity='', review_status='Open', rule_id='', sheet='', q='')}'>Open</a>",
            f"<a href='{_result_url(token, filters, severity='', review_status='Needs correction', rule_id='', sheet='', q='')}'>Needs correction</a>",
            f"<a href='{_result_url(token, filters, severity='', review_status='Suppressed', rule_id='', sheet='', q='')}'>Suppressed</a>",
        ]
    )
    total = len(result.get("findings", []))
    reference_hidden = _hidden_view_inputs(filters, _REFERENCE_VIEW_KEYS)
    reset_url = _result_url(
        token,
        filters,
        severity="",
        review_status="",
        rule_id="",
        sheet="",
        q="",
        sort_by="priority",
        group_by="",
    )
    return f"""<section class='card' id='filters' tabindex='-1' aria-labelledby='filters-heading'><h2 id='filters-heading'>Review filters and view</h2><p><strong>Visible:</strong> {visible} of {total} findings. Filtering, sorting, and grouping change only this view; findings and saved review state are unchanged.</p><p><strong>Quick views:</strong> {quick}</p><form action='/results' method='get'><input type='hidden' name='token' value='{html.escape(token, quote=True)}'>{reference_hidden}<div style='display:flex;gap:1rem;flex-wrap:wrap'><label>Severity<br><select name='severity'>{severity_options}</select></label><label>Review status<br><select name='review_status'>{review_options}</select></label><label>Rule<br><select name='rule_id'>{rule_options}</select></label><label>Sheet<br><select name='sheet'>{sheet_options}</select></label><label>Search<br><input type='search' name='q' value='{html.escape(filters['q'], quote=True)}' placeholder='message, evidence, row, note'></label><label>Sort by<br><select name='sort_by'>{sort_options}</select></label><label>Group by<br><select name='group_by'>{group_options}</select></label></div><p><button type='submit'>Apply view</button> <a href='{reset_url}'>Reset findings view</a></p></form></section>"""


def _attention_panel(token: str, summary: dict, filters: dict[str, str]) -> str:
    open_url = _result_url(token, filters, severity="", review_status="Open", rule_id="", sheet="", q="")
    correction_url = _result_url(token, filters, severity="", review_status="Needs correction", rule_id="", sheet="", q="")
    reference_url = _result_url(token, filters, ref_status="Exceptions") + "#references"
    return f"""<section class='card' id='attention' tabindex='-1' aria-labelledby='attention-heading'>
<h2 id='attention-heading'>Review attention summary</h2>
<div class='metrics'>
<div class='metric'><strong>{summary['open_count']}</strong><br>Open findings</div>
<div class='metric'><strong>{summary['needs_correction_count']}</strong><br>Needs correction</div>
<div class='metric'><strong>{summary['reference_exception_count']}</strong><br>Reference exceptions</div>
</div>
<p>{html.escape(summary['finding_message'])}</p>
<p>{html.escape(summary['reference_message'])}</p>
<p><a href='{open_url}'>View Open findings</a> &nbsp; <a href='{correction_url}'>View Needs correction</a> &nbsp; <a href='{reference_url}'>View reference exceptions</a></p>
<p class='visually-helpful'>These counts describe the current review state only. They do not establish estimator approval, reference authority, or bid readiness.</p>
</section>"""


def _render_review_rows(groups, dispositions: dict[int, dict[str, str]]) -> str:
    parts: list[str] = []
    has_grouping = len(groups) > 1 or (groups and groups[0][0])
    for label, findings in groups:
        if has_grouping and label:
            parts.append(
                f"<tr class='group-row'><th colspan='10' scope='rowgroup'>"
                f"{html.escape(label)} <span class='visually-helpful'>({len(findings)} finding{'s' if len(findings) != 1 else ''})</span></th></tr>"
            )
        for finding in findings:
            finding_id = int(finding["id"])
            row = _server._review_row(
                finding,
                dispositions.get(finding_id, {"status": "Open", "reason": ""}),
            ).replace("<tr>", f"<tr id='finding-{finding_id}'>", 1)
            parts.append(row)
    return "".join(parts) or "<tr><td colspan='10'>No findings match the current filters. The underlying audit result is unchanged.</td></tr>"


def findings_page(token: str, session: dict, message: str = "", filters: dict[str, str] | None = None) -> bytes:
    result = session["result"]
    dispositions = session.setdefault("dispositions", _server.default_dispositions(result))
    incoming = filters or {}
    filters = {
        "severity": str(incoming.get("severity", "") or ""),
        "review_status": str(incoming.get("review_status", "") or ""),
        "rule_id": str(incoming.get("rule_id", "") or ""),
        "sheet": str(incoming.get("sheet", "") or ""),
        "q": str(incoming.get("q", "") or ""),
        "sort_by": str(incoming.get("sort_by", "priority") or "priority"),
        "group_by": str(incoming.get("group_by", "") or ""),
        "ref_status": str(incoming.get("ref_status", "Exceptions") or "Exceptions"),
        "ref_type": str(incoming.get("ref_type", "") or ""),
        "ref_q": str(incoming.get("ref_q", "") or ""),
        "ref_sort": str(incoming.get("ref_sort", "status") or "status"),
        "ref_group": str(incoming.get("ref_group", "") or ""),
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
    ordered_findings = sort_findings(visible_findings, dispositions, filters["sort_by"])
    grouped_findings = group_findings(ordered_findings, dispositions, filters["group_by"])

    counts = result["counts"]
    metrics = result["review_metrics"]
    disposition_counts = _server.review_metrics(result, dispositions)
    attention = review_attention_summary(result, dispositions, session.get("reference_results", []))
    attention_html = _attention_panel(token, attention, filters)
    rows = _render_review_rows(grouped_findings, dispositions)
    alert = f"<div class='notice'>{html.escape(message)}</div>" if message else ""
    review_summary = " | ".join(f"{html.escape(status)}: {disposition_counts[status]}" for status in REVIEW_STATUSES)
    controls = _filter_controls(token, result, filters, len(visible_findings))
    finding_view = {key: filters[key] for key in _FINDING_VIEW_KEYS}
    reference_view = {key: filters[key] for key in _REFERENCE_VIEW_KEYS}
    reference_html = reference_panel(token, session, view=reference_view, preserve=finding_view).replace(
        "<section class='card'>",
        "<section class='card' id='references' tabindex='-1' aria-labelledby='references-heading'>",
        1,
    ).replace("<h2>Governed reference validation</h2>", "<h2 id='references-heading'>Governed reference validation</h2>", 1)
    navigation = "<nav class='skip-links' aria-label='Review page navigation'><a href='#attention'>Skip to attention summary</a><a href='#filters'>Skip to filters</a><a href='#findings'>Skip to findings</a><a href='#references'>Skip to references</a></nav>"
    return _server.page("Audit results", f"""{_ACCESSIBILITY_STYLE}{navigation}{alert}<div class='notice'><strong>{html.escape(metrics['status'])}.</strong> Deterministic review prompts only; this is not a bid certification.</div><section class='card'><div class='metrics'><div class='metric'><strong>{metrics['affected_rows']} / {result['rows_reviewed']}</strong><br>Affected rows ({metrics['affected_row_percent']}%)</div><div class='metric'><strong>{metrics['priority_rows']}</strong><br>Critical/high-priority rows</div><div class='metric'><strong>{metrics['finding_count']}</strong><br>Total findings</div><div class='metric'><strong>{result['score']}/100</strong><br>Legacy score</div></div><p><strong>Rows reviewed:</strong> {result['rows_reviewed']} &nbsp; <strong>Review-status score:</strong> {result['score']}/100 (legacy) &nbsp; <strong>Sheets:</strong> {html.escape(', '.join(result['sheets_reviewed']))}</p><p>Critical: {counts['Critical']} | High: {counts['High']} | Medium: {counts['Medium']} | Low: {counts['Low']}</p><p><strong>Human review:</strong> {review_summary}</p><p>{html.escape(result['score_explanation'])}</p><p><a class='button' href='/export/package?token={token}'>Download review package ZIP</a> <a class='button' href='/export/findings?token={token}'>Download findings CSV</a> <a class='button' href='/export/review?token={token}'>Download review CSV</a> <a class='button' href='/export/summary?token={token}'>Download management summary HTML</a> <a href='/'>Start another audit</a></p></section>{attention_html}{controls}<section class='card' id='findings' tabindex='-1' aria-labelledby='findings-heading'><h2 id='findings-heading'>Findings review</h2><p>Review state is temporary and local to this session. It does not alter the original estimate, deterministic findings, severity, or score. Suppressed findings require a reason.</p><form action='/review' method='post'><input type='hidden' name='token' value='{html.escape(token, quote=True)}'><div style='overflow:auto'><table aria-describedby='findings-caption'><caption id='findings-caption'>Visible deterministic findings and human review controls</caption><thead><tr><th>Severity</th><th>Rule</th><th>Sheet</th><th>Row</th><th>Field</th><th>Finding</th><th>Evidence</th><th>Recommended action</th><th>Review status</th><th>Reason / note</th></tr></thead><tbody>{rows}</tbody></table></div><p><button type='submit'>Save visible review states</button> <a href='#filters'>Back to filters</a></p></form></section>{reference_html}""")


_server.findings_page = findings_page


class Handler(_server.Handler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/guide":
            self.send_html(guide_page())
            return
        if parsed.path == "/export/references":
            _server.expire_sessions()
            token = parse_qs(parsed.query).get("token", [""])[0]
            session = SESSIONS.get(token)
            if not session or "result" not in session:
                self.send_html(home("This temporary audit session is no longer available. Upload the file again."), HTTPStatus.NOT_FOUND)
                return
            content = reference_review_csv(session.get("reference_results", []), session.get("reference_metadata", []))
            filename = "bid_audit_reference_checks.csv"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return
        if parsed.path == "/export/package":
            _server.expire_sessions()
            token = parse_qs(parsed.query).get("token", [""])[0]
            session = SESSIONS.get(token)
            if not session or "result" not in session:
                self.send_html(home("This temporary audit session is no longer available. Upload the file again."), HTTPStatus.NOT_FOUND)
                return
            content, filename = build_review_package(session)
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return
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
                "sort_by": query.get("sort_by", ["priority"])[0],
                "group_by": query.get("group_by", [""])[0],
                "ref_status": query.get("ref_status", ["Exceptions"])[0],
                "ref_type": query.get("ref_type", [""])[0],
                "ref_q": query.get("ref_q", [""])[0],
                "ref_sort": query.get("ref_sort", ["status"])[0],
                "ref_group": query.get("ref_group", [""])[0],
            }
            self.send_html(findings_page(token, session, filters=filters))
            return
        super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/references":
            _server.expire_sessions()
            try:
                token = parse_qs(parsed.query).get("token", [""])[0]
                session = SESSIONS.get(token)
                if not session or "result" not in session or "audit_sheets" not in session:
                    raise InputError("This temporary audit session expired. Upload the estimate again.")
                message = _server._multipart_message(self)
                uploads, revisions = parse_reference_multipart(message)
                pending = validate_reference_submission(session, uploads, revisions)
                session.update(pending)
                self.send_html(findings_page(token, session, "Governed reference validation completed using the explicitly supplied CSV file(s). Evidence metadata was recorded for this temporary session."))
            except (InputError, ValueError) as exc:
                self.send_html(home(str(exc)), HTTPStatus.BAD_REQUEST)
            return
        super().do_POST()


def run() -> None:
    print(f"Civil Estimate Review Auditor running at http://{HOST}:{PORT}")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


_server.run = run


if __name__ == "__main__":
    run()
