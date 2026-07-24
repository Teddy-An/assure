import unittest
import re
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SKILL_PATHS = (
    PLUGIN_ROOT / "skills" / "assure" / "SKILL.md",
    PLUGIN_ROOT / "skills" / "assure-map" / "SKILL.md",
    PLUGIN_ROOT / "skills" / "assure-verify" / "SKILL.md",
)


class SkillIsolationTests(unittest.TestCase):
    def test_repository_rules_prevent_external_workflow_dependencies(self):
        rules = (PLUGIN_ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("Keep Assure self-contained", rules)
        self.assertIn("Do not add dependencies on external workflow", rules)
        self.assertIn("Do not combine Assure runtime verification", rules)
        claude = (PLUGIN_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertIn("Follow `AGENTS.md`", claude)
        self.assertIn("Do not invoke or adopt external workflow", claude)

    def test_assure_skills_are_exclusive_workflows(self):
        for path in SKILL_PATHS:
            text = path.read_text(encoding="utf-8")
            normalized = " ".join(text.split())
            with self.subTest(skill=path.parent.name):
                self.assertIn("## Workflow isolation", text)
                self.assertIn(
                    "Do not invoke or apply other workflow skills", normalized
                )
                self.assertIn(
                    "stop Assure and report the instruction conflict", normalized
                )

    def test_assure_skills_reference_only_assure_routed_skills(self):
        for path in SKILL_PATHS:
            text = path.read_text(encoding="utf-8")
            references = re.findall(r"\$([a-z0-9:-]+)", text)
            with self.subTest(skill=path.parent.name):
                self.assertTrue(
                    all(value.startswith("assure:") for value in references),
                    references,
                )

    def test_assure_skills_do_not_name_external_workflow_plugins(self):
        forbidden = ("super" + "powers", "under" + "stand-anything")
        for path in SKILL_PATHS:
            text = path.read_text(encoding="utf-8").lower()
            with self.subTest(skill=path.parent.name):
                for value in forbidden:
                    self.assertNotIn(value, text)

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

    def test_main_workflow_declares_core_safety_and_mapping_invariants(self):
        assure = (
            PLUGIN_ROOT / "skills" / "assure" / "SKILL.md"
        ).read_text(encoding="utf-8")
        mapping = (
            PLUGIN_ROOT / "skills" / "assure-map" / "SKILL.md"
        ).read_text(encoding="utf-8")
        verification = (
            PLUGIN_ROOT / "skills" / "assure-verify" / "SKILL.md"
        ).read_text(encoding="utf-8")

        for phrase in (
            "Never modify the original project",
            "Never read or write production data",
            "Work without optional providers",
            "Report network assurance exactly",
            "Fail closed at every outbound boundary",
            "Minimize tokens and elapsed work",
            "trace each behavior backward",
            "forbidden side effects",
            "complete approved baseline",
        ):
            self.assertIn(phrase, assure)
        self.assertIn("Do not sequentially read every source body", mapping)
        self.assertIn("common effect-ledger shape", mapping)
        self.assertIn("production data or service access", verification)
        self.assertIn("exact network assurance", verification)


if __name__ == "__main__":
    unittest.main()
