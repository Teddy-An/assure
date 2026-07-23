import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.detect_environment import detect_environment


class EnvironmentDetectorTests(unittest.TestCase):
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
