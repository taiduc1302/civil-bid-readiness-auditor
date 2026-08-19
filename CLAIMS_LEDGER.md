# Claim ledger

| Public claim | Evidence |
|---|---|
| The app runs without third-party Python dependencies. | `requirements.txt`; standard-library imports in `app/`. |
| The app supports a local CSV/XLSX audit workflow. | `tests/test_audit_engine.py`, `tests/test_server.py`. |
| Numeric non-finite values and -100% markup conversion are controlled. | `tests/test_external_regressions.py`. |
| The sample data is synthetic. | `samples/synthetic_civil_estimate.csv` and `samples/expected_synthetic_result.json`. |
| The app is not production-ready and does not certify a bid. | `product/PRD.md`, `qa/known_limitations.md`, and this README. |

Unknown: production accuracy, savings, compatibility with every estimating export, customer adoption, willingness to pay, and commercial validation.

