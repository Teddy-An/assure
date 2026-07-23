import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.assure_output import detect_language, emit_json, localize


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


if __name__ == "__main__":
    unittest.main()
