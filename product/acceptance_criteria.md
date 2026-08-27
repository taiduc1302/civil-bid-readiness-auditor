# P0 acceptance criteria

| ID | Criterion |
|---|---|
| AC-01 | A valid CSV produces row-linked findings and a deterministic score. |
| AC-02 | A valid XLSX, including a multi-sheet file, is ingested without using Excel or an external API. |
| AC-03 | Missing required fields, blank files, malformed files, and unsupported types produce actionable errors. |
| AC-04 | Common aliases auto-map; the UI exposes manual mapping when required mappings are absent. Optional estimate hierarchy aliases are retained when detected. |
| AC-05 | Rules detect the documented missing, zero, negative, duplicate, unit, reconciliation, markup/margin, peer-relative rate outlier, category concentration, and formula-text conditions. Duplicate/conflict checks respect available Bid Item / Activity / Resource context. |
| AC-06 | Findings export to CSV and a management summary exports as printable HTML. |
| AC-07 | The synthetic sample yields the documented expected 0/100 score, 9 reviewed rows, and severity counts (0 Critical, 11 High, 2 Medium, 1 Low) on every run. |
| AC-08 | The running app binds only to loopback and does not write uploaded data or make network calls. |
| AC-09 | The UI and exports include the human-review and non-certification limitation. |
| AC-10 | R015 compares rates only inside peer groups sharing normalized unit and resource/category class, requires at least four positive peer rates, and never uses one global median across unlike units. |
| AC-11 | XLSX ingestion scans the first 20 worksheet rows for a likely estimate header and can skip report titles, project metadata, and blank rows while preserving original source row numbers. |
| AC-12 | If no sufficiently confident XLSX header is found, ingestion retains first-readable-row behavior so manual mapping remains possible. |
| AC-13 | GitHub Actions runs the unit test suite on pull requests and pushes to `main` using supported Python versions. |
| AC-14 | Safe UOM spelling variants normalize for deterministic comparisons without changing source values or performing quantity conversions. |
| AC-15 | Distinct earthwork volume bases (`BCY`, `LCY`, `CCY`) and US ton versus metric tonne remain distinct unless a future explicit conversion policy is supplied. |
| AC-16 | Audit results report unique affected rows, affected-row percentage, Critical/High priority rows, total findings, and an operational review status; the legacy score remains secondary for compatibility. |
| AC-17 | Equivalent UOM spelling variants do not create false R010 inconsistent-unit findings and can participate in the same R015 peer group. |
| AC-18 | A fictional hierarchical civil estimate fixture exercises Bid Item / Activity / Resource context, safe UOM normalization, duplicate detection, extension mismatch, zero placeholders, and peer-relative rate outliers without using live company/project data. |
| AC-19 | A named structured-civil export profile maps known source headers into canonical fields deterministically and leaves missing/unknown columns unmapped rather than guessing values. |
| AC-20 | Export profiles remain a thin adapter layer: they do not infer quantities, rates, units, resource classes, codes, or company-specific codebook values. |
| AC-21 | The HeavyBid-style resource-export adapter activates only when its required hierarchy/resource header signature is unambiguous; mapping is exact/case-insensitive/whitespace-normalized and non-fuzzy. |
| AC-22 | Human finding dispositions support `Open`, `Reviewed`, `Accepted`, `Needs correction`, and `Suppressed`; suppression requires a reason and invalid review updates fail closed without partial mutation. |
| AC-23 | Human dispositions remain separate from deterministic findings: they do not alter source estimate values, rule output, severity counts, or the legacy score. |
| AC-24 | Review-state CSV export preserves original finding evidence plus human status/reason and protects formula-like text from spreadsheet execution. |
| AC-25 | Explicitly supplied Activity/Resource reference CSVs are validated by exact code against a governed snapshot and report `MATCH`, `UNIT_MISMATCH`, `NO_MATCH`, or `NOT_CHECKED` while preserving source row/sheet linkage. |
| AC-26 | Governed reference validation rejects duplicate reference codes, missing required reference columns, and empty/header-only reference files; it never proposes replacement codes or performs physical unit conversion. |
| AC-27 | A successful governed-reference match does not imply HeavyBid import validity. Any future HeavyBid-readable output must retain `HEAVYBID_IMPORT_VALIDATED=false` until a real independent test import is reviewed. |
| AC-28 | A stable temporary `/results` view filters findings by severity, review status, rule, sheet, and free text without mutating deterministic findings or dispositions. |
| AC-29 | Review navigation reports visible/total finding counts, provides common quick views and row anchors, and fails safely for expired session tokens. |
| AC-30 | The local review-package ZIP is generated only on explicit download from the current in-memory session and deterministically includes a manifest, findings CSV, review CSV, summary HTML, README, and reference checks only when present. |
| AC-31 | The review package never contains original estimate/reference bytes, does not claim bid approval, and explicitly preserves `NOT_PRODUCTION_READY`, `NOT_ESTIMATOR_VALIDATED`, and `HEAVYBID_IMPORT_VALIDATED=false`. |
| AC-32 | Governed reference upload records role, filename, user-supplied revision/label, exact byte size, and SHA-256 for the uploaded bytes; blank revision remains blank and authority is explicitly `NOT_ESTABLISHED_BY_APP`. |
| AC-33 | Reference-check CSV and review-package manifest preserve reference metadata plus sheet/row linkage, and formula-like filename/revision text is protected from spreadsheet execution. |
| AC-34 | Reference reruns update checks and metadata atomically: a failed replacement does not partially overwrite the previous successful reference evidence, and inactive stale metadata is excluded when current reference checks are absent. |
| AC-35 | Findings can be sorted deterministically by priority/severity, source sheet/row, rule, sheet, or review status, with finding id as the final stable tie-breaker; sorting never mutates audit or review state. |
| AC-36 | Findings can be optionally grouped by sheet, rule, or review status while preserving current sorted order, and the review page provides keyboard-friendly skip links, focus targets, visible focus styling, and an accessible table caption. |
| AC-37 | A local fictional onboarding guide is reachable from the home page, can start the existing synthetic sample flow, covers review views/dispositions/reference metadata/review-package export, and repeats the non-certification and HeavyBid safety boundaries. |
| AC-38 | Governed reference results support a presentation-only default Exceptions view, status/type filtering, metadata-aware free-text search, deterministic sorting by status/source/code/type, and optional grouping by status/type without mutating stored reference results or metadata. |
| AC-39 | Findings-view and reference-view parameters preserve each other in the stable `/results` query state; invalid reference-view parameters fail safe, and reference CSV/review-package exports remain full-session snapshots regardless of active UI filters. |
| AC-40 | A presentation-only attention summary reports current Open findings, Needs correction findings, and non-MATCH reference checks; zero findings/attention/exceptions are explicitly not treated as estimate correctness, estimator approval, reference authority, or bid readiness, and filtered empty states state that underlying audit results are unchanged. |
| AC-41 | Review-package ZIPs include deterministic `integrity.json` metadata covering byte size and SHA-256 for every other member; the in-memory verifier rejects changed, missing, duplicate, unexpected, unsafe, or unsupported packages and explicitly does not restore session state or infer approval, readiness, authority, or HeavyBid import validity. |
| AC-42 | A local `/verify-package` screen accepts one review-package ZIP through the existing 26 MB multipart route, runs integrity verification entirely in memory, reports package/integrity evidence, creates no review session, restores no review state, and fails safely for missing, wrong-extension, invalid, or tampered packages. |
| AC-43 | The onboarding guide can start exactly the bundled structured fictional estimate and download exactly the bundled fictional Activity/Resource reference CSVs through fixed routes; demo references are never auto-applied, arbitrary filesystem paths are not exposed, and the structured demo opens the normal editable mapping workflow without automatic audit/approval/reference state. |
| AC-44 | Grouped findings headings show compact severity plus Open/Needs correction composition, and grouped reference-type headings show compact reference-status composition, while preserving every ordered evidence row and without mutating findings, dispositions, reference results, metadata, scores, mappings, or exports. |
| AC-45 | Public local UI pages expose a document language, one global skip-to-main link, an explicit focusable main landmark, assertive alert semantics for errors, and polite status semantics for notices without changing visible review content or any audit/review/reference/package state. |
