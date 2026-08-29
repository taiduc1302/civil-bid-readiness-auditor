# Archived review continuation contract

## Purpose

Archived review continuation lets a reviewer resume **human disposition work** from a previously exported, verified Civil Estimate Review Auditor review-package ZIP.

It is deliberately **not** estimate restoration and **not** deterministic re-audit.

Review-package v1 intentionally excludes the original estimate and reference file bytes. Therefore a continuation session cannot prove that the archived findings still describe the current project files.

## Entry gate

Continuation is a separate flow from read-only package verification.

Before a temporary archived session is created, the app must:

1. receive the review-package ZIP again;
2. require explicit acknowledgement that the flow is archived review only;
3. pass the existing ZIP structure/path/size/SHA-256 verifier;
4. pass the existing semantic snapshot consistency checks;
5. reconstruct the complete supported snapshot evidence within the continuation safety limit.

The verifier screen itself remains read-only and creates no session.

## Session identity

A continuation session is marked:

`session_mode = archived_review_snapshot`

The session records the source package filename, SHA-256, package/integrity versions, and source session mode. It does **not** retain the uploaded package bytes.

## Available actions

An archived continuation may:

- filter, search, sort, and group archived findings;
- inspect archived governed reference checks and recorded metadata;
- change human finding dispositions;
- use the existing explicit-selection, preview, one-time bulk review flow;
- export findings/review/reference CSVs;
- export a new review-package snapshot.

## Explicitly unavailable actions

An archived continuation may not:

- remap source estimate columns;
- rerun deterministic audit rules;
- replace or rerun Activity/Resource governed references;
- claim that original estimate/reference bytes were restored;
- claim that a current project file matches the archived evidence;
- establish estimator approval, reference authority, bid readiness, or HeavyBid import validity.

The reconstructed session intentionally has no `audit_sheets` and has an empty parsed `sheets` set, so accidental legacy audit paths fail closed before replacing the archived result.

## Archived metrics

The legacy compatibility score displayed in an archived continuation is reconstructed only from stored finding severities using the existing legacy weighting formula. It is labeled as archived-snapshot-derived. No deterministic rules are rerun.

## Reference evidence

Existing reference checks remain visible as historical snapshot evidence. Reference upload/replacement controls are removed from the archived review view. The reference rerun endpoint also lacks the required audited source rows and fails closed.

## Re-export provenance

A review package exported from an archived continuation must contain `session_context` with:

- `mode = archived_review_snapshot`;
- `continuation_only = true`;
- `re_audit_performed = false`;
- `original_estimate_bytes_available = false`;
- `original_reference_bytes_available = false`;
- `reference_rerun_available = false`;
- source package filename, SHA-256, format/version/integrity identity, and prior session mode.

This prevents a second-generation package from looking like a fresh estimate audit.

## Current safety limit

Editable archived continuation currently supports at most **1000 findings or 1000 governed reference checks** in one package. Packages above that threshold can still use read-only verification/preview but fail closed before creating an editable continuation session.

This limit exists because the current semantic snapshot inspector is intentionally bounded. Raising it requires a separate reviewed streaming/full-snapshot contract rather than silently bypassing the current bound.

## HeavyBid boundary

Archived review continuation does not change HeavyBid controls. It does not create or validate HeavyBid import artifacts and preserves the existing safety state:

- `NOT_PRODUCTION_READY=true`
- `NOT_ESTIMATOR_VALIDATED=true`
- `HEAVYBID_IMPORT_VALIDATED=false`
