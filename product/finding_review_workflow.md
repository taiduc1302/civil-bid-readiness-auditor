# Finding review and disposition workflow

Deterministic findings are review prompts, not verdicts. This workflow records the human review state without changing or hiding the original audit result.

## Statuses

- `Open` — not yet reviewed.
- `Reviewed` — examined by a reviewer; no final disposition recorded yet.
- `Accepted` — finding is understood and accepted as intentional/currently valid.
- `Needs correction` — reviewer determined that estimate data should be corrected outside the auditor.
- `Suppressed` — finding is intentionally excluded from active review reporting for a documented reason.

## Controls

- Every finding starts as `Open`.
- `Suppressed` always requires a nonblank reason.
- Unknown statuses fail closed.
- Unknown finding IDs fail closed.
- Review state never edits source estimate values.
- Review state never changes the deterministic rule output or legacy score.
- The original finding remains visible in exports together with review status and reason.
- CSV review exports protect formula-like status/reason text from spreadsheet execution.

## Intended next UI step

The browser results page can expose a status selector and reason field per finding, then save those values into the existing temporary local session. A separate review CSV export should preserve both deterministic finding data and human dispositions.

## Boundary

A human disposition is not proof of bid correctness, commercial approval, HeavyBid import validity, or codebook compliance. `Accepted` means only that the reviewer has accepted the flagged condition in the context of this review.
