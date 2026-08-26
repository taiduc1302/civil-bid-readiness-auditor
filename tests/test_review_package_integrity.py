from __future__ import annotations

import io
import json
import sys
import unittest
import warnings
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from audit_engine import audit, parse_upload
from finding_review import default_dispositions
from review_package import build_review_package, integrity_manifest, verify_review_package


class ReviewPackageIntegrityTests(unittest.TestCase):
    def package(self) -> bytes:
        sample = ROOT / "samples" / "synthetic_civil_estimate.csv"
        result = audit(parse_upload(sample.name, sample.read_bytes()))
        data, _ = build_review_package({
            "filename": sample.name,
            "result": result,
            "dispositions": default_dispositions(result),
            "mappings": {},
        })
        return data

    def members(self, data: bytes) -> dict[str, bytes]:
        with zipfile.ZipFile(io.BytesIO(data)) as book:
            return {name: book.read(name) for name in book.namelist()}

    def make_zip(self, members: dict[str, bytes], duplicate: tuple[str, bytes] | None = None) -> bytes:
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as book:
            for name, payload in members.items():
                book.writestr(name, payload)
            if duplicate:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)
                    book.writestr(duplicate[0], duplicate[1])
        return output.getvalue()

    def test_changed_member_fails_sha_verification(self):
        members = self.members(self.package())
        members["findings.csv"] += b"tampered\n"
        with self.assertRaisesRegex(ValueError, "SHA-256 does not match"):
            verify_review_package(self.make_zip(members))

    def test_missing_integrity_member_fails_closed(self):
        members = self.members(self.package())
        members.pop("integrity.json")
        with self.assertRaisesRegex(ValueError, "missing required members"):
            verify_review_package(self.make_zip(members))

    def test_unexpected_and_unsafe_members_fail_closed(self):
        members = self.members(self.package())
        members["extra.txt"] = b"not allowed"
        with self.assertRaisesRegex(ValueError, "unexpected members"):
            verify_review_package(self.make_zip(members))

        members = self.members(self.package())
        members["../outside.txt"] = b"unsafe"
        with self.assertRaisesRegex(ValueError, "unsafe member path"):
            verify_review_package(self.make_zip(members))

    def test_duplicate_member_names_fail_closed(self):
        members = self.members(self.package())
        with self.assertRaisesRegex(ValueError, "duplicate member names"):
            verify_review_package(
                self.make_zip(members, duplicate=("manifest.json", members["manifest.json"]))
            )

    def test_rehashed_unsupported_manifest_identity_still_fails(self):
        members = self.members(self.package())
        members.pop("integrity.json")
        manifest = json.loads(members["manifest.json"])
        manifest["package_format"] = "not-this-product"
        members["manifest.json"] = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
        members["integrity.json"] = (
            json.dumps(integrity_manifest(members), indent=2, sort_keys=True) + "\n"
        ).encode()
        with self.assertRaisesRegex(ValueError, "manifest identity is unsupported"):
            verify_review_package(self.make_zip(members))

    def test_invalid_integrity_hash_contract_fails_closed(self):
        members = self.members(self.package())
        integrity = json.loads(members["integrity.json"])
        integrity["members"]["findings.csv"]["sha256"] = "not-a-sha"
        members["integrity.json"] = (json.dumps(integrity, indent=2, sort_keys=True) + "\n").encode()
        with self.assertRaisesRegex(ValueError, "integrity SHA-256 is invalid"):
            verify_review_package(self.make_zip(members))

    def test_blank_and_non_zip_payloads_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "blank"):
            verify_review_package(b"")
        with self.assertRaisesRegex(ValueError, "readable ZIP"):
            verify_review_package(b"not-a-zip")


if __name__ == "__main__":
    unittest.main()
