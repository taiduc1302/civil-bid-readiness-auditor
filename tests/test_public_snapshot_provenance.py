from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HISTORICAL = ROOT / "provenance" / "initial_public_snapshot_2026-08-19" / "ALLOWLIST_MANIFEST.json"


class PublicSnapshotProvenanceTests(unittest.TestCase):
    def test_unqualified_root_allowlist_is_not_present(self):
        self.assertFalse((ROOT / "ALLOWLIST_MANIFEST.json").exists())

    def test_initial_snapshot_manifest_is_preserved_as_dated_history(self):
        self.assertTrue(HISTORICAL.is_file())
        manifest = json.loads(HISTORICAL.read_text(encoding="utf-8"))
        self.assertEqual(manifest["schema_version"], "1.0.0")
        self.assertEqual(manifest["generated_at"], "2026-08-19T00:00:00Z")
        files = manifest["files"]
        self.assertGreater(len(files), 0)
        paths = [item["path"] for item in files]
        self.assertEqual(len(paths), len(set(paths)))
        for item in files:
            self.assertIsInstance(item["size_bytes"], int)
            self.assertGreaterEqual(item["size_bytes"], 0)
            self.assertRegex(item["sha256"], re.compile(r"^[0-9a-f]{64}$"))

    def test_provenance_docs_explicitly_reject_current_tree_interpretation(self):
        text = (ROOT / "provenance" / "README.md").read_text(encoding="utf-8").casefold()
        self.assertIn("not a current-tree integrity manifest", text)
        self.assertIn("2026-08-19", text)
        self.assertIn("no generated current-release source-tree allowlist manifest", text)
        self.assertIn("no provenance evidence was discarded", text)


if __name__ == "__main__":
    unittest.main()
