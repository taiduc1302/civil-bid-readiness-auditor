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

Use the Review attention summary to see current Open / Needs correction findings. These are attention counts, not readiness or approval.

Learning goal: findings are deterministic prompts requiring human review.

## 4. Use review views

Try several presentation-only views:

- `Priority` quick view;
- filter by rule or review status;
- free-text search;
- sort by source row, rule, sheet, review status, or priority;
- group by sheet, rule, or review status.

Use the skip links to move between attention, filters, findings, and reference sections with the keyboard.

Learning goal: filtering/sorting/grouping does not change findings, severity, score, or saved review state.

## 5. Record human dispositions

Change a few fictional findings to states such as:

- Reviewed
- Needs correction
- Accepted
- Suppressed

Suppressed findings require a reason. Saving a disposition does not modify the source estimate or deterministic finding.

Learning goal: human review state is separate from audit output.

## 6. Start the one-click structured fictional demo

Return to the local **Fictional onboarding walkthrough** page and choose **Run structured fictional sample**. This loads exactly the bundled `synthetic_heavybid_style_resource_export.csv` and opens the normal editable mapping page.

The HeavyBid-style mapping may be preselected using supported exact aliases, but it remains editable and reviewable. No audit or reference validation is run automatically.

Learning goal: structured profile detection is a mapping convenience, not approval or direct HeavyBid integration.

## 7. Download and manually apply fictional reference snapshots

From the guide, use:

- **Download fictional Activity reference CSV** → `synthetic_activity_reference.csv`
- **Download fictional Resource reference CSV** → `synthetic_resource_reference.csv`

After auditing the structured fictional estimate, upload one or both files manually in **Governed reference validation**. References are never auto-applied by the demo.

Optionally enter a revision/label such as `Training Rev A`.

Inspect the recorded evidence metadata:

- role;
- filename;
- revision/label exactly as typed;
- byte size;
- SHA-256;
- `authority_status=NOT_ESTABLISHED_BY_APP`.

Learning goal: filename/revision/hash improve traceability but do not establish that a reference is current, approved, or authoritative.

## 8. Review reference checks

Reference results can include:

- MATCH
- UNIT_MISMATCH
- NO_MATCH
- NOT_CHECKED

The default view shows Exceptions. You can filter by status/type, search reference metadata, sort, and group without changing the stored checks.

The tool does not invent replacement codes or perform physical unit conversion.

Learning goal: a MATCH is evidence of an exact lookup against the supplied snapshot, not approval of the codebook or a HeavyBid import.

## 9. Export and verify the review package

Choose **Download review package ZIP**. The deterministic review snapshot can contain:

- `manifest.json`
- `integrity.json`
- `findings.csv`
- `review.csv`
- `summary.html`
- `README.txt`
- `references.csv` when governed reference checks exist

The original estimate/reference file bytes are intentionally excluded.

Return to the home page and choose **Verify review package ZIP** to check recorded member structure, SHA-256 values, and semantic snapshot consistency in memory. The verifier can display a bounded read-only snapshot but still creates no review session.

Learning goal: verification proves recorded package integrity/consistency, not current source-file truth.

## 10. Continue archived human review without re-auditing

After verification, open **Archived review continuation**. Select the same ZIP again and acknowledge that this is continuation of archived review evidence only.

The continuation session recreates:

- archived deterministic finding evidence;
- the human disposition state stored in `review.csv`;
- archived governed reference checks and reference metadata when present.

It does **not** recreate:

- original estimate bytes;
- original reference bytes;
- parsed estimate rows for remapping;
- an `audit_sheets` source for deterministic re-audit/reference rerun.

You can continue filters, single-row review, explicit bulk review, and review/package exports. Archived reference evidence is read-only. A new package exported from this continuation records the prior package filename/SHA-256 and `session_context.mode=archived_review_snapshot` so it cannot look like a fresh audit.

Current editable continuation supports at most 1000 findings/reference checks; larger packages remain available for read-only verification/preview.

Learning goal: continuing human review of archived evidence is materially different from rerunning an audit against the original estimate.

## Safety state to remember

The current controlled boundary remains:

- `NOT_PRODUCTION_READY=true`
- `NOT_ESTIMATOR_VALIDATED=true`
- `HEAVYBID_IMPORT_VALIDATED=false`

A future HeavyBid-readable candidate writer requires an explicitly approved schema/template and an independent real HeavyBid test import before import-validation status can change.
