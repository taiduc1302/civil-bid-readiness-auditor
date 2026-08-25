# Governed Crew Code / Production Rate evidence

This layer compares explicitly exported operational fields against an explicitly supplied approved Activity reference snapshot.

It is **evidence-only**. It does not design crews, calculate production, fill blanks, repair rates, or establish pricing authority.

## Comparable fields

The operational reference may contain:

- `activity_code`
- `crew_code`
- `production_rate`

An export may contain the corresponding Activity Code, Crew Code, and Production Rate.

A field is compared only when it is explicitly present on **both** source and reference rows. If a Crew Code or Production Rate is missing on either side, that field is not inferred.

## Statuses

- `MATCH`
- `CREW_MISMATCH`
- `PRODUCTION_MISMATCH`
- `CREW_AND_PRODUCTION_MISMATCH`
- `INVALID_PRODUCTION_RATE`
- `NO_MATCH`
- `NOT_CHECKED`

Production Rate comparison is numeric and requires finite explicit decimals. Nonnumeric, NaN, or infinite values are reported as invalid rather than corrected.

## Governance rules

- Activity Code matching is exact after case/whitespace normalization.
- Duplicate Activity Codes in the supplied reference are rejected.
- Missing source Crew/Production values remain missing.
- Historical cost fields and unrelated reference columns are ignored.
- A matching Crew Code or Production Rate is review evidence only; it does not validate estimate correctness or HeavyBid import safety.

## HeavyBid boundary

This layer does not change the controlled output flags. Any future test artifact continues to require the separate output eligibility gate and must preserve:

- `NOT_PRODUCTION_READY=true`
- `NOT_ESTIMATOR_VALIDATED=true`
- `HEAVYBID_IMPORT_VALIDATED=false`

until a real independent HeavyBid test import is completed and reviewed.
