# Civil Bid Readiness Auditor — PRD

## Problem and user

An estimator needs a quick, defensible pre-submit review of a spreadsheet export. The product finds deterministic data-completeness, consistency, and arithmetic exceptions without asserting a bid is commercially or technically correct.

## P0 (required)

1. Local browser interface that accepts CSV and XLSX estimate exports.
2. Detect worksheets and common column aliases; permit manual column mappings if automatic mapping is incomplete.
3. Validate input and show useful errors without retaining the file.
4. Run transparent rules and show severity, message, evidence, record/sheet, and recommended action.
5. Calculate a repeatable, explainable **review-status score**.
6. Export findings CSV and a printable HTML management summary.
7. Include a synthetic sample project and expected results.

## P1 (not built)

Configurable rule weights, saving audit configurations, corrected-workbook export, and quote-comparison import.

## P2 (not built)

Integrations, cloud collaboration, document/OCR extraction, benchmarking, and AI summaries.

## Non-goals and safeguards

The product does not validate rate, quantity, scope, productivity, price, margin, contract compliance, profitability, or bid readiness. It only identifies deterministic review prompts from values supplied in the file. All input processing happens in memory on `127.0.0.1`; no account, API, telemetry, or remote storage is used.

