# Claim ledger

| Public claim | Evidence |
|---|---|
| The app runs without third-party Python dependencies. | `requirements.txt`; standard-library imports in `app/`. |
| The app supports a local CSV/XLSX audit workflow. | `tests/test_audit_engine.py`, `tests/test_server.py`. |
| Numeric non-finite values and -100% markup conversion are controlled. | `tests/test_external_regressions.py`. |
| The app supports optional hierarchy-aware mapping and a fail-closed HeavyBid-style resource-export profile. | `app/heavybid_adapter.py`, `tests/test_heavybid_adapter.py`, `tests/test_server_profile_detection.py`. |
| The app supports temporary local human finding dispositions and review CSV export. | `app/finding_review.py`, `tests/test_finding_review.py`, `tests/test_server_review.py`. |
| The app supports presentation-only findings filters, deterministic sorting/grouping, and stable temporary results navigation without mutating deterministic findings or dispositions. | `app/review_filters.py`, `tests/test_review_filters.py`, `tests/test_server_filters.py`. |
| The review page includes keyboard-friendly skip links, focus targets, visible focus styling, and a findings table caption. | `app/server.py`, `tests/test_server_filters.py`. |
| The app exports a deterministic local ZIP review package without embedding original estimate/reference bytes. | `app/review_package.py`, `tests/test_review_package.py`, `tests/test_server_package.py`. |
| The app can validate explicitly supplied Activity/Resource codes and units against governed CSV snapshots without guessing replacements or converting physical units. | `app/reference_validation.py`, `tests/test_reference_validation.py`, `tests/test_server_references.py`. |
| Governed reference uploads can record role, filename, user-supplied revision/label, byte size, and SHA-256 as temporary-session evidence without establishing authority. | `app/reference_metadata.py`, `app/reference_session.py`, `tests/test_reference_metadata.py`, `tests/test_server_reference_metadata.py`. |
| A local fictional onboarding walkthrough can start the existing synthetic sample flow and teaches review views, dispositions, reference evidence, and package export while repeating safety boundaries. | `app/onboarding.py`, `product/onboarding_walkthrough.md`, `tests/test_onboarding.py`. |
| Bundled estimate and reference examples are fictional/synthetic. | `samples/` fixtures and corresponding tests. |
| The app is not production-ready and does not certify a bid, reference authority, or HeavyBid import. | `product/PRD.md`, `qa/known_limitations.md`, `product/review_ux_milestone.md`, `product/post_consolidation_roadmap.md`, and `README.md`. |

Unknown: production accuracy, savings, compatibility with every estimating export, customer adoption, willingness to pay, commercial validation, and production HeavyBid import safety.
