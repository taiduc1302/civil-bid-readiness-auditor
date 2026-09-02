# Contributing

Thanks for helping improve Civil Estimate Review Auditor.

## Workflow

For substantive bugs, features, architecture changes, or review-workflow changes:

1. Open an Issue first. Describe the problem, evidence, scope, and acceptance criteria.
2. Create a task-specific branch from the current default branch.
3. Keep the change limited to the Issue scope.
4. Open a Pull Request and link the Issue with `Closes #<number>` when the PR fully resolves it.
5. Record validation performed, known limitations, and the specific areas where reviewer attention is needed.
6. Address review findings before merge. Do not treat automated review as a substitute for human ownership of the change.

Small typo-only or formatting-only fixes may skip the Issue when there is no meaningful design or review decision.

## Review expectations

A useful review checks more than whether the code runs. Review the change against its stated acceptance criteria, regression risk, evidence boundaries, failure behavior, and documentation claims. Prefer concrete findings tied to files, behavior, or missing tests.

## Product safety boundaries

Do not weaken established review and evidence controls. In particular, do not imply that deterministic findings, reference matches, package integrity, or archived evidence prove estimate correctness, bid readiness, estimator approval, or HeavyBid import validity.

Do not introduce real confidential project data, credentials, secrets, or proprietary reference material into public fixtures or documentation.

## Validation

Run the repository's relevant automated tests for any behavior change. Documentation-only changes should still be checked for broken links, inaccurate claims, and contradictions with current product behavior.
