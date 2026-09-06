# Review Timeline evidence-export contract

## Status

This document defines `civil-estimate-review-timeline-export` v1. The deterministic **in-memory builder and independent verifier core are implemented** in `app/review_timeline_export.py` under AC-64. Distribution remains deliberately unbuilt: there is no browser export route, download control, accepted Timeline-export upload/input route, persistence layer, or cross-request/cross-route transfer of verified state.

The existing Review Timeline browser preview remains bounded presentation only. It is not the portable full-evidence export and is not export authority.

## Purpose and input authority

The export preserves verified archived evidence chronology only. Creation starts only from the same **2–10 Delta ZIPs** accepted by Review Timeline. Every input must freshly and independently pass `verify_review_delta_export()` and the set must satisfy the existing connected, acyclic, linear Earlier→Later review-package SHA-256 lineage rules.

The Delta verifier may expose its full canonical comparison only as an opt-in in-process result **after** all normal ZIP, integrity, semantic, count, anchor, CSV, manifest, and safety checks have succeeded. The exporter must use that verified full comparison. It must never parse raw unverified Delta members through a side path.

The export contains every verified finding, governed-reference, and reference-metadata change row from each Delta, **including `UNCHANGED` rows**. The bounded browser/Timeline verifier preview is not sufficient: truncated preview rows are **not sufficient export evidence**.

## Format identity and exact root members

Export identity:

- `civil-estimate-review-timeline-export`
- version `1`

Integrity identity:

- `civil-estimate-review-timeline-export-integrity`
- version `1`

The exact root member set is:

- `manifest.json`
- `review_timeline.json`
- `snapshots.csv`
- `transitions.csv`
- `finding_changes.csv`
- `reference_changes.csv`
- `reference_metadata_changes.csv`
- `README.txt`
- `integrity.json`

All members are root files. Directories, alternate paths, duplicate names, missing members, unexpected members, encryption, and unsafe paths are invalid. This export is neither a review-package nor a Review Delta export and must not be accepted by archived continuation, Review Delta comparison, Review Delta verification, or the existing Review Timeline input route.

## Canonical `review_timeline.json`

`review_timeline.json` is the sole canonical evidence member. It contains only:

- the supported export identity/version;
- ordered `snapshots` reconstructed from exact review-package SHA-256 continuity;
- ordered `transitions` corresponding one-to-one with adjacent snapshots; and
- the exact safety object below.

Each snapshot records zero-based chain index, exact review-package SHA-256, supported package/integrity versions, source session mode, source filename, rows reviewed, and sorted unique descriptive package-filename aliases.

Each transition records zero-based chain index, descriptive uploaded Delta filename, exact Delta-export ZIP SHA-256, exact Earlier/Later review-package SHA-256 values, recomputed finding/reference/reference-metadata counts, and complete canonical verified change-row arrays. Delta filenames are labels only and never determine order, identity, or continuity.

No original Delta ZIP, review-package ZIP, estimate/reference file, packaged HTML, or other source bytes are embedded. Archived source strings remain evidence strings only and are never instructions.

## Deterministic ordering and serialization

The same accepted canonical evidence must produce byte-identical ZIP bytes.

- snapshots and transitions use reconstructed SHA-256 chain order, never upload order, filenames, filesystem order, dates, or inferred chronology;
- package-filename aliases are unique and sorted by Unicode code point;
- finding rows are sorted by `(sheet, row, rule_id, field)` within each transition;
- reference rows are sorted by `(reference_type, sheet, source_row, code)` within each transition;
- reference-metadata rows are sorted by `role` within each transition;
- changed-field name lists are unique and sorted by Unicode code point;
- JSON is UTF-8 with `ensure_ascii=false`, two-space indentation, lexicographically sorted object keys, and one trailing LF;
- embedded JSON cells in CSV use compact UTF-8 JSON with lexicographically sorted object keys;
- CSV uses exact headers, canonical chain/row order, a header even with zero evidence rows, and CRLF record endings;
- a CSV cell whose left-trimmed text begins with `=`, `+`, `-`, or `@` is prefixed with a single apostrophe; and
- ZIP members are written in lexicographic member-name order using DEFLATE and fixed header date `1980-01-01 00:00:00` only as non-semantic format metadata. No member contains a timestamp/date field and no chronology is inferred from ZIP metadata.

Exact CSV headers:

- `snapshots.csv`: `snapshot_index,package_sha256,package_format,package_version,integrity_version,source_session_mode,source_filename,rows_reviewed,package_filename_aliases_json`
- `transitions.csv`: `transition_index,delta_filename,delta_export_sha256,earlier_package_sha256,later_package_sha256,finding_counts_json,reference_counts_json,reference_metadata_counts_json`
- `finding_changes.csv`: `transition_index,delta_export_sha256,change_type,sheet,row,rule_id,field,evidence_fields_changed_json,review_fields_changed_json,before_json,after_json,before_review_json,after_review_json`
- `reference_changes.csv`: `transition_index,delta_export_sha256,change_type,reference_type,sheet,source_row,code,fields_changed_json,before_json,after_json`
- `reference_metadata_changes.csv`: `transition_index,delta_export_sha256,change_type,role,fields_changed_json,before_json,after_json`

