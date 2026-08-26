# Fictional onboarding walkthrough

This walkthrough teaches the current **Civil Estimate Review Auditor** workflow using only bundled fictional data. It is a training/demo path, not evidence that the tool certifies an estimate, reference authority, or HeavyBid import.

## 1. Start with the synthetic estimate

Run the local app and choose **Run synthetic sample**. The sample intentionally contains missing values, duplicate/conflict conditions, reconciliation issues, unit inconsistencies, and other deterministic review prompts.

Learning goal: understand that the tool builds a review queue; a low legacy score is not a verdict on a real bid.

## 2. Review mapping before audit

On the mapping page, confirm the required fields:

- Description
- Quantity
- Unit
- Rate

Optional fields may include Amount, Category, Bid Item, Activity, Resource Type, and Resource Code. Do not treat auto-detected mappings as approval; they remain editable.

Learning goal: audit quality depends on explicit source-field mapping.

## 3. Run the deterministic audit

Run the audit and inspect:

- affected rows;
- Critical/High priority rows;
- finding count;
- sheet and source-row evidence;
- rule id, message, evidence, and recommended action.

Learning goal: findings are deterministic prompts requiring human review.

## 4. Use review views

Try several presentation-only views:

- `Priority` quick view;
- filter by rule or review status;
- free-text search;
- sort by source row, rule, sheet, review status, or priority;
- group by sheet, rule, or review status.

Use the skip links to move between filters, findings, and reference sections with the keyboard.

Learning goal: filtering/sorting/grouping does not change findings, severity, score, or saved review state.

## 5. Record human dispositions

Change a few fictional findings to states such as:

- Reviewed
- Needs correction
- Accepted
- Suppressed

Suppressed findings require a reason. Saving a disposition does not modify the source estimate or deterministic finding.

Learning goal: human review state is separate from audit output.

## 6. Try governed reference evidence on the HeavyBid-style fictional fixture

For the reference portion of the walkthrough, start a new audit using the bundled fictional HeavyBid-style resource export fixture and map its hierarchy/resource fields. Then upload the bundled fictional Activity and/or Resource reference CSV.

Optionally enter a revision/label such as `Training Rev A`.

Inspect the recorded evidence metadata:

- role;
- filename;
- revision/label exactly as typed;
- byte size;
- SHA-256;
- `authority_status=NOT_ESTABLISHED_BY_APP`.

Learning goal: filename/revision/hash improve traceability but do not establish that a reference is current, approved, or authoritative.

## 7. Review reference checks

Reference results can include:

- MATCH
- UNIT_MISMATCH
- NO_MATCH
- NOT_CHECKED

The tool does not invent replacement codes or perform physical unit conversion.

Learning goal: a MATCH is evidence of an exact lookup against the supplied snapshot, not approval of the codebook or a HeavyBid import.

## 8. Export the review package

Choose **Download review package ZIP**. The deterministic review snapshot can contain:

- `manifest.json`
- `findings.csv`
- `review.csv`
- `summary.html`
- `README.txt`
- `references.csv` when governed reference checks exist

The original estimate/reference file bytes are intentionally excluded.

Learning goal: the ZIP is a portable review snapshot, not a saved project database, bid approval, or HeavyBid artifact.

## Safety state to remember

The current controlled boundary remains:

- `NOT_PRODUCTION_READY=true`
- `NOT_ESTIMATOR_VALIDATED=true`
- `HEAVYBID_IMPORT_VALIDATED=false`

A future HeavyBid-readable candidate writer requires an explicitly approved schema/template and an independent real HeavyBid test import before import-validation status can change.
