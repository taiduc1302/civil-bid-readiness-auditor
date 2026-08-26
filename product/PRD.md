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
7. Presentation-only review attention summary for Open findings, Needs correction findings, and governed reference exceptions, with explicit non-readiness empty-state language.
8. Stable temporary findings navigation with filters for severity, review status, rule, sheet, and free text plus common quick views.
9. Deterministic presentation-only findings sorting by priority, source, rule, sheet, or review status and optional grouping by sheet, rule, or review status.
10. Keyboard-friendly skip links, focus targets, visible focus styling, and review-table caption/labels.
11. Findings CSV, review-state CSV, governed-reference CSV, printable HTML management summary, and deterministic local ZIP review package.
12. Review-package manifest containing mappings, reviewed sheets, finding/review/reference counts, source filename, package version, reference evidence metadata, and safety flags while excluding original estimate/reference bytes.
13. Deterministic review-package integrity metadata plus an in-memory verifier for member names, allowed structure, byte sizes, SHA-256 values, and supported package identity. Integrity verification does not restore session state or establish approval/readiness.
14. Exact Activity/Resource code + unit validation against explicitly supplied governed reference snapshots.
15. Governed reference evidence metadata: role, filename, user-supplied revision/label, byte size, SHA-256, and explicit `NOT_ESTABLISHED_BY_APP` authority state.
16. Presentation-only governed reference result views: Exceptions by default, status/type filters, metadata-aware search, deterministic sort by status/source/code/type, optional grouping by status/type, and composed `/results` state with findings views.
17. Optional evidence-only Crew Code / Production Rate comparison when values are explicit on both source and approved reference.
18. Local fictional onboarding walkthrough covering mapping, review views, dispositions, governed reference evidence, and review-package export using bundled training data only.
19. Controlled output eligibility manifest requiring approved project authorities, explicit approvals, resolved exceptions, revisions, and SHA-256 identities.
20. Versioned create-new-only candidate artifact planning with no-overwrite controls and approved schema/template identity.
21. Immediate pre-write SHA-256 revalidation of reviewed sources and schema authority.
22. Synthetic flat, hierarchical, HeavyBid-style, reference, review-UX, onboarding, package-integrity, and control-gate fixtures with regression coverage.
23. GitHub Actions test matrix on supported Python versions.

## Next product milestone

### P1 — review UX hardening

- define any future review-package re-open/state-restoration workflow only after an explicit version/migration/ownership contract; package integrity verification is built, session restoration is not;
- consider carefully constrained bulk review actions only with explicit human ownership and fail-closed validation;
- add clearer first-run hints around optional governed reference workflows without implying authority;
- continue accessibility review for semantics beyond the current keyboard/focus pass;
- evaluate whether a compact per-group summary improves large review sessions without hiding individual evidence rows.

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

Cloud collaboration, authentication, document/OCR extraction, AI summaries, market benchmarking, automatic corrections, review-package session restoration/re-open, direct HeavyBid database/API access, and production import automation.

## Non-goals and safeguards

The product does not establish correct rate, quantity, scope, productivity, price, margin, contract compliance, profitability, codebook authority, or bid readiness. It identifies review prompts from supplied data and explicitly supplied reference snapshots. All current application processing occurs in memory on `127.0.0.1`; no account, telemetry, or remote storage is used by the application.
