# Current product audit and roadmap

This file supersedes the earlier post-consolidation checkpoint. Several items that were originally listed as future work are now implemented on `main`; this roadmap records the current boundary instead of preserving those items as if they were still open.

## Current built baseline

The current product includes:

1. vendor-neutral deterministic CSV/XLSX estimate review with controlled early-row header detection and source-row preservation;
2. optional Bid Item / Activity / Resource hierarchy context with rule-specific conflict/duplicate semantics and conservative UOM normalization;
3. a fail-closed HeavyBid-style flat resource-export adapter that only maps supported explicit headers;
4. temporary local human finding dispositions, filtering, sorting, grouping, attention summaries, explicit-selection two-step bulk review, and preserved view context;
5. governed Activity/Resource exact code + unit validation against explicitly supplied reference snapshots with evidence metadata;
6. deterministic review-package export, integrity verification, semantic snapshot validation, and bounded read-only preview;
7. acknowledged archived-review snapshot continuation for human disposition work only, without source restoration, deterministic re-audit, or reference rerun;
8. Review Delta / Change Intelligence between two independently verified review-package snapshots without re-auditing either source;
9. fictional onboarding and structured demo data;
10. controlled HeavyBid-oriented output eligibility, artifact planning, and immediate pre-write evidence revalidation guardrails.

All current layers remain review aids. None certifies estimate correctness, reference authority, bid readiness, estimator approval, or production HeavyBid import safety.

## P1 — reliability and review-workflow hardening

### 1. Temporary session-state hardening

The runtime uses a threaded local HTTP server while review state is held in shared in-memory sessions. Harden per-session mutation semantics so concurrent review, bulk, audit, and reference requests cannot overwrite one another or consume a one-time plan twice. Define the 30-minute lifetime explicitly as an idle-timeout policy or another tested policy so active review does not unexpectedly expire only because the session is old.

Tracked in issue #67.

### 2. Runtime feature composition

The public server is currently assembled through compatibility wrappers and idempotent installers. Remove behavior that depends on incidental import order or user-visible page-title strings, while preserving all current routes and fail-closed behavior. Add a fully composed runtime regression test.

Tracked in issue #68.

### 3. Documentation and release-evidence consistency

Keep README, PRD, workflow, claims, acceptance criteria, NOTICE, and roadmap aligned with the implemented product. `ALLOWLIST_MANIFEST.json` is historical/stale relative to the current tree and must either become an explicitly historical snapshot artifact or be regenerated from an exact release tree with verification.

Tracked in issue #70 for the allowlist decision.

### 4. Review Delta presentation/export conveniences

Review Delta is already built. Future P1 work may add neutral export/presentation conveniences, such as a deterministic CSV/JSON comparison artifact or clearer lineage display. Do not convert evidence drift into an automatic quality, improvement, or readiness score.

### 5. Archived continuation scale only when justified

Editable archived continuation currently caps supported snapshots at 1000 findings or 1000 reference checks. Do not raise the limit by bypassing semantic validation. If real use requires larger snapshots, define a reviewed full-snapshot/streaming validation contract first.

## P2 — governed estimating references

### 1. Expose Crew Code / Production Rate evidence in the browser

The pure evidence-only operational comparison module and tests already exist, but the normal browser reference flow does not yet invoke them. Add this only through an explicit governed-reference UI contract, compare only fields supplied on both sides, preserve source/reference provenance, and define package-version compatibility before adding new archived evidence types.

Tracked in issue #69.

### 2. Reference-review dispositions

Evaluate a separate human-review disposition model for governed reference exceptions. Keep deterministic reference results immutable and do not treat a human disposition as reference authority.

### 3. Historical cost/rate evidence

Historical cost/rate fields remain non-authoritative unless a separate estimator/project-control contract explicitly designates a snapshot and its intended use. Do not silently promote historical values into current pricing authority.

## P3 — controlled HeavyBid candidate writer

A HeavyBid-readable candidate writer is **not built** and remains blocked until an explicitly approved real schema/template authority is available.

Existing guardrails already cover output eligibility, create-new-only artifact planning, approved schema identity, and immediate pre-write hash revalidation. The remaining controlled path is:

1. obtain and explicitly approve the exact HeavyBid-readable schema/template authority and project-specific required authorities;
2. consume only a passing gate, versioned artifact plan, and fresh pre-write verification;
3. map only explicit reviewed values into that approved schema;
4. create a new versioned candidate and never overwrite the baseline;
5. hash the produced candidate and record a post-write manifest;
6. preserve `NOT_PRODUCTION_READY=true`, `NOT_ESTIMATOR_VALIDATED=true`, and `HEAVYBID_IMPORT_VALIDATED=false`;
7. perform an independent real HeavyBid test import and human review before import-validation status can change.

Issue #14 remains the governing HeavyBid writer/test-import boundary. Do not implement a generic XLSX writer and label it HeavyBid-compatible.

## Governance / repository controls

GitHub Actions currently runs the unit test suite on Python 3.12 and 3.13 for pull requests and pushes to `main`. The `main` branch is not currently protected, so those checks are not enforced as merge requirements. Enabling branch protection / required status checks is recommended before treating the repository as a controlled release workflow.

## Explicitly deferred / non-goals

- cloud collaboration, accounts, or authentication;
- OCR/document extraction and AI-generated estimate decisions;
- automatic code replacement or automatic quantity/rate correction;
- automatic BCY/LCY/CCY, ton/tonne, density, swell/shrink, or currency conversions without an explicit governed policy;
- invented Bid Item, Activity, Resource, Crew, Production, Quantity, or Rate values;
- true source-file/session restoration or deterministic re-audit from a review-package v1 snapshot;
- direct HeavyBid database/API access;
- production HeavyBid import automation.
