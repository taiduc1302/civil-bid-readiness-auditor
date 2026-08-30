# Review Delta / Change Intelligence contract

## Purpose

Review Delta compares two already-exported, verified review-package ZIP snapshots and explains what changed between them. It is a comparison of archived review evidence, not a new estimate audit and not a judgement about which snapshot is correct.

## Safety boundary

Before comparison, both packages must pass the existing ZIP/integrity and semantic package validation. Comparison runs entirely in memory and creates no review session. Original estimate/reference bytes are not reconstructed or required.

The comparator must never claim that a changed finding, human disposition, or reference result is an improvement, regression, approval, or bid-readiness signal. It reports evidence drift only.

## Finding comparison

Findings are aligned by the deterministic anchor `(sheet, row, rule_id, field)`. Duplicate anchors fail closed because an ambiguous comparison would be misleading.

For aligned findings, deterministic evidence consists of severity, message, evidence text, and recommended action. Human review state consists of review status and reason.

Each aligned finding is classified as:

- `UNCHANGED`
- `REVIEW_CHANGED` — only human review status/reason changed
- `EVIDENCE_CHANGED` — deterministic evidence changed while review state did not
- `EVIDENCE_AND_REVIEW_CHANGED` — both changed

Anchors present only in the later snapshot are `ADDED`; anchors present only in the earlier snapshot are `REMOVED`.

## Reference comparison

Reference checks are aligned by `(reference_type, sheet, source_row, code)`. Duplicate anchors fail closed.

Aligned reference checks compare status, reference code, reference unit, and message. They are classified as `UNCHANGED` or `CHANGED`; unmatched checks are `ADDED` or `REMOVED`.

Reference snapshot metadata is compared separately by role (`activity` / `resource`) so a changed filename, revision/label, byte size, SHA-256, or authority-status evidence is visible even when row-level checks happen to match.

## Package lineage

The report records each package filename, SHA-256, package version, source estimate filename, and archived/live session provenance when available. Package identity differences are descriptive only.

## UI

A dedicated local `/compare-review-packages` screen accepts exactly two review-package ZIPs under the existing multipart size limits. Uploaded package bytes are not added to `SESSIONS` and are not written to disk.

The result page shows summary counts and bounded tables of changed findings, changed reference checks, and reference metadata drift. Unchanged rows are counted but omitted from the default detail tables.

## Explicit non-goals

- no deterministic re-audit;
- no estimate/source restoration;
- no automatic disposition changes;
- no reference reruns;
- no HeavyBid writer/import action;
- no claim that fewer findings or different review states mean a better estimate.
