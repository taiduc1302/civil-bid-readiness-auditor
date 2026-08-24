# User workflow

1. Start the local server and open the displayed `http://127.0.0.1` URL.
2. Upload a CSV or XLSX estimate export, or load the synthetic sample.
3. Review detected worksheets and column mapping. Include only estimate sheets; leave cover/summary sheets excluded. Required fields are Description, Quantity, Unit, and Rate. Optional hierarchy fields include Bid Item, Activity, Resource Type, and Resource Code.
4. If a supported HeavyBid-style flat resource export is recognized, review the exact-alias preselected mappings. Recognition is fail-closed and all mappings remain editable.
5. Run the deterministic audit.
6. Review findings by severity and inspect sheet/row evidence. Treat affected-row metrics and severity as the primary operational indicators; the legacy score is secondary and is not a quality or readiness certification.
7. Record a temporary human disposition for each finding: `Open`, `Reviewed`, `Accepted`, `Needs correction`, or `Suppressed`. Suppressed findings require a reason. Dispositions do not alter the estimate, finding, severity, or score.
8. Optionally upload an explicitly approved Activity and/or Resource reference CSV. Reference checks are exact-code only and report `MATCH`, `UNIT_MISMATCH`, `NO_MATCH`, or `NOT_CHECKED`. They never guess replacement codes or convert units.
9. Download findings CSV, review-state CSV, reference-check CSV (when references were supplied), or the printable management-summary HTML.
10. Close the application. Current estimate, review, and reference state exists only in temporary process memory and expires with the local session/process.

Unsupported: encrypted/password-protected files, legacy `.xls`, images/PDFs, macros, formula evaluation, arbitrary advanced Excel features, direct HeavyBid database access, and production HeavyBid import validation.
