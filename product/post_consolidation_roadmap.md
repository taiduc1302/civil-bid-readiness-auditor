# Post-consolidation product audit and roadmap

## Baseline after consolidation

The current `main` includes five distinct layers:

1. vendor-neutral deterministic audit core;
2. hierarchical civil estimate context and conservative UOM normalization;
3. fail-closed HeavyBid-style flat resource-export adapter;
4. temporary local human finding review/disposition workflow;
5. exact governed Activity/Resource reference validation against explicitly supplied CSV snapshots.

All current layers remain review aids. None certifies bid correctness or production HeavyBid import safety.

## Product audit findings

### A. Documentation drift — fix now

The implementation moved beyond the original P0 documentation. README, PRD, user workflow, claims, and acceptance criteria must describe review dispositions, governed references, and the HeavyBid-style boundary consistently.

### B. Product naming / positioning — decision required

`Civil Bid Readiness Auditor` can be read as a certification claim even though the product explicitly does not validate bid readiness. Evaluate a safer public product name such as `Civil Estimate Review Auditor` or `Civil Estimate QA Auditor` while preserving repository history and existing links.

Do not rename solely for cosmetics; decide after checking desired commercial positioning and migration impact.

### C. Ingestion technical debt

- XLSX scans early rows for a likely header; CSV currently assumes the first row is the header.
- The custom standard-library XLSX parser intentionally does not evaluate formulas or support arbitrary advanced workbook features.
- Reference CSVs are intentionally narrow and explicit.

Recommended next hardening: add controlled CSV header scanning with source-row preservation and regression fixtures.

### D. Hierarchy granularity technical debt

The current duplicate/conflict context key includes Bid Item, Activity, Resource Type, and Resource Code. This is conservative for resource-level comparisons, but it can prevent an Activity-level conflict from surfacing when different resource codes are present.

Do not simply remove Resource Code globally. Split rule context deliberately by rule semantics and add fixtures for Bid Item-, Activity-, and Resource-level conflicts.

### E. Review workflow UX

Current disposition state is temporary and local. This is safe for the MVP but limits multi-session review. Before adding persistence, define a versioned audit/review package with explicit source identity and no silent overwrite. Persistence should not blur deterministic findings with human dispositions.

### F. Governed reference evolution

Activity/Resource exact-code checking is a useful foundation. The next governed-reference layer may add Crew Code and Production Rate only when those fields are explicitly present in an approved reference snapshot and relevant export. Historical cost/rate snapshots must not become current pricing authority by default.

## Next milestone: controlled estimating review package

### Track 1 — product hardening

1. synchronize docs/claims/acceptance criteria;
2. decide public product naming;
3. add CSV header scanning parity with XLSX;
4. split hierarchy context by rule semantics;
5. improve filtering/navigation for findings and reference exceptions;
6. define versioned local audit/review package export.

### Track 2 — governed references

1. add reference source metadata: filename, role, revision/label, and SHA-256;
2. optionally validate exported Crew Code against an explicitly supplied approved reference;
3. optionally compare Production Rate only where both source and approved reference explicitly provide it;
4. classify results as review evidence, never automatic correction.

### Track 3 — HeavyBid-readable output gate

Do not implement production output merely because Track 2 passes.

A controlled HeavyBid-readable test artifact must require:

- populated project-specific Bid Item authority;
- project-specific baseline `Activities_Import` workbook;
- recorded source/reference identity and immutable hashes;
- resolved audit/reference exceptions or explicit estimator dispositions;
- estimator setup/quantity approval as applicable;
- commercial approval;
- versioned output that never overwrites the baseline.

Always preserve:

- `NOT_PRODUCTION_READY`
- `NOT_ESTIMATOR_VALIDATED`
- `HEAVYBID_IMPORT_VALIDATED=false`

Only a real independently reviewed HeavyBid test import can change the import-validation status.

## Explicitly deferred

- direct HeavyBid database/API access;
- automatic code replacement;
- automatic BCY/LCY/CCY or ton/tonne conversion;
- invented Bid Item/Activity/Resource/Crew/Production values;
- automatic correction of quantities or rates;
- production import automation;
- cloud collaboration/authentication until the local review contract is stable.
