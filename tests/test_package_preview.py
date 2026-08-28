from __future__ import annotations

import io
import json
import sys
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from audit_engine import audit, parse_upload
from finding_review import default_dispositions
from package_preview import inspect_review_package_members, snapshot_preview_body
from review_package import build_review_package, integrity_manifest, verify_review_package


class PackagePreviewTests(unittest.TestCase):
    def session(self, filename="synthetic_civil_estimate.csv"):
        sample = ROOT / "samples" / "synthetic_civil_estimate.csv"
        result = audit(parse_upload(sample.name, sample.read_bytes()))
        return {
            "filename": filename,
            "result": result,
            "dispositions": default_dispositions(result),
            "mappings": {},
        }

    def rebuild(self, package: bytes, mutate):
        with zipfile.ZipFile(io.BytesIO(package), "r") as book:
            members = {name: book.read(name) for name in book.namelist() if name != "integrity.json"}
        mutate(members)
        members["integrity.json"] = (
            json.dumps(integrity_manifest(members), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        ).encode("utf-8")
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as book:
            for name in sorted(members):
                book.writestr(name, members[name])
        return output.getvalue()

    def test_verified_package_contains_read_only_bounded_snapshot(self):
        package, _ = build_review_package(self.session())
        verified = verify_review_package(package)
        preview = verified["snapshot_preview"]
        self.assertFalse(preview["session_restored"])
        self.assertEqual(preview["source_filename"], "synthetic_civil_estimate.csv")
        self.assertEqual(preview["finding_total"], 14)
        self.assertEqual(preview["reference_total"], 0)
        self.assertEqual(preview["review_status_counts"]["Open"], 14)

        bounded = inspect_review_package_members(package, {"valid": True}, row_limit=2)
        self.assertEqual(len(bounded["finding_rows"]), 2)
        self.assertTrue(bounded["findings_truncated"])
        self.assertEqual(bounded["finding_total"], 14)

    def test_preview_escapes_package_text_and_never_renders_member_html(self):
        package, _ = build_review_package(self.session("<script>alert(1)</script>.csv"))
        preview = verify_review_package(package)["snapshot_preview"]
        body = snapshot_preview_body(preview)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;.csv", body)
        self.assertNotIn("<script>alert(1)</script>.csv", body)
        self.assertIn("does not render package <code>summary.html</code>", body)
        self.assertIn("never exposes a session-restore action", body)
        self.assertNotIn("<form", body)
        self.assertNotIn("<iframe", body)

    def test_rehashed_manifest_with_relaxed_safety_is_rejected_semantically(self):
        package, _ = build_review_package(self.session())

        def mutate(members):
            manifest = json.loads(members["manifest.json"].decode("utf-8"))
            manifest["safety"]["bid_certified"] = True
            members["manifest.json"] = (
                json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
            ).encode("utf-8")

        changed = self.rebuild(package, mutate)
        with self.assertRaisesRegex(ValueError, "safety state"):
            verify_review_package(changed)

    def test_rehashed_review_evidence_mismatch_is_rejected_semantically(self):
        package, _ = build_review_package(self.session())

        def mutate(members):
            text = members["review.csv"].decode("utf-8")
            members["review.csv"] = text.replace("Quantity is zero.", "Different finding evidence.", 1).encode("utf-8")

        changed = self.rebuild(package, mutate)
        with self.assertRaisesRegex(ValueError, "evidence does not match"):
            verify_review_package(changed)

    def test_rehashed_invalid_review_state_is_rejected_semantically(self):
        package, _ = build_review_package(self.session())

        def mutate(members):
            text = members["review.csv"].decode("utf-8")
            members["review.csv"] = text.replace(",Open,", ",Approve everything,", 1).encode("utf-8")

        changed = self.rebuild(package, mutate)
        with self.assertRaisesRegex(ValueError, "invalid review disposition"):
            verify_review_package(changed)

    def test_preview_requires_prior_integrity_result(self):
        package, _ = build_review_package(self.session())
        with self.assertRaisesRegex(ValueError, "successful integrity result"):
            inspect_review_package_members(package, {"valid": False})
        with self.assertRaisesRegex(ValueError, "row limit"):
            inspect_review_package_members(package, {"valid": True}, row_limit=0)


if __name__ == "__main__":
    unittest.main()
