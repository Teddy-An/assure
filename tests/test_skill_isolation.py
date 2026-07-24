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

    def test_mapping_prefers_functional_probes_over_manual_helper_gaps(self):
        text = (
            PLUGIN_ROOT / "skills" / "assure-map" / "SKILL.md"
        ).read_text(encoding="utf-8")
        normalized = " ".join(text.split())
        for value in (
            ".assure/probes/",
            "success, failure, and boundary inputs",
            "assert both required effects and forbidden effects",
            "missing Docker daemon",
            "Static source inspection alone",
        ):
            with self.subTest(value=value):
                self.assertIn(value, normalized)

    def test_main_workflow_requires_validated_probe_baselines(self):
        assure = (
            PLUGIN_ROOT / "skills" / "assure" / "SKILL.md"
        ).read_text(encoding="utf-8")
        mapping = (
            PLUGIN_ROOT / "skills" / "assure-map" / "SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertIn("functional-probes-v1", assure)
        self.assertIn("policy validator", assure)
        self.assertIn("functional-probes-v1", mapping)
        self.assertIn("assure_probe_policy.py", mapping)


if __name__ == "__main__":
    unittest.main()
