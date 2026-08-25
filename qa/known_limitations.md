# Known limitations

- The score is a deterministic **review-status** measure, not a bid-readiness certification or estimate-quality score.
- Rules cannot establish correct quantities, rates, scope, productivity, contract compliance, profitability, or whether a negative/zero/duplicate value is intended.
- Rate outliers are only relative to positive rates in the same selected file; no market benchmark is used.
- Amount reconciliation excludes tax, discount, allowance, and rounding-policy interpretation.
- CSV ingestion currently assumes the first row is the header; XLSX has controlled early-row header scanning.
- The XLSX reader does not evaluate formulas, read legacy XLS/macro/encrypted workbooks, or support arbitrary advanced Excel features.
- Browser uploads use a deliberately narrow multipart parser for the estimate file and optional Activity/Resource reference CSV fields; it is not a general upload framework.
- Human finding dispositions and governed-reference results are temporary local session state; there is no persistent audit history.
- The current hierarchy key is conservative and resource-specific; some future Activity-level conflict checks may need rule-specific hierarchy semantics.
- Governed-reference matching is exact-code review evidence only. It does not establish codebook authority, current pricing, Crew/Production correctness, or HeavyBid import validity.
- No authentication, multi-user coordination, corrected-workbook export, direct HeavyBid integration, or production import automation exists.
- This is a reviewable MVP, not production-ready software.

