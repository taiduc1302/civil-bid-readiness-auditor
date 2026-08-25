# Civil Estimate Review Auditor — PRD

## Product position

**Civil Estimate Review Auditor** is a local-first deterministic review tool for civil estimate exports. It helps an estimator find data-completeness, consistency, arithmetic, hierarchy, review-state, and governed-reference exceptions before a commercial decision.

It is deliberately a **review** product, not a bid-readiness certification system. The existing GitHub repository slug remains unchanged for link stability.

## Built baseline

1. Local browser interface for CSV/XLSX estimate exports.
2. Controlled early-row header detection for XLSX and CSV, common aliases, manual column mapping, and source-row preservation.
3. Fail-closed HeavyBid-style resource-export adapter with hierarchy-aware mapping.
4. Deterministic audit rules with rule-specific hierarchy context and conservative UOM normalization.
5. Review metrics plus the legacy review-status score.
6. Human finding dispositions stored only in the temporary local session; suppression requires a reason.
7. Findings CSV, review-state CSV, governed-reference CSV, and printable HTML management summary.
8. Exact Activity/Resource code + unit validation against explicitly supplied governed reference snapshots.
9. Optional evidence-only Crew Code / Production Rate comparison when values are explicit on both source and approved reference.
10. Controlled output eligibility manifest requiring approved project authorities, explicit approvals, resolved exceptions, revisions, and SHA-256 identities.
11. Versioned create-new-only candidate artifact planning with no-overwrite controls and approved schema/template identity.
12. Immediate pre-write SHA-256 revalidation of reviewed sources and schema authority.
13. Synthetic flat, hierarchical, HeavyBid-style, reference, and control-gate fixtures with regression coverage.
14. GitHub Actions test matrix on supported Python versions.

## Next product milestone

### P1 — review UX and package hardening

- migrate remaining runtime/UI/report strings to the new public product title;
- improve finding filtering/navigation and reference-review ergonomics;
- define a versioned local review-package export without introducing silent persistence;
- record explicit source/reference identity in downloadable review packages;
- improve end-to-end onboarding with a realistic fictional walkthrough.

### P2 — governed estimating references

- expose optional Crew Code / Production Rate evidence in the local UI only when explicit approved references are supplied;
- support explicit reference role/revision/hash metadata in the UI/session;
- keep historical cost/rate fields non-authoritative unless explicitly designated by estimator/project controls;
- add controlled reference disposition/review export.

### P3 — controlled HeavyBid candidate writer

A candidate writer is **not yet built**. It may be implemented only against an explicitly approved HeavyBid-readable schema/template authority and only after all existing gates pass.

The writer must:

- consume a passing eligibility manifest, versioned artifact plan, and fresh pre-write hash verification;
- map only explicit reviewed fields into the approved schema;
- create a new versioned `.xlsx` candidate and never overwrite the baseline;
- re-check immutable evidence immediately before writing;
- hash the created candidate and record a post-write manifest;
- preserve `NOT_PRODUCTION_READY`, `NOT_ESTIMATOR_VALIDATED`, and `HEAVYBID_IMPORT_VALIDATED=false`;
- require an independent real HeavyBid test import before import-validation status can change.

## Deferred / not built

Cloud collaboration, authentication, document/OCR extraction, AI summaries, market benchmarking, automatic corrections, direct HeavyBid database/API access, and production import automation.

## Non-goals and safeguards

The product does not establish correct rate, quantity, scope, productivity, price, margin, contract compliance, profitability, codebook authority, or bid readiness. It identifies review prompts from supplied data and explicitly supplied reference snapshots. All current application processing occurs in memory on `127.0.0.1`; no account, telemetry, or remote storage is used by the application.
