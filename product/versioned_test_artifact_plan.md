# Versioned HeavyBid test-artifact planning contract

This contract sits **after** the controlled output eligibility gate and **before** any future candidate workbook writer.

It does not create a workbook. It only determines whether a candidate writer could safely create a new versioned `.xlsx` file without overwriting the project baseline.

## Required inputs

- a passing output-gate manifest;
- baseline path;
- proposed output path;
- explicit output version;
- explicitly approved schema/template authority with filename, revision, SHA-256, and authority status.

## No-overwrite controls

The plan fails closed when:

- output path is the same as the baseline path, including case/slash normalization;
- output path is not `.xlsx`;
- output filename does not contain the explicit version token;
- output version contains characters outside letters, numbers, dot, underscore, and hyphen;
- schema/template authority is missing, unapproved, or has an invalid SHA-256;
- the prior eligibility gate did not pass;
- any mandatory control flag was relaxed.

A passing plan always reports:

- `write_mode=CREATE_NEW_ONLY`
- `overwrite_allowed=false`
- `artifact_created=false`
- `heavybid_import_attempted=false`
- `NOT_PRODUCTION_READY=true`
- `NOT_ESTIMATOR_VALIDATED=true`
- `HEAVYBID_IMPORT_VALIDATED=false`

## Baseline identity

The plan carries forward the `baseline_activities_import` source identity from the gate manifest. A future writer must verify the baseline hash again immediately before writing and must stop if the source changed.

## Remaining work before any candidate writer

A future writer still requires:

1. an explicitly approved schema/template contract;
2. deterministic field mapping into that schema;
3. immutable re-check of source/reference hashes immediately before writing;
4. create-new-only filesystem behavior;
5. a post-write manifest containing the candidate artifact hash;
6. independent estimator review;
7. a real HeavyBid test import performed and reviewed separately.

Synthetic tests or successful file creation can never change `HEAVYBID_IMPORT_VALIDATED=false`.
