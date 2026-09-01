# Operational Activity evidence UI contract

## Purpose

The local review UI may compare explicitly exported **Crew Code** and/or **Production Rate** values with an explicitly supplied governed Activity reference snapshot. This is row-linked review evidence only.

It is not crew design, production calculation, pricing authority, estimator approval, bid-readiness certification, or HeavyBid import validation.

## Source requirements

Operational comparison is available only in a current source-backed audit when an included sheet explicitly maps:

- `activity`; and
- `crew_code` and/or `production_rate`.

The source must contain an explicit nonblank value for at least one operational field that also exists in the supplied operational reference. Missing source fields are never populated or inferred.

HeavyBid-style header aliases may preselect these optional mappings only when exact supported headers are present. They do not affect profile detection or deterministic audit rules.

## Reference requirements

The user must separately upload a UTF-8 CSV that contains:

- Activity Code; and
- Crew Code and/or Production Rate.

Matching is Activity-Code based and case/whitespace normalized only. Duplicate normalized Activity Codes fail closed. At least one operational field must overlap the explicitly mapped source fields and contain an explicit value.

Extra fields, including historical cost/rate columns, are ignored by the operational comparator.

## Evidence metadata

The temporary session records for the operational upload:

- role: `operational_activity`;
- filename;
- user-supplied revision/label, which may be blank;
- exact byte size;
- SHA-256 of the uploaded bytes; and
- `authority_status=NOT_ESTABLISHED_BY_APP`.

The application does not infer whether the supplied reference is current, approved, project-authoritative, or commercially valid.

## Comparison statuses

Operational evidence uses separate statuses:

- `MATCH`;
- `CREW_MISMATCH`;
- `PRODUCTION_MISMATCH`;
- `CREW_AND_PRODUCTION_MISMATCH`;
- `INVALID_PRODUCTION_RATE`;
- `NO_MATCH`; and
- `NOT_CHECKED`.

Production comparison requires finite explicit numeric values on both sides. No conversion, tolerance, replacement value, or derived production calculation is performed.

## Session lifecycle

Operational evidence is fingerprinted against the included source rows plus the explicit Activity/Crew/Production mapping. If a successful re-audit changes that evidence, the prior operational comparison is cleared before it can be shown as current.

A failed audit or failed reference submission does not partially replace the existing session evidence.

## Portable-package boundary

Operational evidence is **not part of review-package v1**. It is intentionally excluded from:

- `references.csv`;
- the current review-package manifest/reference metadata;
- archived review continuation; and
- Review Delta.

Adding operational evidence to portable packages requires a separate explicit package/version compatibility contract plus semantic verification, archived-continuation, and Review Delta updates. It must not be silently overloaded into the existing Activity/Resource reference rows.

## Safety boundary

The feature never:

- invents or proposes Crew Codes;
- calculates or recommends Production Rates;
- fills missing source/reference values;
- treats historical cost/rate fields as current pricing authority;
- changes deterministic findings, quantities, rates, mappings, or human dispositions;
- establishes estimator approval or project reference authority;
- claims bid readiness; or
- changes `HEAVYBID_IMPORT_VALIDATED=false`.
