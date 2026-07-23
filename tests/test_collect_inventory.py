import json
import os
import stat
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

    def test_executable_adapter_receives_absolute_project_and_preserves_its_output(self):
        root = self.make_root()
        adapters = root / ".assure" / "adapters"
        adapters.mkdir(parents=True)
        adapter = adapters / "read_only_adapter.py"
        adapter.write_text(
            "#!" + sys.executable + "\n"
            "import json\n"
            "import sys\n"
            "assert sys.argv == [sys.argv[0], '--project', str(__import__('pathlib').Path(sys.argv[2]).resolve())]\n"
            "print(json.dumps({'items': [{'kind': 'route', 'path': 'api/health'}], "
            "'failures': [{'reason': 'partial discovery'}]}))\n",
            encoding="utf-8",
        )
        adapter.chmod(adapter.stat().st_mode | stat.S_IXUSR)
        original_adapter = adapter.read_text(encoding="utf-8")

        result = collect_inventory(root)

        self.assertEqual(result["adapter_items"], [{"kind": "route", "path": "api/health"}])
        self.assertEqual(result["adapter_failures"], [{"reason": "partial discovery"}])
        self.assertEqual(adapter.read_text(encoding="utf-8"), original_adapter)

    def test_invalid_executable_adapter_is_reported_without_aborting_collection(self):
        root = self.make_root()
        (root / "app.py").write_text("print('ok')\n", encoding="utf-8")
        adapters = root / ".assure" / "adapters"
        adapters.mkdir(parents=True)
        adapter = adapters / "invalid_adapter"
        adapter.write_text("this is not an executable script\n", encoding="utf-8")
        adapter.chmod(adapter.stat().st_mode | stat.S_IXUSR)

        try:
            result = collect_inventory(root)
        except OSError as exc:
            self.fail(f"collection must report invalid adapters instead of raising: {exc}")

        self.assertEqual(result["changed_files"], ["app.py"])
        self.assertEqual(result["adapter_failures"][0]["adapter"], "invalid_adapter")
        self.assertTrue(result["adapter_failures"][0]["reason"])
        self.assertTrue((root / ".assure" / "discovery-index.json").exists())
        self.assertTrue((root / ".assure" / "cache" / "file-hashes.json").exists())

    def test_non_utf8_adapter_output_is_reported_without_aborting_collection(self):
        root = self.make_root()
        (root / "app.py").write_text("print('ok')\n", encoding="utf-8")
        adapters = root / ".assure" / "adapters"
        adapters.mkdir(parents=True)
        adapter = adapters / "non_utf8_adapter.py"
        adapter.write_text(
            "#!" + sys.executable + "\n"
            "import sys\n"
            "sys.stdout.buffer.write(b'\\xff')\n",
            encoding="utf-8",
        )
        adapter.chmod(adapter.stat().st_mode | stat.S_IXUSR)

        try:
            result = collect_inventory(root)
        except UnicodeDecodeError as exc:
            self.fail(f"collection must report non-UTF-8 adapter output instead of raising: {exc}")

        self.assertEqual(result["changed_files"], ["app.py"])
        self.assertEqual(result["adapter_failures"][0]["adapter"], "non_utf8_adapter.py")
        self.assertEqual(result["adapter_failures"][0]["reason"], "invalid JSON: adapter output is not UTF-8")
        self.assertTrue((root / ".assure" / "discovery-index.json").exists())
        self.assertTrue((root / ".assure" / "cache" / "file-hashes.json").exists())

    def test_direct_cli_runs_without_site_packages(self):
        root = self.make_root()
        (root / "app.py").write_text("print('ok')\n", encoding="utf-8")
        repository = Path(__file__).parent.parent

        result = subprocess.run(
            [
                sys.executable,
                "-S",
                "scripts/collect_inventory.py",
                "--project",
                str(root),
            ],
            cwd=repository,
            text=True,
            capture_output=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["candidate_count"], 1)


if __name__ == "__main__":
    unittest.main()
