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
        "report.feature_tree": "Feature verification structure",
        "report.all_results": "All results",
        "report.artifact_directory": "Artifact directory",
        "report.artifact": "artifact: `{artifact}`",
        "report.manual": "manual: {instruction}",
        "report.duration": "duration: {duration}s",
        "report.exit_code": "exit code: `{exit_code}`",
        "report.field": "Field",
        "report.value": "Value",
        "report.status": "Status",
        "report.number": "No.",
        "report.count": "Count",
        "report.risk": "Risk",
        "report.section": "Section",
        "report.id": "ID",
        "report.scenario": "Scenario",
        "report.mode": "Mode",
        "report.result": "Result",
        "report.detail": "Detail",
        "report.provider": "Execution provider",
        "report.network": "Test network",
        "report.passed": "passed",
        "report.failed": "failed",
        "report.result_passed": "Passed",
        "report.result_failed": "Failed",
        "report.result_unverified": "Unverified",
        "report.result_confirm": "Confirm",
        "report.result_excluded": "Excluded",
        "report.mode_automated": "Automated",
        "report.mode_manual": "Manual",
        "report.mode_uncovered": "Uncovered",
        "report.mode_excluded": "Excluded",
        "report.no_coverage": "No verification coverage",
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
        "report.feature_tree": "전체 기능 검증 구조",
        "report.all_results": "전체 결과",
        "report.artifact_directory": "아티팩트 디렉터리",
        "report.artifact": "아티팩트: `{artifact}`",
        "report.manual": "수동: {instruction}",
        "report.duration": "소요 시간: {duration}초",
        "report.exit_code": "종료 코드: `{exit_code}`",
        "report.field": "항목",
        "report.value": "결과",
        "report.status": "상태",
        "report.number": "번호",
        "report.count": "개수",
        "report.risk": "위험도",
        "report.section": "영역",
        "report.id": "ID",
        "report.scenario": "검증 항목",
        "report.mode": "방식",
        "report.result": "결과",
        "report.detail": "상세",
        "report.provider": "실행 provider",
        "report.network": "테스트 네트워크",
        "report.passed": "통과",
        "report.failed": "실패",
        "report.result_passed": "통과",
        "report.result_failed": "실패",
        "report.result_unverified": "미검증",
        "report.result_confirm": "확인",
        "report.result_excluded": "제외",
        "report.mode_automated": "자동",
        "report.mode_manual": "수동",
        "report.mode_uncovered": "미커버",
        "report.mode_excluded": "제외",
        "report.no_coverage": "검증 커버리지 없음",
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
