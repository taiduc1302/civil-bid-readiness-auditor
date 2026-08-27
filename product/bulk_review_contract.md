# Bulk finding review action contract

## Purpose

Define a controlled boundary for bulk human finding dispositions. The current implementation can **plan** an explicit bulk action and **apply it to a new dispositions copy** after revalidating that the plan is still current. It does not mutate the browser session or expose a bulk-action UI.

Bulk review is a human workflow convenience. It never changes deterministic findings, severity, audit metrics, the legacy score, estimate values, governed reference results, or HeavyBid safety state.

## Built planning contract

`app/bulk_review.py` creates an apply-ready plan only when all of the following are true:

- the caller explicitly supplies one or more finding IDs;
- every selected ID exists in the current deterministic finding set;
- the selection contains no duplicate IDs;
- the target disposition is one of the existing supported human review states;
- `Suppressed` includes a nonblank reason;
- human ownership is explicitly acknowledged with the boolean value `True`.

Plan version 2 records:

- exact ordered target IDs and count;
- requested status/reason;
- expected current status/reason for every target;
- SHA-256 of the full deterministic finding identity set;
- SHA-256 of the selected finding identities;
- a SHA-256 content digest for the plan itself;
- explicit safety flags stating that deterministic/reference data and score are not changed and automatic application is disabled.

The plan SHA-256 is a local integrity check, not authentication or a cryptographic proof of reviewer authority.

There is intentionally no implicit `all findings` target.

## Built pure apply-to-copy validator

`apply_bulk_review_plan(...)` returns a new dispositions mapping only after all controls still match immediately before application:

1. supported plan format/version;
2. valid plan content digest;
3. explicit human ownership acknowledgement;
4. non-relaxed safety flags;
5. exact selected finding IDs and target count;
6. supported target status and suppression-reason rule;
7. full finding-set SHA-256;
8. selected finding identity SHA-256;
9. exact expected current status/reason for every selected finding.

If any deterministic finding identity or selected review state changed after planning, the plan is stale and application fails. The input `result` and `dispositions` objects remain unchanged on both success and failure; successful output is a separate mapping.

## Browser/session gate remains unbuilt

No browser control currently calls the apply validator and no session mutation occurs automatically. A future browser layer may assign the returned mapping to the session only after an explicit user action and only after the validator succeeds. That assignment must be one atomic operation.

## Explicit non-goals

- no automatic selection of every visible or hidden finding;
- no inferred reviewer identity or approval authority;
- no automatic `Accepted` or `Suppressed` decisions;
- no bulk mutation of governed reference results;
- no estimate corrections;
- no changes to severity, finding text, score, quantity, rate, scope, or HeavyBid controls;
- no claim that completing human review means the estimate or bid is correct or ready.

## Future UI gate

Before a browser bulk-apply control is added, it must expose the exact selected count, target status, reason, and human-ownership acknowledgement and preserve individual evidence rows. A filtered view must never become an implicit bulk scope. The UI must build a fresh plan from explicit selections and use the returned apply-to-copy result only after immediate validation.
