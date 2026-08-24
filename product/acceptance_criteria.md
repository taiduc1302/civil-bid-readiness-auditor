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
