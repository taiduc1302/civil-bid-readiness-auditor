# Review Timeline contract

## Purpose

Review Timeline reconstructs one neutral multi-snapshot chain from independently verified portable Review Delta evidence bundles. It answers only: **which archived review-package snapshots are structurally connected by the supplied verified Delta transitions, what evidence-change counts were recorded on each transition, and what bounded changed-evidence rows are present in the verifier-approved preview?**

It is not a calendar timeline, quality trend, readiness trend, estimate audit, source-currentness check, or HeavyBid validation workflow.

## Inputs

One local request accepts **2–10** `civil-estimate-review-delta-export` v1 ZIPs.

Every bundle is independently processed through the existing strict `verify_review_delta_export()` contract before any lineage, counts, or detail rows are used. Uploaded bytes are held only for the request and are not added to `SESSIONS` or written to disk by the application.

Each Delta ZIP is bounded by the Delta verifier's existing **50 MB** compressed-bundle limit. Because a valid Timeline request may contain several valid Delta bundles, `/review-timeline` uses a dedicated multipart parser with an aggregate bound of **502 MB including form overhead** instead of the legacy general **26 MB** upload cap. This larger request envelope does not relax the Delta verifier's per-bundle/member/uncompressed limits: each bundle must still pass independent verification before it contributes any evidence.

## Ordering authority

Upload order, Delta filenames, review-package filenames, source filenames, filesystem timestamps, and inferred dates are not ordering authorities.

Each verified Delta transition carries exact review-package SHA-256 lineage:

`Earlier review-package SHA-256 -> Later review-package SHA-256`

The timeline order is reconstructed only from those exact package identities.

For each distinct review-package SHA-256, the following semantic lineage must also agree wherever that snapshot appears in multiple Delta bundles:

- package format = `civil-estimate-review-package`;
- package version = 1;
- package integrity version = 1;
- source session mode;
- source filename; and
- rows reviewed.

A review-package filename is descriptive only. If the same package SHA-256 appears under different filenames in adjacent Delta bundles, all recorded names are preserved as sorted aliases and do not break continuity.

## Linear-chain requirement

The supplied transitions must resolve to exactly one connected acyclic linear chain.

The builder fails closed for:

- fewer than 2 or more than 10 Delta bundles;
- an individual Delta bundle above its supported 50 MB compressed size or any bundle that otherwise fails independent verification;
- an aggregate Timeline request above its bounded multipart envelope;
- duplicate Delta-bundle bytes/SHA-256;
- duplicate `Earlier -> Later` transition edges;
- a self-transition whose Earlier and Later package SHA-256 are the same;
- invalid review-package SHA-256 lineage;
- unsupported review-package package/integrity versions;
- conflicting semantic lineage for the same review-package SHA-256;
- more than one outgoing edge from a snapshot (branch);
- more than one incoming edge to a snapshot (merge);
- cycles; or
- disconnected transition sets.

The output contains the structurally ordered snapshots and transitions only after every supplied edge and snapshot belongs to that one chain.

## Transition evidence

For each ordered transition the model records:

- uploaded Delta filename as a descriptive label;
- exact Delta bundle SHA-256;
- Earlier review-package SHA-256;
- Later review-package SHA-256;
- verified finding-change counts;
- verified standard Activity/Resource reference-check change counts;
- verified standard reference-metadata change counts; and
- a narrower bounded detail preview derived only from the already verified Delta preview.

The Timeline detail preview never parses raw Delta members independently and never bypasses `verify_review_delta_export()`. It accepts only the verifier-returned changed rows and applies additional per-transition caps:

- up to **25 finding-change rows**;
- up to **25 governed-reference-change rows**; and
- up to **10 reference-metadata-change rows**.

`UNCHANGED` rows remain represented by the verified transition count summary but are deliberately excluded from the detail preview. The model records the verified changed-row total, rows shown, and additional rows omitted for each category. Browser omission is a presentation bound only; it does not alter verified counts or imply improvement/regression.

## Browser presentation

`/review-timeline` renders:

- an ordered snapshot table;
- an ordered transition table;
- package and Delta SHA-256 evidence;
- descriptive filename aliases and source metadata;
- per-transition change counts; and
- collapsed bounded detail tables for changed finding, governed-reference, and reference-metadata evidence.

Every detail cell is escaped and limited to **500 characters** before rendering. The page explicitly states when verified changed rows are omitted from the browser preview. User-supplied labels and archived evidence text are never rendered as active HTML.

The page creates no review session and reruns no estimate/reference logic.

## Safety boundary

The model explicitly preserves:

- `session_created=false`;
- `re_audit_performed=false`;
- `source_currency_inferred=false`;
- `quality_trend_inferred=false`;
- `improvement_regression_inferred=false`;
- `readiness_inferred=false`; and
- `heavybid_import_validated=false`.

Therefore a structurally valid chain or displayed changed-evidence row does **not** establish:

- calendar dates or chronological elapsed time;
- that snapshots still match current project/source files;
- that snapshots belong to the same commercial revision merely because hashes connect;
- estimate correctness or completeness;
- improvement or regression;
- estimator approval or reference authority;
- bid readiness; or
- HeavyBid import validity.

Fewer findings, more reviewed dispositions, fewer reference exceptions, or any before/after detail must never be converted into an automatic trend/quality score or a generated better/worse narrative.

## Operational Crew / Production boundary

Operational Crew Code / Production Rate evidence is temporary-session evidence and is outside review-package v1 and Delta-export v1. Review Timeline therefore does not reconstruct, infer, summarize, or invent operational evidence.

## Explicit non-goals

- no calendar/timestamp inference;
- no persistent timeline database;
- no source-file restoration or current-source verification;
- no estimate/reference rerun;
- no automatic review-state changes;
- no trend/quality/readiness score;
- no AI better/worse narrative;
- no HeavyBid writer/import action;
- no invented Bid Item, Activity, Resource, Crew, Production, Rate, or Quantity values.
