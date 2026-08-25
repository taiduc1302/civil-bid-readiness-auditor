# Controlled estimating output eligibility gate

This gate defines the minimum evidence and approvals required before a **separate future step** may prepare a versioned HeavyBid-readable **test** artifact.

It does **not** create a HeavyBid file, modify HeavyBid, validate a production import, or authorize production use.

## Required source authorities

The source register must contain exactly one approved entry for each role:

- `project_biditem_authority`
- `baseline_activities_import`

Every registered source must record:

- role
- filename
- revision/label
- SHA-256
- authority status (`APPROVED` or `REFERENCE_ONLY`)

Required authority roles must be `APPROVED`. Duplicate required roles are ambiguous and block eligibility.

## Required approvals

The following explicit approvals must all be true:

- `estimator_setup_approved`
- `estimator_quantity_approved`
- `commercial_approved`

The application must not infer any approval from a clean audit, codebook match, synthetic test, or absence of findings.

## Exception gate

Every supplied exception must be one of:

- `RESOLVED`
- `APPROVED_EXCEPTION`

`APPROVED_EXCEPTION` requires a nonblank human reason. Any open, unknown, or otherwise unresolved status blocks the gate.

## Control flags

Even when every eligibility condition passes, the manifest must preserve:

- `NOT_PRODUCTION_READY=true`
- `NOT_ESTIMATOR_VALIDATED=true`
- `HEAVYBID_IMPORT_VALIDATED=false`

Passing this gate means only:

> the minimum governed evidence exists to consider preparing a separate controlled test artifact.

It does not mean the estimate is correct, the import file is valid, or HeavyBid will accept the file.

## Manifest behavior

`build_output_manifest(...)` creates review metadata only. It records the source register, approvals, exception state, explicit output version, and immutable control flags.

It deliberately reports:

- `artifact_created=false`
- `heavybid_import_attempted=false`

A later implementation may create a new versioned test artifact only under a separately reviewed output-preparation contract. It must never overwrite the project baseline.

## Explicit non-goals

- direct HeavyBid database/API access
- automatic production import
- automatic quantity/rate correction
- automatic code replacement
- invented Bid Item, Activity, Resource, Crew, Production, Rate, or Quantity values
- BCY/LCY/CCY conversion without an explicit approved policy
- US ton / metric tonne conversion without an explicit approved policy
