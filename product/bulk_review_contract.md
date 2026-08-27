# Bulk finding review action contract

## Purpose

Define a controlled boundary for bulk human finding dispositions. The implementation can plan an explicit bulk action, apply it to a new dispositions copy after fail-closed revalidation, and expose that control through a two-step browser workflow using only individually checked findings.

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

## Built browser/session gate

`app/bulk_review_ui.py` installs a two-step browser flow on top of the same controls without changing the core audit engine:

1. Each visible evidence row has its own **Select for bulk** checkbox.
2. There is no select-all control. Filters, grouping, or hidden rows never become implicit selection.
3. The user chooses the target human review status and reason/note and explicitly acknowledges ownership of the checked rows.
4. **Preview bulk action** builds plan v2 and stores one temporary one-time plan token. Preview does not mutate dispositions.
5. The preview page lists the exact selected IDs/rows, current states, target state, reason, count, and plan fingerprint.
6. A second explicit confirmation is required to apply the previewed plan.
7. Immediately before application, `apply_bulk_review_plan(...)` revalidates plan digest, finding identities, selected IDs, and expected current states.
8. Only after validation succeeds is the returned mapping assigned to `session["dispositions"]` in one statement.
9. A successful plan token is one-time. Replay is rejected. A newer preview replaces the older pending plan.
10. A stale plan is consumed and rejected without partially updating the selected findings.

Ordinary per-row **Save visible review states** remains available and is independent of the bulk ownership/preview controls.

## Explicit non-goals

- no automatic selection of every visible or hidden finding;
- no inferred reviewer identity or approval authority;
- no automatic `Accepted` or `Suppressed` decisions;
- no bulk mutation of governed reference results;
- no estimate corrections;
- no changes to severity, finding text, score, quantity, rate, scope, or HeavyBid controls;
- no claim that completing human review means the estimate or bid is correct or ready.

## Safety maintenance rule

Any future bulk-review UX change must preserve explicit row selection, preview-before-apply, one-time plan semantics, immediate stale-state revalidation, and atomic session assignment. A filtered view must never become bulk scope by itself.
