import unittest
from pathlib import Path


README = Path(__file__).resolve().parents[1] / "README.md"


class ReadmeTests(unittest.TestCase):
    def test_readme_has_matching_english_and_korean_sections(self):
        text = README.read_text(encoding="utf-8")
        english, korean = text.split('<a id="한국어"></a>', maxsplit=1)

        english_headings = [
            "## Why Assure",
            "## What makes it different",
            "## How it works",
            "## Requirements",
            "## Local installation",
            "## Quick start",
            "## Project state",
            "## Verdicts and safety boundaries",
            "## Limitations",
            "## Development",
            "## License",
        ]
        korean_headings = [
            "## 왜 Assure인가",
            "## 무엇이 다른가",
            "## 작동 방식",
            "## 요구 사항",
            "## 로컬 설치",
            "## 빠른 시작",
            "## 프로젝트 상태",
            "## 판정과 안전 경계",
            "## 제한 사항",
            "## 개발",
            "## 라이선스",
        ]

        for heading in english_headings:
            self.assertIn(heading, english)
        for heading in korean_headings:
            self.assertIn(heading, korean)

    def test_readme_documents_verified_install_and_usage_contract(self):
        text = README.read_text(encoding="utf-8")
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


if __name__ == "__main__":
    unittest.main()
