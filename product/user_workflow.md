# User workflow

1. Start the local server and open the displayed `http://127.0.0.1` URL. New users can open the fictional onboarding walkthrough from the home page.
2. For the basic walkthrough, run the normal synthetic sample. For hierarchy/reference practice, the guide can **Run structured fictional sample**, which loads only the bundled `synthetic_heavybid_style_resource_export.csv` into the normal editable mapping flow.
3. The guide also provides direct downloads for the bundled `synthetic_activity_reference.csv` and `synthetic_resource_reference.csv`. These files are fictional and are never auto-applied; upload them manually only after auditing the structured demo.
4. For normal work, upload a CSV or XLSX estimate export and review detected worksheets and column mapping. Required fields are Description, Quantity, Unit, and Rate. Optional hierarchy fields include Bid Item, Activity, Resource Type, and Resource Code.
5. If a supported HeavyBid-style flat resource export is recognized, review the exact-alias preselected mappings. Recognition is fail-closed and all mappings remain editable.
6. Run the deterministic audit.
7. Use the review attention summary and stable temporary findings view to identify Open / Needs correction attention items, then filter, sort, group, or search findings. These controls never change deterministic findings or saved review state.
8. Inspect sheet/row evidence and record a temporary human disposition for each finding: `Open`, `Reviewed`, `Accepted`, `Needs correction`, or `Suppressed`. Suppressed findings require a reason. Dispositions do not alter the estimate, finding, severity, or score.
9. Optionally upload an Activity and/or Resource reference CSV. For each supplied reference, an optional revision/label may be entered exactly as known. The app records role, filename, revision/label, file size, and SHA-256 as evidence but does not establish reference authority.
10. Reference checks are exact-code only and report `MATCH`, `UNIT_MISMATCH`, `NO_MATCH`, or `NOT_CHECKED`. Review them with a separate presentation view: Exceptions by default, status/type filters, free-text search including reference metadata, deterministic sorting, and optional grouping. Findings-view and reference-view settings preserve each other.
11. Optional Crew Code / Production Rate comparisons remain evidence-only and do not fill missing values.
12. Download individual findings/review/reference CSVs and the printable management summary, or download the deterministic ZIP review package. Exports remain full-session snapshots regardless of the current findings/reference filters. The package excludes the original estimate/reference bytes.
13. The review package includes `integrity.json`, which records byte size and SHA-256 for every other member. The in-memory verifier can detect changed, missing, duplicate, unexpected, unsafe, or unsupported package contents.
14. To verify a previously exported ZIP without restoring it, return to the home page and choose **Verify review package ZIP**. Upload one package; verification runs in memory, returns only integrity/package identity evidence, and never adds the package to `SESSIONS` or restores findings, dispositions, mappings, references, or approvals.
15. Close the application. Current estimate, review, findings-view, reference-view, and reference evidence state exists only in temporary process memory and expires with the local session/process.

Unsupported: encrypted/password-protected files, legacy `.xls`, images/PDFs, macros, formula evaluation, arbitrary advanced Excel features, direct HeavyBid database access, production HeavyBid import validation, and review-package state restoration/re-open.
