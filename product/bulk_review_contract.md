# Bulk finding review action contract

## Purpose

Define a controlled boundary for any future bulk human-disposition workflow. The current implementation can **plan and validate** an explicit bulk action; it does not apply one.

Bulk review is a human workflow convenience. It never changes deterministic findings, severity, audit metrics, the legacy score, estimate values, governed reference results, or HeavyBid safety state.

## Current built layer: planning only

`app/bulk_review.py` creates a plan only when all of the following are true:

- the caller explicitly supplies one or more finding IDs;
- every selected ID exists in the current deterministic finding set;
- the selection contains no duplicate IDs;
- the target disposition is one of the existing supported human review states;
- `Suppressed` includes a nonblank reason;
- human ownership is explicitly acknowledged with the boolean value `True`.

The planner records:

- plan format/version;
- exact ordered target IDs and count;
- requested status/reason;
- the expected current status/reason for every target;
- SHA-256 of the full deterministic finding identity set;
- SHA-256 of the selected finding identities;
- explicit flags that the plan is not automatically applied and does not mutate deterministic/reference data or score.

There is intentionally no implicit `all findings` target and no browser bulk-apply control in this layer.

## Stale-session protection for a future apply step

A future apply implementation must fail closed unless all of these still match the approved plan immediately before mutation:

1. plan format/version;
2. full finding-set SHA-256;
3. selected finding identity SHA-256;
4. exact selected finding IDs;
5. expected current human status/reason for every selected finding;
6. supported target status and suppression-reason rule;
7. explicit human ownership acknowledgement.

If any deterministic finding identity or selected review state changed after planning, the plan is stale and must be rebuilt. A future apply operation must be atomic: either every selected disposition is updated or none are.

## Explicit non-goals

- no automatic selection of every visible or hidden finding;
- no inferred reviewer identity or approval authority;
- no automatic `Accepted` or `Suppressed` decisions;
- no bulk mutation of governed reference results;
- no estimate corrections;
- no changes to severity, finding text, score, quantity, rate, scope, or HeavyBid controls;
- no claim that completing human review means the estimate or bid is correct or ready.

## Future UI gate

Before a browser bulk-apply control is added, it should expose the exact selected count, target status, reason, and human-ownership acknowledgement and must preserve individual evidence rows. The UI must not turn a filtered view into an implicit bulk scope.
