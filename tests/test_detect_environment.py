import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.detect_environment import detect_environment
from scripts.assure_capabilities import assess_capabilities


class EnvironmentDetectorTests(unittest.TestCase):
    def test_capabilities_require_only_minimal_local_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "package.json").write_text(
                '{"dependencies":{"react":"19.0.0"},'
                '"devDependencies":{"vitest":"4.0.0"}}',
                encoding="utf-8",
            )
            (root / "firestore.rules").write_text(
                "rules_version = '2';\n",
                encoding="utf-8",
            )
            result = assess_capabilities(root)

        by_id = {item["id"]: item for item in result["capabilities"]}
        self.assertEqual(
            by_id["react-dom-execution"]["status"],
            "preparation-required",
        )
        self.assertNotIn("firestore-rules-execution", by_id)
        self.assertNotIn("browser-execution", by_id)
        self.assertFalse(result["host"]["administrator_required"])

    def test_detects_next_nest_jest_and_pytest(self):
        root = Path(__file__).parent / "fixtures" / "sample_project"
        result = detect_environment(root)
        self.assertIn("typescript", result["languages"])
        self.assertIn("nextjs", result["frameworks"])
        self.assertIn("nestjs", result["frameworks"])
        self.assertIn("jest", result["test_runners"])
        self.assertIn("pytest", result["test_runners"])

    def test_direct_cli_runs_without_site_packages(self):
        root = Path(__file__).parent / "fixtures" / "sample_project"
        project_root = Path(__file__).parent.parent
        result = subprocess.run(
            [
                sys.executable,
                "-S",
                "scripts/detect_environment.py",
                "--project",
                str(root),
            ],
            cwd=project_root,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"pytest"', result.stdout)

    def test_detects_commented_toml_section_headers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pyproject.toml").write_text(
                "  [project] # metadata\n"
                "dependencies = [\n"
                '  "fastapi>=0.100",\n'
                '  "django>=5.0",\n'
                "]\n"
                "\n"
                " [tool.pytest.ini_options] # test settings\n"
                'testpaths = ["tests"]\n',
                encoding="utf-8",
            )
            result = detect_environment(root)

        self.assertEqual(result["frameworks"], ["django", "fastapi"])
        self.assertEqual(result["test_runners"], ["pytest"])

    def test_ignores_similarly_named_toml_sections(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pyproject.toml").write_text(
                "[project-extra] # not the project table\n"
                'dependencies = ["fastapi", "django"]\n'
                "[tool.pytestx] # not pytest\n",
                encoding="utf-8",
            )
            result = detect_environment(root)

        self.assertEqual(result["frameworks"], [])
        self.assertEqual(result["test_runners"], [])


if __name__ == "__main__":
    unittest.main()
