# Civil Estimate Review Auditor

A local-first, deterministic review tool for CSV/XLSX civil estimate exports. It builds a human-review queue for data-quality exceptions and supports hierarchy-aware mapping, human finding dispositions, governed estimating references, review views, and a portable local review-package export.

> Repository note: the GitHub repository retains the legacy slug `civil-bid-readiness-auditor` to avoid breaking links. The public product title is **Civil Estimate Review Auditor** because the tool performs review, not bid-readiness certification.

## Scope

This is a reviewable prototype, not production-ready estimating software and not a bid-readiness certification system. It does not establish correct quantities, rates, scope, productivity, profitability, contract compliance, codebook authority, or a bid decision. A qualified human reviewer must assess every finding and every reference exception.

## Current workflow

1. Upload a CSV/XLSX estimate export or run the synthetic sample. New users can open the local **Fictional onboarding walkthrough** from the home page; the matching written walkthrough is in `product/onboarding_walkthrough.md`.
2. Review sheet selection and column mapping. Recognized HeavyBid-style resource exports may preselect supported fields using exact aliases only; mappings remain editable.
3. Run the deterministic audit and review row-linked findings.
4. Navigate the temporary results session with filters for severity, review status, rule, sheet, or free text. Sort by priority, source, rule, sheet, or review status; optionally group by sheet, rule, or review status. Quick views include Priority, Open, Needs correction, and Suppressed. These controls change only the presentation view.
5. Use the keyboard-friendly skip links and explicit focus targets to move between filters, findings, and references.
6. Record temporary local finding dispositions (`Open`, `Reviewed`, `Accepted`, `Needs correction`, or `Suppressed`). Suppression requires a reason and never changes the source estimate or deterministic finding.
7. Optionally validate explicitly supplied Activity/Resource codes and units against governed reference data. A user-supplied revision/label, filename, byte size, and SHA-256 are recorded as evidence; the app does not infer reference authority.
8. Optional Crew Code / Production Rate comparison is evidence-only and runs only when those values are explicitly present on both sides.
9. Export individual CSV/HTML reports or download one deterministic ZIP review package containing the manifest, findings, review states, summary, and reference checks when present. Original estimate/reference bytes are intentionally excluded.

## Run locally

Requires Python 3.12 or later and no third-party dependencies.

```powershell
python -m unittest discover -s tests -v
python app/server.py
```

Then open `http://127.0.0.1:8765`. The server binds only to the local machine; uploaded estimate/reference data is held only in temporary process memory by this application.

## HeavyBid boundary

The repository includes a controlled **HeavyBid-style** flat export adapter, not a direct HeavyBid database/API integration. It never invents Bid Item, Activity, Resource, Crew, Production, Rate, or Quantity values. Governed reference matching is separate from import validation.

The codebase includes controlled gates for output eligibility, versioned create-new-only planning, and immediate pre-write source/schema hash revalidation. It still does **not** contain a HeavyBid candidate workbook writer. Any future HeavyBid-readable output must remain `HEAVYBID_IMPORT_VALIDATED=false` until a real independent test import is completed and reviewed.

## Data and privacy

All bundled examples and reference fixtures are fictional and synthetic. Do not use confidential employer, client, supplier, or project data without appropriate authority.

## Public snapshot boundary

This repository intentionally excludes local automation logs, project-control state, release archives, runtime records, company codebooks, and personal/local path data. See `CLAIMS_LEDGER.md`, `NOTICE`, and `product/post_consolidation_roadmap.md`.
