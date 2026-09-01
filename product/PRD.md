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
9. Deterministic presentation-only findings sorting by priority, source, rule, sheet, or review status and optional grouping by sheet, rule, or review status. Group headings include compact severity/Open/Needs correction composition without hiding individual evidence rows.
10. Accessibility semantics across the public local UI: document language, one global skip-to-main link, an explicit focusable main landmark, visible focus styling, assertive alert semantics for errors, polite status semantics for notices, plus review-table caption/labels.
11. Findings CSV, review-state CSV, governed-reference CSV, printable HTML management summary, and deterministic local ZIP review package.
12. Review-package manifest containing mappings, reviewed sheets, finding/review/reference counts, source filename, package version, reference evidence metadata, and safety flags while excluding original estimate/reference bytes.
13. Deterministic review-package integrity metadata plus an in-memory verifier for member names, allowed structure, byte sizes, SHA-256 values, and supported package identity.
14. Semantic package validation after integrity succeeds: required safety state, finding/review evidence agreement, supported review states, manifest count consistency, and optional reference status/type/metadata consistency must pass even when package hashes were internally recomputed.
15. A local read-only review-package verification/preview screen that accepts one ZIP, performs integrity + semantic checks in memory, and displays a bounded escaped snapshot of review/finding/reference evidence without rendering packaged HTML/README as active content. At most 100 finding rows and 100 reference rows are shown; no review session is created/restored.
16. Explicit archived review continuation: after separate upload, acknowledgement, and re-verification, a review-package can create a temporary `archived_review_snapshot` session containing only archived findings, human dispositions, and recorded reference evidence. Original estimate/reference/package bytes are not retained; remapping, deterministic re-audit, and reference rerun source state are unavailable. Re-exported continuation packages carry source package SHA-256 and no-re-audit/no-source-bytes provenance. Current editable continuation is capped at 1000 findings/reference checks; larger packages remain read-only-verifiable.
17. Exact Activity/Resource code + unit validation against explicitly supplied governed reference snapshots.
18. Governed reference evidence metadata: role, filename, user-supplied revision/label, byte size, SHA-256, and explicit `NOT_ESTABLISHED_BY_APP` authority state.
19. Presentation-only governed reference result views: Exceptions by default, status/type filters, metadata-aware search, deterministic sort by status/source/code/type, optional grouping by status/type, compact status composition in reference-type group headings, and composed `/results` state with findings views.
20. Separate source-backed Operational Activity evidence UI for explicitly mapped Activity + Crew Code / Production Rate values. The user supplies a separate Activity operational CSV, only overlapping explicit fields are compared, row linkage plus upload revision/size/SHA-256 evidence is preserved, stale evidence clears when the mapped source evidence changes, and no crew/production value is inferred or calculated. Operational evidence remains session-only and outside review-package v1, archived continuation, Review Delta, and the existing reference CSV until a separate compatibility/version contract is defined.
21. Local fictional onboarding walkthrough covering mapping, review views, dispositions, governed reference evidence, review-package export, verification, archived review continuation, and Review Delta using bundled training data only.
22. Fixed one-click fictional structured demo kit: exactly one bundled HeavyBid-style synthetic estimate plus fixed Activity/Resource reference-download routes; references remain manual and are never auto-applied.
23. Fail-closed bulk finding review plan v2: explicit selected finding IDs only, supported human statuses, suppression reason control, explicit human-ownership acknowledgement, expected current review states, full/selected finding fingerprints, and a plan content SHA-256 integrity check.
24. Pure atomic bulk review apply-to-copy validation: revalidates plan identity/digest, safety flags, targets/count, status/reason, full and selected finding fingerprints, and exact expected current states before returning a separate dispositions mapping. Inputs remain unchanged.
25. Explicit-selection two-step browser bulk review: individually checked findings only, no select-all or implicit filtered-view scope, target status/reason plus ownership acknowledgement, preview with exact rows and no mutation, separate confirmation, one-time plan token, immediate plan revalidation, and one atomic session dispositions assignment only after validation succeeds. Stale/replayed/replaced plans fail closed.
26. Sanitized presentation-view context preservation across review saves and bulk preview/cancel/apply/error paths. Only known findings/reference view keys are retained; token/unknown/redirect-like parameters are discarded and the server constructs local `/results` return URLs itself.
27. Controlled output eligibility manifest requiring approved project authorities, explicit approvals, resolved exceptions, revisions, and SHA-256 identities.
28. Versioned create-new-only candidate artifact planning with no-overwrite controls and approved schema/template identity.
29. Immediate pre-write SHA-256 revalidation of reviewed sources and schema authority.
30. Synthetic flat, hierarchical, HeavyBid-style, reference, operational-reference, review-UX, onboarding, package-integrity/semantic-preview, archived-review continuation, accessibility, bulk-review planning/application/UI, view-context, Review Delta export, and control-gate fixtures with regression coverage.
31. GitHub Actions test matrix on supported Python versions.
32. Review Delta / Change Intelligence: an in-memory comparison of two independently verified review-package snapshots. Findings align by unique sheet/row/rule/field anchors so deterministic evidence changes are separated from human status/reason changes; governed reference checks and role-linked reference metadata are compared independently. Ambiguous duplicate anchors fail closed, no review session is created, no audit/reference logic is rerun, and no improvement/correctness/readiness judgement is inferred. The same pair can be re-verified and exported as a separate deterministic `civil-estimate-review-delta-export` v1 ZIP with full comparison JSON, spreadsheet-safe delta CSVs, lineage/count/safety manifest, README, and SHA-256/size integrity metadata; original package/source bytes and session-only operational evidence are not embedded.
33. Temporary-session concurrency hardening for the local `ThreadingHTTPServer`: one in-memory lock per session token serializes state-sensitive read/validate/write operations while different tokens remain independently concurrent. Active lookup refreshes a 30-minute idle timeout, expiry skips a session while an active request holds its lock, and one-time bulk plans cannot be applied twice by concurrent requests.
34. Explicit deterministic public-runtime composition: one startup composer invokes the idempotent accessibility, bulk-review, review-view-context, operational-reference, archived-review, and Review Delta feature installers. Content modules such as onboarding are side-effect free, and review-only renderer augmentation uses stable internal page identity rather than user-visible display-title strings.

