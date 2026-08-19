# Civil Bid Readiness Auditor

A local-first, deterministic review tool for CSV/XLSX civil estimate exports. It creates a human-review queue for missing, contradictory, duplicate, arithmetic, markup/margin, category, rate-outlier, and formula-text prompts.

## Scope

This is a reviewable prototype, not production-ready estimating software. It does not validate quantities, rates, scope, profitability, contract compliance, or a bid decision. A qualified human reviewer must assess every finding.

## Run locally

Requires Python 3.12 or later and no third-party dependencies.

```powershell
python -m unittest discover -s tests -v
python app/server.py
```

Then open `http://127.0.0.1:8765` and load the synthetic sample. The server binds only to the local machine; no uploaded estimate data is sent to an external service.

## Data and privacy

All bundled examples are fictional and synthetic. Do not use confidential employer, client, supplier, or project data without appropriate authority.

## Public snapshot boundary

This repository intentionally excludes local automation logs, project-control state, release archives, runtime records, and personal/local path data. See `CLAIMS_LEDGER.md` and `NOTICE`.

