import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.assure_output import detect_language, emit_json, localize
from scripts.run_verification import render_report


class Cp949FailingStream(io.StringIO):
    def write(self, text: str) -> int:
        if any(ord(character) > 127 for character in text):
            raise UnicodeEncodeError("cp949", text, 0, 1, "unsupported")
        return super().write(text)


class OutputTests(unittest.TestCase):
    def write_config(self, root: Path, text: str) -> None:
        assure = root / ".assure"
        assure.mkdir()
        (assure / "config.yaml").write_text(text, encoding="utf-8")

    def test_emit_json_falls_back_to_ascii_when_stdout_cannot_encode_korean(self):
        stream = Cp949FailingStream()
        with patch("sys.stdout", stream):
            emit_json({"message": "검증 완료"})
        self.assertEqual(json.loads(stream.getvalue()), {"message": "검증 완료"})

    def test_project_language_overrides_korean_locale(self):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(root))
        self.write_config(root, "language: en\n")
        with patch("scripts.assure_output.locale.getlocale", return_value=("ko_KR", "UTF-8")):
            self.assertEqual(detect_language(root), "en")

    def test_korean_locale_selects_korean_without_project_config(self):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(root))
        with patch("scripts.assure_output.locale.getlocale", return_value=("ko_KR", "UTF-8")):
            self.assertEqual(detect_language(root), "ko")

    def test_localize_interpolates_english_values(self):
        self.assertEqual(localize("report.verdict", "en", verdict="blocked"), "Verdict: blocked")

    def test_localize_returns_korean_catalog_message(self):
        self.assertEqual(localize("verdict.blocked", "ko"), "차단됨")

    def test_report_renders_summary_and_results_as_markdown_tables(self):
        report = render_report({
            "language": "ko",
            "verdict": "blocked",
            "baseline_commit": "abc123",
            "generated_at": "2026-07-24T00:00:00+00:00",
            "counts": {"X": 1},
            "sandbox": {
                "provider": "local-isolated",
                "network": "disabled",
            },
            "results": [{
                "id": "payments.refund",
                "name": "환불 | 중복 방지",
                "section": "결제",
                "risk": "critical",
                "mode": "automated",
                "status": "X",
                "exit_code": 1,
                "duration_seconds": 0.5,
                "artifact": "/tmp/result.log",
            }],
            "artifact_directory": "/tmp/artifacts",
        })
        self.assertIn("| 항목 | 결과 |", report)
        self.assertIn("| 결과 | 개수 |", report)
        self.assertIn("## 전체 기능 검증 구조", report)
        self.assertIn(
            "결제 (1)\n└─ 실패  환불 | 중복 방지",
            report,
        )
        self.assertLess(
            report.index("## 전체 기능 검증 구조"),
            report.index("## 전체 결과"),
        )
        self.assertIn(
            "| 번호 | 위험도 | 영역 | ID | 검증 항목 | 방식 | 결과 | 상세 |",
            report,
        )
        self.assertEqual(
            report.count(
                "| 번호 | 위험도 | 영역 | ID | 검증 항목 | 방식 | 결과 | 상세 |"
            ),
            1,
        )
        self.assertNotIn("차단 및 미해결 결과", report)
        self.assertIn(
            "| 1 | critical | 결제 | `payments.refund` | "
            "환불 \\| 중복 방지 | 자동 | 실패 |",
            report,
        )
        self.assertIn("환불 \\| 중복 방지", report)


if __name__ == "__main__":
    unittest.main()
