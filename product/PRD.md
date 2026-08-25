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
7. Stable temporary results navigation with filters for severity, review status, rule, sheet, and free text plus common quick views.
8. Findings CSV, review-state CSV, governed-reference CSV, printable HTML management summary, and deterministic local ZIP review package.
9. Review-package manifest containing mappings, reviewed sheets, finding/review/reference counts, source filename, package version, reference evidence metadata, and safety flags while excluding original estimate/reference bytes.
10. Exact Activity/Resource code + unit validation against explicitly supplied governed reference snapshots.
11. Governed reference evidence metadata: role, filename, user-supplied revision/label, byte size, SHA-256, and explicit `NOT_ESTABLISHED_BY_APP` authority state.
12. Optional evidence-only Crew Code / Production Rate comparison when values are explicit on both source and approved reference.
13. Controlled output eligibility manifest requiring approved project authorities, explicit approvals, resolved exceptions, revisions, and SHA-256 identities.
14. Versioned create-new-only candidate artifact planning with no-overwrite controls and approved schema/template identity.
15. Immediate pre-write SHA-256 revalidation of reviewed sources and schema authority.
16. Synthetic flat, hierarchical, HeavyBid-style, reference, review-UX, and control-gate fixtures with regression coverage.
17. GitHub Actions test matrix on supported Python versions.

## Next product milestone

### P1 — review UX hardening

- add a realistic fictional end-to-end onboarding walkthrough inside the local app;
- add optional sorting/grouping of findings and reference exceptions without changing deterministic data;
- evaluate package-integrity / re-open semantics before any resumable review workflow is introduced;
- consider carefully constrained bulk review actions only with explicit human ownership and fail-closed validation;
- perform an accessibility and keyboard-navigation pass.

### P2 — governed estimating references

- expose operational Crew Code / Production Rate evidence in the local UI only when explicit governed references are supplied;
- retain historical cost/rate fields as non-authoritative unless explicitly designated by estimator/project controls;
- evaluate explicit reference-review dispositions separately from deterministic code/unit matching.

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
