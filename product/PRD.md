# Civil Bid Readiness Auditor — PRD

## Problem and user

An estimator needs a quick, defensible review of a spreadsheet export before a commercial decision. The product finds deterministic data-completeness, consistency, arithmetic, hierarchy, review-state, and governed-reference exceptions without asserting that a bid is commercially or technically correct.

## Built baseline

1. Local browser interface for CSV/XLSX estimate exports.
2. Worksheet detection, common aliases, manual column mapping, and a fail-closed HeavyBid-style resource-export adapter.
3. Deterministic audit rules with row/sheet evidence and conservative UOM normalization.
4. Review metrics plus the legacy review-status score.
5. Human finding dispositions stored only in the temporary local session; suppression requires a reason.
6. Findings CSV, review-state CSV, governed-reference CSV, and printable HTML management summary.
7. Optional exact-code validation against explicitly supplied Activity and/or Resource reference CSVs.
8. Synthetic flat, hierarchical, HeavyBid-style, and reference fixtures with regression coverage.
9. GitHub Actions test matrix on supported Python versions.

## Next product milestone

### P1 — product hardening

- synchronize public docs/claims with implemented capabilities;
- evaluate product naming so “bid readiness” cannot be interpreted as certification;
- improve CSV header detection to match XLSX behavior;
- review hierarchy granularity for duplicate/conflict rules;
- improve finding filtering/navigation and reference-review ergonomics;
- define versioned local audit/review package export without introducing silent persistence.

### P2 — governed estimating references

- extend explicitly supplied reference validation to optional Crew Code / Production Rate fields when those values are actually present in an approved reference snapshot and export;
- track source identity/revision/hash for governed references;
- keep historical cost/rate fields non-authoritative unless explicitly designated by the estimator/project controls.

### P3 — controlled HeavyBid-readable output gate

Only after explicit estimator, measurement-authority, and commercial approvals:

- require project-specific populated Bid Item authority and baseline Activities import workbook;
- preserve immutable source/reference identity and resolved exceptions;
- create a new versioned test-import artifact without overwriting a baseline;
- preserve `NOT_PRODUCTION_READY`, `NOT_ESTIMATOR_VALIDATED`, and `HEAVYBID_IMPORT_VALIDATED=false` until a real independent HeavyBid test import succeeds.

## Deferred / not built

Cloud collaboration, authentication, document/OCR extraction, AI summaries, market benchmarking, automatic corrections, direct HeavyBid database access, and production import automation.

## Non-goals and safeguards

The product does not establish correct rate, quantity, scope, productivity, price, margin, contract compliance, profitability, codebook authority, or bid readiness. It identifies review prompts from supplied data and explicitly supplied reference snapshots. All current application processing occurs in memory on `127.0.0.1`; no account, telemetry, or remote storage is used by the application.
