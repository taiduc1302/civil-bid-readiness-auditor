from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "product" / "review_timeline_export_contract.md"


class ReviewTimelineExportContractTests(unittest.TestCase):
    def test_contract_defines_exact_deterministic_full_evidence_bundle(self):
        text = CONTRACT.read_text(encoding="utf-8")

        required_identity_and_members = (
            "civil-estimate-review-timeline-export",
            "civil-estimate-review-timeline-export-integrity",
            "manifest.json",
            "review_timeline.json",
            "snapshots.csv",
            "transitions.csv",
            "finding_changes.csv",
            "reference_changes.csv",
            "reference_metadata_changes.csv",
            "README.txt",
            "integrity.json",
        )
        for value in required_identity_and_members:
            self.assertIn(f"`{value}`", text)

        self.assertIn("every verified finding, governed-reference, and reference-metadata change row", text)
        self.assertIn("including `UNCHANGED` rows", text)
        self.assertIn("truncated preview rows are **not sufficient export evidence**", text)
        self.assertIn("The same accepted canonical evidence must produce byte-identical ZIP bytes.", text)
        self.assertIn("2–10 Delta ZIPs", text)
        self.assertIn("at most 50 MB compressed per Delta", text)
        self.assertIn("at most 502 MB for the aggregate multipart request", text)

    def test_contract_requires_exact_safety_and_excluded_content_boundary(self):
        text = CONTRACT.read_text(encoding="utf-8")

        for safety_value in (
            "`evidence_chronology_only=true`",
            "`session_created=false`",
            "`persistence_created=false`",
            "`source_restoration_performed=false`",
            "`re_audit_performed=false`",
            "`reference_rerun_performed=false`",
            "`calendar_chronology_inferred=false`",
            "`source_currency_inferred=false`",
            "`generated_narrative_included=false`",
            "`quality_trend_inferred=false`",
            "`improvement_regression_inferred=false`",
            "`readiness_inferred=false`",
            "`operational_evidence_reconstructed=false`",
            "`heavybid_writer_performed=false`",
            "`heavybid_import_validated=false`",
        ):
            self.assertIn(safety_value, text)

        self.assertIn("`original_delta_exports_included=false`", text)
        self.assertIn("`original_review_packages_included=false`", text)
        self.assertIn("`original_estimate_reference_bytes_included=false`", text)
        self.assertIn("`operational_session_evidence_included=false`", text)
        self.assertIn("No Timeline export can be a controlled-output eligibility decision", text)
        self.assertIn("Bid Item, Activity, Resource, Crew, Production, Rate, or Quantity", text)

    def test_contract_only_increment_has_no_runtime_export_surface(self):
        self.assertFalse((ROOT / "app" / "review_timeline_export.py").exists())

        app_source = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted((ROOT / "app").glob("*.py"))
        )
        self.assertNotIn("/export-review-timeline", app_source)
        self.assertNotIn("build_review_timeline_export", app_source)
        self.assertNotIn("verify_review_timeline_export", app_source)

        synchronized_boundaries = {
            "product/PRD.md": "No exporter, verifier, route, or UI control is built.",
            "product/acceptance_criteria.md": "no exporter, verifier, route, UI control",
            "product/post_consolidation_roadmap.md": "No exporter, verifier, route, UI control",
            "product/review_timeline_contract.md": "The export is **not implemented**.",
            "CLAIMS_LEDGER.md": "this is a contract claim only",
            "qa/known_limitations.md": "no Timeline export builder, verifier, route",
        }
        for relative_path, required_boundary in synchronized_boundaries.items():
            text = (ROOT / relative_path).read_text(encoding="utf-8")
            self.assertIn(required_boundary, text, relative_path)


if __name__ == "__main__":
    unittest.main()
