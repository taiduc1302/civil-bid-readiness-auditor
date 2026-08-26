# User workflow

1. Start the local server and open the displayed `http://127.0.0.1` URL. New users can open the fictional onboarding walkthrough from the home page.
2. Upload a CSV or XLSX estimate export, or load the synthetic sample.
3. Review detected worksheets and column mapping. Include only estimate sheets; leave cover/summary sheets excluded. Required fields are Description, Quantity, Unit, and Rate. Optional hierarchy fields include Bid Item, Activity, Resource Type, and Resource Code.
4. If a supported HeavyBid-style flat resource export is recognized, review the exact-alias preselected mappings. Recognition is fail-closed and all mappings remain editable.
5. Run the deterministic audit.
6. Use the stable temporary findings view to filter by severity, human review status, rule, sheet, or free text; sort by priority/source/rule/sheet/review status; optionally group by sheet/rule/review status. These controls never change deterministic findings or saved review state.
7. Inspect sheet/row evidence and record a temporary human disposition for each finding: `Open`, `Reviewed`, `Accepted`, `Needs correction`, or `Suppressed`. Suppressed findings require a reason. Dispositions do not alter the estimate, finding, severity, or score.
8. Optionally upload an Activity and/or Resource reference CSV. For each supplied reference, an optional revision/label may be entered exactly as known. The app records role, filename, revision/label, file size, and SHA-256 as evidence but does not establish reference authority.
9. Reference checks are exact-code only and report `MATCH`, `UNIT_MISMATCH`, `NO_MATCH`, or `NOT_CHECKED`. Review them with a separate presentation view: Exceptions by default, status/type filters, free-text search including reference metadata, deterministic sorting, and optional grouping. Findings-view and reference-view settings preserve each other.
10. Optional Crew Code / Production Rate comparisons remain evidence-only and do not fill missing values.
11. Download individual findings/review/reference CSVs and the printable management summary, or download the deterministic ZIP review package. Exports remain full-session snapshots regardless of the current findings/reference filters. The package excludes the original estimate/reference bytes.
12. Close the application. Current estimate, review, findings-view, reference-view, and reference evidence state exists only in temporary process memory and expires with the local session/process.

Unsupported: encrypted/password-protected files, legacy `.xls`, images/PDFs, macros, formula evaluation, arbitrary advanced Excel features, direct HeavyBid database access, and production HeavyBid import validation.
