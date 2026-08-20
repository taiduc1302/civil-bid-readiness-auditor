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
