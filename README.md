# Civil Bid Readiness Auditor

A local-first, deterministic review tool for CSV/XLSX civil estimate exports. It builds a human-review queue for data-quality exceptions and supports optional hierarchy-aware mapping, human finding dispositions, and validation against explicitly supplied Activity/Resource reference CSVs.

## Scope

This is a reviewable prototype, not production-ready estimating software and not a bid-readiness certification system. It does not establish correct quantities, rates, scope, productivity, profitability, contract compliance, codebook authority, or a bid decision. A qualified human reviewer must assess every finding and every reference exception.

## Current workflow

1. Upload a CSV/XLSX estimate export or run the synthetic sample.
2. Review sheet selection and column mapping. Recognized HeavyBid-style resource exports may preselect supported fields using exact aliases only; mappings remain editable.
3. Run the deterministic audit and review row-linked findings.
4. Record temporary local finding dispositions (`Open`, `Reviewed`, `Accepted`, `Needs correction`, or `Suppressed`). Suppression requires a reason and never changes the source estimate or deterministic finding.
5. Optionally upload an explicitly approved Activity and/or Resource reference CSV to check exported codes and units. Results are `MATCH`, `UNIT_MISMATCH`, `NO_MATCH`, or `NOT_CHECKED`; no replacement codes or conversions are inferred.
6. Export findings, review-state CSV, reference-check CSV, or the printable management summary.

## Run locally

Requires Python 3.12 or later and no third-party dependencies.

```powershell
python -m unittest discover -s tests -v
python app/server.py
```

Then open `http://127.0.0.1:8765`. The server binds only to the local machine; uploaded estimate/reference data is held only in temporary process memory by this application.

## HeavyBid boundary

The repository includes a controlled **HeavyBid-style** flat export adapter, not a direct HeavyBid database/API integration. It never invents Bid Item, Activity, Resource, Crew, Production, Rate, or Quantity values. Governed reference matching is separate from import validation. Any future HeavyBid-readable output must remain `HEAVYBID_IMPORT_VALIDATED=false` until a real independent test import is completed and reviewed.

## Data and privacy

All bundled examples and reference fixtures are fictional and synthetic. Do not use confidential employer, client, supplier, or project data without appropriate authority.

## Public snapshot boundary

This repository intentionally excludes local automation logs, project-control state, release archives, runtime records, company codebooks, and personal/local path data. See `CLAIMS_LEDGER.md`, `NOTICE`, and `product/post_consolidation_roadmap.md`.
