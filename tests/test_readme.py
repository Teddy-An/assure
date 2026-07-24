import unittest
from pathlib import Path


README = Path(__file__).resolve().parents[1] / "README.md"
README_EN = Path(__file__).resolve().parents[1] / "README.en.md"


class ReadmeTests(unittest.TestCase):
    def test_readmes_are_split_by_language_and_cross_linked(self):
        korean = README.read_text(encoding="utf-8")
        english = README_EN.read_text(encoding="utf-8")
        self.assertIn("[English](README.en.md)", korean)
        self.assertIn("[한국어](README.md)", english)
        self.assertIn("## 왜 Assure가 필요한가", korean)
        self.assertIn("## 무엇이 다른가", korean)
        self.assertIn("## Why use Assure?", english)
        self.assertIn("## What makes it different?", english)

    def test_readme_documents_verified_install_and_usage_contract(self):
        text = (
            README.read_text(encoding="utf-8")
            + README_EN.read_text(encoding="utf-8")
        )
        required = [
            "Early beta",
            "codex plugin marketplace add",
            "codex plugin add assure@assure-local",
            "Run Assure for this project.",
            "Update this project's Assure verification map.",
            "Run the approved full verification baseline.",
            ".assure/verification-manifest.yaml",
            ".assure/discovery-index.json",
            "Copyright (c) 2026 Teddy An",
        ]
        for value in required:
            with self.subTest(value=value):
                self.assertIn(value, text)

    def test_readme_is_read_as_utf8(self):
        self.assertIn("Assure", README.read_text(encoding="utf-8"))
        self.assertIn("Assure", README_EN.read_text(encoding="utf-8"))

    def test_readmes_define_assure_owned_functional_probes(self):
        korean = README.read_text(encoding="utf-8")
        english = README_EN.read_text(encoding="utf-8")
        self.assertIn(".assure/probes/", korean)
        self.assertIn("정상값·실패값·경계값", korean)
        self.assertIn("Assure-owned functional probe", english)
        self.assertIn("valid, invalid, and boundary inputs", english)


if __name__ == "__main__":
    unittest.main()
