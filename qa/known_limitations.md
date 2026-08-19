# Known limitations

- The score is a deterministic **review-status** measure, not a bid-readiness certification or estimate-quality score.
- Rules cannot establish correct quantities, rates, scope, productivity, contract compliance, profitability, or whether a negative/zero/duplicate value is intended.
- Rate outliers are only relative to positive rates in the same selected file; no market benchmark is used.
- Amount reconciliation excludes tax, discount, allowance, and rounding-policy interpretation.
- The XLSX reader does not evaluate formulas, read legacy XLS/macro/encrypted workbooks, or support arbitrary advanced Excel features.
- The multipart parser supports a single ordinary browser file field and is deliberately not a general upload framework.
- No authentication, multi-user coordination, audit-history persistence, corrected-workbook export, or integrations exist.
- This is a reviewable MVP, not production-ready software.

