# Governed reference/codebook validation

This layer checks exported Activity and Resource codes against an explicitly supplied reference snapshot. It is deterministic, exact-match, and fail-closed.

## What it can report

- `MATCH` — exact code exists and the supplied UOM is compatible after conservative spelling normalization.
- `UNIT_MISMATCH` — exact code exists but supplied UOM differs; no conversion is attempted.
- `NO_MATCH` — supplied code is absent from the governed reference snapshot.
- `NOT_CHECKED` — no source code was supplied.

## Governance rules

- The reference snapshot must be explicitly supplied/approved for the review context.
- Project-specific approved reference data overrides generic fallback data.
- Duplicate normalized codes make the reference invalid and are rejected.
- Matching is exact after case/whitespace normalization; there is no fuzzy code guessing.
- The validator never invents a replacement code.
- The validator never updates estimate rows.
- The validator never treats historical cost values as current pricing authority.
- BCY, LCY, and CCY remain distinct.
- US ton and metric tonne remain distinct.
- Unit mismatches are review prompts only; no physical conversion is performed.

## Public repository boundary

The bundled CSV files under `samples/` are fictional test references only. They are not Tybo, HCSS, supplier, client, or project codebooks and must not be treated as production authorities.

A future private/company workflow may load an approved project-specific Activity/Material/Resource reference, but that governed source must remain separate from the public synthetic fixtures.

## HeavyBid boundary

A codebook match does not prove that a HeavyBid import is valid. Any future HeavyBid-readable output remains subject to project-specific baseline controls and independent test-import validation. Keep `HEAVYBID_IMPORT_VALIDATED=false` until that separate gate is passed.
