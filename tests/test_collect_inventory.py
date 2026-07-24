import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.collect_inventory import collect_inventory


class InventoryTests(unittest.TestCase):
    def make_root(self) -> Path:
        return Path(tempfile.mkdtemp())

    def test_collects_candidates_in_path_order_and_excludes_generated_directories(self):
        root = self.make_root()
        (root / "src").mkdir()
        (root / "src" / "zeta.ts").write_text("export const zeta = true;\n", encoding="utf-8")
        (root / "src" / "alpha.py").write_text("print('alpha')\n", encoding="utf-8")
        (root / "node_modules").mkdir()
        (root / "node_modules" / "ignored.js").write_text("ignored\n", encoding="utf-8")
        (root / "dist").mkdir()
        (root / "dist" / "ignored.py").write_text("ignored\n", encoding="utf-8")

        result = collect_inventory(root)

        self.assertEqual(
            [item["path"] for item in result["candidate_files"]],
            ["src/alpha.py", "src/zeta.ts"],
        )
        self.assertEqual(result["adapter_failures"], [])
        self.assertTrue((root / ".assure" / "discovery-index.json").exists())

    def test_second_run_marks_unchanged_files_and_removed_files(self):
        root = self.make_root()
        app = root / "app.py"
        app.write_text("print('ok')\n", encoding="utf-8")
        collect_inventory(root)
        app.unlink()

        result = collect_inventory(root)

        self.assertEqual(result["changed_files"], [])
        self.assertEqual(result["unchanged_files"], [])
        self.assertEqual(result["deleted_files"], ["app.py"])

    def test_second_run_marks_identical_files_unchanged(self):
        root = self.make_root()
        (root / "app.py").write_text("print('ok')\n", encoding="utf-8")
        collect_inventory(root)

        result = collect_inventory(root)

        self.assertEqual(result["changed_files"], [])
        self.assertEqual(result["unchanged_files"], ["app.py"])

    def test_project_adapter_is_never_executed(self):
        root = self.make_root()
        adapters = root / ".assure" / "adapters"
        adapters.mkdir(parents=True)
        marker = root / "must-not-exist"
        adapter = adapters / "external_adapter.py"
        adapter.write_text(
            "from pathlib import Path\n"
            f"Path({str(marker)!r}).touch()\n",
            encoding="utf-8",
        )

        result = collect_inventory(root)

        self.assertEqual(result["adapter_items"], [])
        self.assertEqual(result["adapter_failures"][0]["adapter"], adapter.name)
        self.assertIn("disabled", result["adapter_failures"][0]["reason"])
        self.assertFalse(marker.exists())

    def test_direct_cli_runs_without_site_packages(self):
        root = self.make_root()
        (root / "app.py").write_text("print('ok')\n", encoding="utf-8")
        repository = Path(__file__).parent.parent

        result = subprocess.run(
            [
                sys.executable,
                "-X",
                "utf8",
                "-S",
                "scripts/collect_inventory.py",
                "--project",
                str(root),
            ],
            cwd=repository,
            capture_output=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
        self.assertEqual(
            json.loads(result.stdout.decode("utf-8"))["candidate_count"],
            1,
        )


if __name__ == "__main__":
    unittest.main()
