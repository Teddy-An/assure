import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SKILL_PATHS = (
    PLUGIN_ROOT / "skills" / "assure" / "SKILL.md",
    PLUGIN_ROOT / "skills" / "assure-map" / "SKILL.md",
    PLUGIN_ROOT / "skills" / "assure-verify" / "SKILL.md",
)


class SkillIsolationTests(unittest.TestCase):
    def test_assure_skills_are_exclusive_workflows(self):
        for path in SKILL_PATHS:
            text = path.read_text(encoding="utf-8")
            normalized = " ".join(text.split())
            with self.subTest(skill=path.parent.name):
                self.assertIn("## Workflow isolation", text)
                self.assertIn(
                    "Do not invoke or apply other workflow skills", normalized
                )

    def test_assure_skills_do_not_reference_superpowers(self):
        for path in SKILL_PATHS:
            with self.subTest(skill=path.parent.name):
                self.assertNotIn("superpowers:", path.read_text(encoding="utf-8"))

    def test_assure_skills_require_supported_python_runtime(self):
        required = (
            "1. `python3 --version`",
            "2. `python --version`",
            "3. `py -3 --version`",
            "Python 3.9 or newer",
            "Python 2",
            "explicit user approval",
            "rerun runtime discovery",
            "<python-command>",
        )
        forbidden = (
            "PYTHONPATH=<plugin-root>/scripts python3",
            "Run `python3 <assure-root>/scripts",
            "python3 <assure-root>/scripts",
        )

        for path in SKILL_PATHS:
            text = path.read_text(encoding="utf-8")
            normalized = " ".join(text.split())
            with self.subTest(skill=path.parent.name):
                for value in required:
                    self.assertIn(value, normalized)
                for value in forbidden:
                    self.assertNotIn(value, text)


if __name__ == "__main__":
    unittest.main()