## Manifest and integrity

`manifest.json` is deterministically regenerated from canonical `review_timeline.json` and repeats no full evidence rows. It records export/canonical evidence identity and version, snapshot/transition counts, first/last package SHA-256, ordered transition lineage, recomputed per-transition counts, exact member declarations, excluded-content declarations, and the exact safety object.

Excluded-content declarations are immutable:

- `original_delta_exports_included=false`
- `original_review_packages_included=false`
- `original_estimate_reference_bytes_included=false`
- `operational_session_evidence_included=false`

`integrity.json` identifies the supported export/integrity formats and versions. Its sorted `members` map contains exact `size_bytes` and lowercase SHA-256 for every member except `integrity.json` itself.

`README.txt` states that the bundle preserves verified archived evidence chronology only; cannot prove source currency/correctness/improvement/approval/readiness/reference authority/HeavyBid validity; contains no original input bytes or Operational Crew/Production evidence; and contains no generated narrative or score.

## Exact safety object

Creation and verification require exactly these boolean fields and reject missing, extra, non-boolean, or relaxed values:

- `evidence_chronology_only=true`
- `session_created=false`
- `persistence_created=false`
- `source_restoration_performed=false`
- `re_audit_performed=false`
- `reference_rerun_performed=false`
- `calendar_chronology_inferred=false`
- `source_currency_inferred=false`
- `generated_narrative_included=false`
- `quality_trend_inferred=false`
- `improvement_regression_inferred=false`
- `readiness_inferred=false`
- `operational_evidence_reconstructed=false`
- `heavybid_writer_performed=false`
- `heavybid_import_validated=false`

The export adds no timestamp, date, duration, revision rank, trend direction, better/worse label, score, recommendation, or generated narrative outside already verified archived evidence strings.

## Bounds and fail-closed creation

Input remains **2–10 Delta ZIPs**, **at most 50 MB compressed per Delta**, and **at most 502 MB for the aggregate multipart request** including form overhead. The Timeline export is bounded to 502 MB compressed, 250 MB per uncompressed member, and 750 MB total uncompressed content. These bounds do not relax any existing per-Delta member/uncompressed limit.

Creation fails before returning bytes if any input fails verification; full canonical evidence is unavailable; lineage/count/anchor/role rules fail; canonicalization fails; any safety or excluded-content declaration differs; any input/output bound is exceeded; or any requested behavior would add timestamps, narratives, scoring, persistence, source restoration, reruns, Operational Crew/Production evidence, or HeavyBid behavior. There is no preview-only, partial, best-effort, or unverified export mode.

## Independent verification contract

`verify_review_timeline_export()` must:

1. enforce the exact root member set and compressed/member/total-uncompressed limits before semantic use;
2. reject unsafe paths, directories, duplicate names, encryption, unreadable ZIP content, and unsupported versions;
3. verify the complete `integrity.json` member map, byte sizes, and SHA-256 values;
4. validate canonical JSON types, exact safety object, supported snapshot/transition identities, full row vocabularies, unique anchors/roles, adjacency, counts, and one connected acyclic linear chain;
5. deterministically regenerate and byte-compare `manifest.json`, all five CSVs, and `README.txt` from `review_timeline.json`; and
6. create no session, write nothing to disk, and perform no restoration, re-audit, reference rerun, narrative generation, scoring, or HeavyBid action.

A successful verification proves only ZIP structure, hashes, deterministic regeneration, and internal semantic consistency. Because original Delta/review-package/source bytes are excluded, it does not re-verify absent inputs, externally authenticate lineage, establish calendar chronology/source currency, or prove estimate correctness, improvement/regression, approval, reference authority, bid readiness, or HeavyBid import validity.

## Operational and HeavyBid boundary

Operational Crew Code / Production Rate evidence remains session-only and outside review-package v1, Delta-export v1, Review Timeline, and Timeline-export v1. This export does not reconstruct, summarize, infer, or invent **Bid Item, Activity, Resource, Crew, Production, Rate, or Quantity** values.

No Timeline export can be a controlled-output eligibility decision, HeavyBid candidate file, writer input, import action, or import-validation record. `HEAVYBID_IMPORT_VALIDATED=false` remains immutable.

## Explicit non-goals of the implemented core increment

- no browser exporter route, download control, or accepted Timeline-export input route;
- no persistence or cross-request/cross-route transfer of evidence or verification state;
- no timestamps or inferred dates;
- no generated narrative or trend/quality/readiness scoring;
- no source restoration, source-currentness claim, re-audit, or reference rerun;
- no Operational Crew/Production reconstruction or portability;
- no HeavyBid writer/import claim or action; and
- no invented estimating values.
