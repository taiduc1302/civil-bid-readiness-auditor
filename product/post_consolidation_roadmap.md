# Post-consolidation product audit and roadmap

## Current review-product baseline

The current product is a local-first deterministic **review** system, not a bid-readiness certification system. Its built layers now include:

1. CSV/XLSX ingestion, manual mapping, hierarchy-aware context, deterministic review rules, and conservative UOM normalization;
2. fail-closed HeavyBid-style flat resource-export mapping that never invents estimate values;
3. temporary human finding dispositions, filters/sorts/groups, attention summaries, accessibility semantics, explicit-selection bulk review, and per-session concurrency controls;
4. governed Activity/Resource reference validation plus separate session-only Operational Activity Crew Code / Production Rate comparison when those values are explicitly supplied;
5. deterministic portable review-package export, strict integrity + semantic verification, bounded read-only preview, and acknowledged archived-review continuation;
6. Review Delta comparison, deterministic portable Delta export, and independent Delta-export verification;
7. neutral Review Timeline reconstruction from 2–10 independently verified Delta bundles using exact review-package SHA-256 continuity only;
8. controlled output eligibility planning and pre-write hash revalidation, without a HeavyBid candidate writer.

All layers remain review aids. None certifies estimate correctness, bid readiness, reference authority, commercial approval, or production HeavyBid import safety.

## Delivered Review Timeline increment

Review Timeline is now part of the public local runtime. It:

- accepts 2–10 `civil-estimate-review-delta-export` v1 ZIPs;
- independently verifies every bundle before using lineage/count evidence;
- orders one connected acyclic linear chain only from exact `Earlier -> Later` review-package SHA-256 continuity;
- rejects duplicate/conflicting/branching/merging/cyclic/disconnected lineage;
- preserves package filenames as descriptive aliases only;
- renders bounded escaped snapshot/transition evidence;
- creates no review session and reruns no estimate/reference logic; and
- uses a dedicated bounded multipart path compatible with the Delta verifier's 50 MB per-bundle limit rather than inheriting the legacy 26 MB request cap.

It is evidence chronology only. It does not infer calendar dates, source currency, commercial revision identity, quality, improvement/regression, approval, bid readiness, or HeavyBid import validity. Session-only Operational Crew/Production evidence remains outside review-package v1, Delta-export v1, and Review Timeline.

## Next safe roadmap increments

### P1 — read-only evidence UX hardening

Preferred next increments stay read-only and work only from already verified evidence:

1. add bounded per-transition evidence-detail disclosure to Review Timeline, using the already independently verified Delta comparison rows and preserving the current no-session/no-inference contract;
2. improve cross-navigation among Review Delta verification and Review Timeline without persisting uploads or inventing chronology;
3. add focused regression fixtures for larger valid multi-bundle timeline requests and malformed aggregate requests without weakening per-bundle verifier limits;
4. keep any future timeline export deterministic and evidence-only; do not introduce timestamps, generated narratives, or trend scoring unless a separate explicit contract is approved.

### P2 — portable operational evidence only under a new version contract

Operational Crew Code / Production Rate evidence is currently session-only. If portability is required, define a new package/version compatibility contract first, then update package verification, archived continuation, Review Delta, and Review Timeline together. Do not retrofit those fields into review-package v1 or Delta-export v1.

Historical cost/rate fields remain non-authoritative unless explicitly designated by project controls. No missing Crew, Production, Rate, Quantity, Activity, Resource, or Bid Item value may be inferred or designed by the application.

### P3 — controlled HeavyBid candidate writer remains gated

A HeavyBid candidate writer is **not built**. Do not implement one merely because review/reference gates exist.

Any future HeavyBid-readable test artifact must require:

- explicitly approved project-specific Bid Item authority;
- explicitly approved Activity/resource/schema/template authority;
- recorded immutable source/reference/template identities and fresh SHA-256 revalidation;
- resolved audit/reference exceptions or explicit estimator dispositions;
- estimator setup/quantity approval as applicable;
- commercial approval;
- create-new-only versioned output that never overwrites the approved baseline; and
- a post-write manifest and independent real HeavyBid test import.

Always preserve:

- `NOT_PRODUCTION_READY`
- `NOT_ESTIMATOR_VALIDATED`
- `HEAVYBID_IMPORT_VALIDATED=false`

Only a real independently reviewed HeavyBid test import can change the import-validation status.

## Explicitly deferred

- direct HeavyBid database/API access;
- automatic code replacement;
- automatic BCY/LCY/CCY or ton/tonne conversion;
- invented Bid Item/Activity/Resource/Crew/Production/Rate/Quantity values;
- automatic correction of quantities or rates;
- automatic quality/readiness/trend scoring from Review Delta or Review Timeline;
- inferred calendar chronology or source-currentness from archived evidence;
- persistent multi-user timeline/history storage;
- production import automation; and
- cloud collaboration/authentication until the local review contract is stable.
