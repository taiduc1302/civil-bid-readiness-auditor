# Claim ledger

| Public claim | Evidence |
|---|---|
| The app runs without third-party Python dependencies. | `requirements.txt`; standard-library imports in `app/`. |
| The app supports a local CSV/XLSX audit workflow. | `tests/test_audit_engine.py`, `tests/test_server.py`. |
| Numeric non-finite values and -100% markup conversion are controlled. | `tests/test_external_regressions.py`. |
| The app supports optional hierarchy-aware mapping and a fail-closed HeavyBid-style resource-export profile. | `app/heavybid_adapter.py`, `tests/test_heavybid_adapter.py`, `tests/test_server_profile_detection.py`. |
| The app supports temporary local human finding dispositions and review CSV export. | `app/finding_review.py`, `tests/test_finding_review.py`, `tests/test_server_review.py`. |
| The app can validate explicitly supplied Activity/Resource codes and units against governed CSV snapshots without guessing replacements or converting physical units. | `app/reference_validation.py`, `tests/test_reference_validation.py`, `tests/test_server_references.py`. |
| Bundled estimate and reference examples are fictional/synthetic. | `samples/` fixtures and corresponding tests. |
| The app is not production-ready and does not certify a bid or HeavyBid import. | `product/PRD.md`, `qa/known_limitations.md`, `product/post_consolidation_roadmap.md`, and `README.md`. |

Unknown: production accuracy, savings, compatibility with every estimating export, customer adoption, willingness to pay, commercial validation, and production HeavyBid import safety.
