import tempfile
import unittest
from pathlib import Path

import yaml

from scripts.assure_identity import generation_marker
from scripts.assure_probe_compatibility import (
    delete_stale_probes,
    probe_compatibility,
    stale_probe_files,
)


class ProbeCompatibilityTests(unittest.TestCase):
    def test_current_generation_marker_is_compatible(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "current.test.ts"
            path.write_text(
                generation_marker("//") + "\ntest('current', () => {})\n",
                encoding="utf-8",
            )

            result = probe_compatibility(path)

        self.assertTrue(result["compatible"])

    def test_old_or_unmarked_probe_is_stale(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            probes = root / ".assure" / "probes"
            probes.mkdir(parents=True)
            (probes / "old.test.ts").write_text(
                "// ASSURE_GENERATED: version=0.1.0 "
                + "distribution_sha256="
                + "0" * 64
                + " probe_schema=1 generator_contract=old\n"
                + "test('old', () => {})\n",
                encoding="utf-8",
            )
            (probes / "unmarked.test.ts").write_text(
                "test('unknown', () => {})\n",
                encoding="utf-8",
            )

            stale = stale_probe_files(root)

        self.assertEqual(len(stale), 2)
        self.assertTrue(all(item["reason"] for item in stale))

    def test_delete_removes_only_stale_assure_probe_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            probes = root / ".assure" / "probes"
            probes.mkdir(parents=True)
            current = probes / "current.test.ts"
            current.write_text(
                generation_marker("//") + "\ntest('current', () => {})\n",
                encoding="utf-8",
            )
            stale = probes / "old.test.ts"
            stale.write_text("test('old', () => {})\n", encoding="utf-8")
            product = root / "tests" / "product.test.ts"
            product.parent.mkdir()
            product.write_text("test('product', () => {})\n", encoding="utf-8")

            deleted = delete_stale_probes(root)

            self.assertEqual([item["path"] for item in deleted], [
                ".assure/probes/old.test.ts"
            ])
            self.assertTrue(current.exists())
            self.assertTrue(product.exists())

    def test_legacy_policy_forces_full_probe_regeneration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            assure = root / ".assure"
            probes = assure / "probes"
            probes.mkdir(parents=True)
            current = probes / "current.test.ts"
            current.write_text(
                generation_marker("//") + "\ntest('current', () => {})\n",
                encoding="utf-8",
            )
            (assure / "verification-manifest.yaml").write_text(
                yaml.safe_dump({
                    "schema_version": 1,
                    "baseline": {
                        "status": "approved",
                        "verification_policy": "functional-probes-v1",
                    },
                    "sections": [],
                }),
                encoding="utf-8",
            )

            stale = stale_probe_files(root)

        self.assertEqual(len(stale), 1)
        self.assertIn("legacy verification policy", stale[0]["reason"])


if __name__ == "__main__":
    unittest.main()
