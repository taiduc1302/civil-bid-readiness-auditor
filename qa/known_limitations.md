# Known limitations

- The score is a deterministic **review-status** measure, not a bid-readiness certification or estimate-quality score.
- Rules cannot establish correct quantities, rates, scope, productivity, contract compliance, profitability, or whether a negative/zero/duplicate value is intended.
- Rate outliers are only relative to positive rates in the same selected file; no market benchmark is used.
- Amount reconciliation excludes tax, discount, allowance, and rounding-policy interpretation.
- CSV and XLSX ingestion use controlled early-row header detection, but unusual report layouts can still require manual mapping and unsupported structures may fail closed.
- The XLSX reader does not evaluate formulas, read legacy XLS/macro/encrypted workbooks, or support arbitrary advanced Excel features.
- Browser uploads use deliberately narrow multipart handling for known estimate/reference/review-package fields; it is not a general upload framework.
- Live human finding dispositions and governed-reference results remain temporary local session state; review-package ZIPs provide portable snapshots, not a persistent audit-history database.
- Rule-specific hierarchy context reduces false grouping, but the deterministic rules still cannot infer missing scope relationships that are not present in the supplied export.
- Governed-reference matching is exact-code review evidence only. It does not establish codebook authority, current pricing, Crew/Production correctness, or HeavyBid import validity.
- Review-package verification/preview checks package integrity and internal semantic consistency only; it cannot prove that archived findings still match current project/source files.
- Archived review continuation recreates only verified snapshot findings/dispositions/reference evidence. It does not restore original estimate/reference/package bytes, remap columns, rerun deterministic audit rules, or rerun governed references.
- Editable archived continuation currently supports at most 1000 findings or 1000 reference checks per package; larger packages remain read-only-verifiable/previewable.
- No authentication, multi-user coordination, corrected-workbook export, true source-file/session restoration, direct HeavyBid integration, or production import automation exists.
- This is a reviewable MVP, not production-ready software.

