# Review product UX milestone

This milestone improves the local review experience without changing deterministic audit rules, governed-reference semantics, or HeavyBid output gates.

## Track A — findings filters and navigation

- add a stable results URL for an existing temporary session;
- filter findings by severity, human review status, rule, sheet, and free text;
- show visible / total finding counts;
- preserve review controls on filtered views;
- provide quick links for common review slices (priority, open, needs correction, suppressed);
- keep filtering presentation-only: deterministic findings and review state are unchanged.

## Track B — versioned local review package

- export a ZIP review package from the current temporary session;
- include findings CSV, human review CSV, reference checks CSV when available, management summary HTML, and a package manifest JSON;
- include mappings, reviewed sheets, review/reference counts, source filename, and safety/non-certification flags in the manifest;
- do not include or silently persist the original estimate/reference file bytes;
- package export is a review snapshot, not a HeavyBid artifact and not bid approval.

## Track C — governed reference metadata

- capture reference role, filename, user-supplied revision/label, size, and SHA-256 at upload time;
- display metadata alongside reference results;
- include metadata in reference export/review package;
- never infer authority from filename or content; the user-supplied reference remains an explicit review input.

## Safety boundary

- no audit-rule changes;
- no automatic corrections;
- no production persistence/database;
- no HeavyBid import behavior;
- no change to `HEAVYBID_IMPORT_VALIDATED=false` controls.
