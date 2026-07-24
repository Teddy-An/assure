from __future__ import annotations

import json
import locale
import re
import sys
from pathlib import Path
from typing import Any


MESSAGES = {
    "en": {
        "report.title": "Assure Release Verification",
        "report.verdict": "Verdict: {verdict}",
        "report.verdict_label": "Verdict",
        "report.baseline_commit": "Baseline commit: `{commit}`",
        "report.baseline_commit_label": "Baseline commit",
        "report.generated_at": "Generated at: {timestamp}",
        "report.generated_at_label": "Generated at",
        "report.summary": "Summary",
        "report.unresolved": "Blocking and unresolved results",
        "report.none": "None",
        "report.all_results": "All results",
        "report.artifact_directory": "Artifact directory",
        "report.artifact": "artifact: `{artifact}`",
        "report.manual": "manual: {instruction}",
        "report.duration": "duration: {duration}s",
        "report.exit_code": "exit code: `{exit_code}`",
        "report.field": "Field",
        "report.value": "Value",
        "report.status": "Status",
        "report.count": "Count",
        "report.risk": "Risk",
        "report.section": "Section",
        "report.id": "ID",
        "report.scenario": "Scenario",
        "report.mode": "Mode",
        "report.result_detail": "Result / detail",
        "report.provider": "Execution provider",
        "report.network": "Test network",
        "report.passed": "passed",
        "report.failed": "failed",
        "verdict.releasable": "releasable",
        "verdict.warning": "warning",
        "verdict.approval-required": "approval-required",
        "verdict.blocked": "blocked",
    },
    "ko": {
        "report.title": "Assure 릴리스 검증",
        "report.verdict": "판정: {verdict}",
        "report.verdict_label": "판정",
        "report.baseline_commit": "기준 커밋: `{commit}`",
        "report.baseline_commit_label": "기준 커밋",
        "report.generated_at": "생성 시각: {timestamp}",
        "report.generated_at_label": "생성 시각",
        "report.summary": "요약",
        "report.unresolved": "차단 및 미해결 결과",
        "report.none": "없음",
        "report.all_results": "전체 결과",
        "report.artifact_directory": "아티팩트 디렉터리",
        "report.artifact": "아티팩트: `{artifact}`",
        "report.manual": "수동: {instruction}",
        "report.duration": "소요 시간: {duration}초",
        "report.exit_code": "종료 코드: `{exit_code}`",
        "report.field": "항목",
        "report.value": "결과",
        "report.status": "상태",
        "report.count": "개수",
        "report.risk": "위험도",
        "report.section": "영역",
        "report.id": "ID",
        "report.scenario": "검증 항목",
        "report.mode": "방식",
        "report.result_detail": "결과 / 비고",
        "report.provider": "실행 provider",
        "report.network": "테스트 네트워크",
        "report.passed": "통과",
        "report.failed": "실패",
        "verdict.releasable": "릴리스 가능",
        "verdict.warning": "경고",
        "verdict.approval-required": "승인 필요",
        "verdict.blocked": "차단됨",
    },
}


def detect_language(project_root: Path) -> str:
    config_path = project_root / ".assure" / "config.yaml"
    if config_path.exists():
        try:
            config = config_path.read_text(encoding="utf-8")
        except OSError:
            config = ""
        match = re.search(r"(?m)^\s*language\s*:\s*['\"]?(en|ko)\b", config)
        if match:
            return match.group(1)
    language, _ = locale.getlocale()
    return "ko" if language and language.lower().startswith("ko") else "en"


def localize(key: str, language: str, **values: str) -> str:
    template = MESSAGES.get(language, MESSAGES["en"]).get(key, key)
    return template.format(**values)


def emit_json(payload: dict[str, Any]) -> None:
    text = json.dumps(payload, ensure_ascii=False)
    try:
        sys.stdout.write(text + "\n")
    except UnicodeEncodeError:
        sys.stdout.write(json.dumps(payload, ensure_ascii=True) + "\n")