## Next product milestone

### P1 — review UX hardening

- archived human-review continuation is built; any future **true estimate/source restoration or re-audit** requires a separate package/version/migration/ownership contract that supplies and verifies the original source bytes rather than treating archived review evidence as current input;
- Review Delta comparison and portable evidence export are built; any future timeline/trend presentation must preserve neutral evidence-drift semantics and must not become an automatic quality score;
- evaluate additional fictional first-run guidance only when it demonstrates already-built behavior rather than implying reference authority or automatic decisions;
- keep bulk actions limited to explicit selections and preserve one-time preview/revalidation semantics; do not add select-all or implicit view-based scope.

### P2 — governed estimating references

- if Crew Code / Production Rate evidence is ever added to portable review packages, define a new explicit package/version compatibility contract and update semantic verification, archived continuation, and Review Delta together rather than overloading package-v1 reference rows;
- retain historical cost/rate fields as non-authoritative unless explicitly designated by estimator/project controls;
- evaluate explicit reference-review dispositions separately from deterministic code/unit and operational evidence matching.

### P3 — controlled HeavyBid candidate writer

A candidate writer is **not yet built**. It may be implemented only against an explicitly approved HeavyBid-readable schema/template authority and only after all existing gates pass.

The writer must:

- consume a passing gate + versioned artifact plan + fresh pre-write verification;
- map only explicit reviewed fields into the approved schema;
- create a new versioned `.xlsx` candidate and never overwrite the baseline;
- re-check immutable evidence immediately before writing;
- hash the created candidate and record a post-write manifest;
- preserve `NOT_PRODUCTION_READY`, `NOT_ESTIMATOR_VALIDATED`, and `HEAVYBID_IMPORT_VALIDATED=false`;
- require an independent real HeavyBid test import before import-validation status can change.

## Deferred / not built

Cloud collaboration, authentication, document/OCR extraction, AI summaries, market benchmarking, automatic corrections, true source-file/session restoration or deterministic re-audit from a review package, portable-package operational Crew/Production evidence, automatic Review Delta quality/trend scoring, direct HeavyBid database/API access, and production import automation.

## Non-goals and safeguards

The product does not establish correct rate, quantity, scope, productivity, price, margin, contract compliance, profitability, codebook authority, or bid readiness. It identifies review prompts from supplied data and explicitly supplied reference snapshots. All current application processing occurs in memory on `127.0.0.1`; no account, telemetry, or remote storage is used by the application.