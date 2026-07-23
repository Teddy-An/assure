from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

if __package__:
    from .assure_common import AssureError, load_manifest, sha256_file, write_json
    from .assure_mocks import inject_mocks
    from .assure_output import detect_language, emit_json, localize
    from .assure_runners import build_runner_command
    from .assure_sandbox import Sandbox, SandboxUnavailable, prepare_sandbox
    from .assure_state import classify_project
else:
    from assure_common import AssureError, load_manifest, sha256_file, write_json
    from assure_mocks import inject_mocks
    from assure_output import detect_language, emit_json, localize
    from assure_runners import build_runner_command
    from assure_sandbox import Sandbox, SandboxUnavailable, prepare_sandbox
    from assure_state import classify_project


RISKS = {"critical", "high", "normal"}
MODES = {"automated", "manual", "uncovered", "excluded"}
AUTOMATED_TIMEOUT_SECONDS = 15
_WINDOWS_COMMAND_SUPERVISOR = (
    "import subprocess, sys\n"
    "if sys.stdin.buffer.read(1) != b'1':\n"
    "    raise SystemExit(125)\n"
    "raise SystemExit(subprocess.call(sys.argv[1:]))\n"
)


if os.name == "nt":
    from ctypes import wintypes

    class _IoCounters(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_uint64),
            ("WriteOperationCount", ctypes.c_uint64),
            ("OtherOperationCount", ctypes.c_uint64),
            ("ReadTransferCount", ctypes.c_uint64),
            ("WriteTransferCount", ctypes.c_uint64),
            ("OtherTransferCount", ctypes.c_uint64),
        ]


    class _BasicLimitInformation(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]


    class _ExtendedLimitInformation(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", _BasicLimitInformation),
            ("IoInfo", _IoCounters),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]


    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    _kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    _kernel32.SetInformationJobObject.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
    ]
    _kernel32.SetInformationJobObject.restype = wintypes.BOOL
    _kernel32.AssignProcessToJobObject.argtypes = [
        wintypes.HANDLE,
        wintypes.HANDLE,
    ]
    _kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
    _kernel32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    _kernel32.TerminateJobObject.restype = wintypes.BOOL
    _kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    _kernel32.CloseHandle.restype = wintypes.BOOL


def _raise_last_windows_error() -> None:
    raise ctypes.WinError(ctypes.get_last_error())


def _create_windows_job() -> Any:
    job = _kernel32.CreateJobObjectW(None, None)
    if not job:
        _raise_last_windows_error()
    information = _ExtendedLimitInformation()
    information.BasicLimitInformation.LimitFlags = 0x00002000
    if not _kernel32.SetInformationJobObject(
        job,
        9,
        ctypes.byref(information),
        ctypes.sizeof(information),
    ):
        _kernel32.CloseHandle(job)
        _raise_last_windows_error()
    return job


def _start_automated_process(
    command: list[str],
    project_root: Path,
    log_handle: Any,
) -> tuple[subprocess.Popen[Any], Any]:
    if os.name != "nt":
        return (
            subprocess.Popen(
                command,
                cwd=project_root,
                shell=False,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            ),
            None,
        )

    job = _create_windows_job()
    process = subprocess.Popen(
        [sys.executable, "-c", _WINDOWS_COMMAND_SUPERVISOR, *command],
        cwd=project_root,
        stdin=subprocess.PIPE,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
    )
    try:
        if not _kernel32.AssignProcessToJobObject(job, int(process._handle)):
            _raise_last_windows_error()
        process.stdin.write(b"1")
        process.stdin.close()
        process.stdin = None
    except BaseException:
        process.kill()
        process.wait()
        _kernel32.CloseHandle(job)
        raise
    return process, job


def _terminate_automated_process(
    process: subprocess.Popen[Any],
    job: Any,
) -> None:
    if os.name == "nt":
        if not _kernel32.TerminateJobObject(job, 124):
            _raise_last_windows_error()
    else:
        os.killpg(process.pid, signal.SIGKILL)
    process.wait()


def require_nonempty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AssureError(f"{field} must be a non-empty string")
    return value


def flatten_scenarios(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    scenarios: list[dict[str, Any]] = []
    scenario_ids: set[str] = set()
    for section in manifest["sections"]:
        if not isinstance(section, dict):
            raise AssureError("manifest section must be an object")
        section_id = require_nonempty_string(section.get("id"), "section id")
        section_name = require_nonempty_string(section.get("name"), "section name")
        section_scenarios = section.get("scenarios", [])
        if not isinstance(section_scenarios, list):
            raise AssureError(f"section scenarios must be a list: {section_id}")
        for scenario in section_scenarios:
            if not isinstance(scenario, dict):
                raise AssureError("manifest scenario must be an object")
            scenario_id = require_nonempty_string(
                scenario.get("id"),
                "scenario id",
            )
            if scenario_id in scenario_ids:
                raise AssureError(f"duplicate scenario id: {scenario_id}")
            scenario_ids.add(scenario_id)
            require_nonempty_string(scenario.get("name"), "scenario name")
            risk = scenario.get("risk")
            if risk not in RISKS:
                raise AssureError(f"unsupported scenario risk: {risk}")
            verification = scenario.get("verification")
            if not isinstance(verification, dict):
                raise AssureError(
                    f"scenario verification must be an object: {scenario_id}"
                )
            mode = verification.get("mode")
            if mode not in MODES:
                raise AssureError(f"unsupported verification mode: {mode}")
            if mode == "automated":
                tests = verification.get("tests")
                if not isinstance(tests, list) or not tests:
                    raise AssureError(
                        "automated scenario requires at least one test: "
                        f"{scenario_id}"
                    )
                for test in tests:
                    if not isinstance(test, dict):
                        raise AssureError(
                            f"automated test must be an object: {scenario_id}"
                        )
                    build_runner_command(test, Path.cwd())
            item = dict(scenario)
            item["section_id"] = section_id
            item["section_name"] = section_name
            scenarios.append(item)
    return scenarios


def result_for_non_automated(scenario: dict[str, Any]) -> dict[str, Any]:
    verification = scenario["verification"]
    mode = verification["mode"]
    statuses = {"manual": "👁", "uncovered": "?", "excluded": "—"}
    return {
        "id": scenario["id"],
        "name": scenario["name"],
        "section": scenario["section_name"],
        "risk": scenario["risk"],
        "mode": mode,
        "status": statuses[mode],
        "instructions": verification.get("instructions", []),
        "reason": verification.get("reason"),
    }


def safe_artifact_name(scenario_id: str) -> str:
    safe_prefix = "".join(
        character
        if character.isascii()
        and (character.isalnum() or character in {"-", "_", "."})
        else "_"
        for character in scenario_id
    )[:64].strip("._")
    if not safe_prefix:
        safe_prefix = "scenario"
    digest = hashlib.sha256(scenario_id.encode("utf-8")).hexdigest()
    return f"{safe_prefix}-{digest}"


def run_automated(
    project_root: Path,
    scenario: dict[str, Any],
    artifacts: Path,
    sandbox: Sandbox,
) -> dict[str, Any]:
    tests = scenario["verification"]["tests"]
    scenario_artifact = artifacts / f"{safe_artifact_name(scenario['id'])}.log"
    scenario_artifact.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    exit_code = 0
    with scenario_artifact.open("w", encoding="utf-8") as log_handle:
        for test in tests:
            runner_command = build_runner_command(test, project_root)
            command = sandbox.wrap(runner_command.argv(), test["runner"])
            log_handle.write(f"$ {' '.join(command)}\n")
            log_handle.flush()
            # shell=True is limited to commands in a human-approved manifest.
            process, job = _start_automated_process(
                command,
                sandbox.root,
                log_handle,
            )
            try:
                process.wait(timeout=AUTOMATED_TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired:
                _terminate_automated_process(process, job)
                log_handle.write(
                    f"command timed out after {AUTOMATED_TIMEOUT_SECONDS} seconds\n"
                )
                exit_code = 124
                continue
            finally:
                if job is not None:
                    _kernel32.CloseHandle(job)
            if process.returncode != 0:
                exit_code = process.returncode
    duration = round(time.monotonic() - started, 3)
    return {
        "id": scenario["id"],
        "name": scenario["name"],
        "section": scenario["section_name"],
        "risk": scenario["risk"],
        "mode": "automated",
        "status": "O" if exit_code == 0 else "X",
        "exit_code": exit_code,
        "duration_seconds": duration,
        "artifact": str(scenario_artifact),
    }


def apply_verdict(results: list[dict[str, Any]]) -> str:
    priority = 0
    for result in results:
        risk = result["risk"]
        status = result["status"]
        if risk == "critical" and status in {"X", "👁", "?"}:
            priority = max(priority, 3)
        elif risk == "high" and status == "X":
            priority = max(priority, 3)
        elif risk == "high" and status in {"👁", "?"}:
            priority = max(priority, 2)
        elif risk == "normal" and status in {"X", "👁", "?"}:
            priority = max(priority, 1)
    return {
        0: "releasable",
        1: "warning",
        2: "approval-required",
        3: "blocked",
    }[priority]


def render_report(summary: dict[str, Any]) -> str:
    counts = summary["counts"]
    language = summary.get("language", "en")
    verdict = localize(f"verdict.{summary['verdict']}", language)
    lines = [
        f"# {localize('report.title', language)}",
        "",
        f"**{localize('report.verdict', language, verdict=verdict)}**",
        f"**{localize('report.baseline_commit', language, commit=summary['baseline_commit'])}**",
        f"**{localize('report.generated_at', language, timestamp=summary['generated_at'])}**",
        "",
        f"## {localize('report.summary', language)}",
        "",
        f"- O: {counts.get('O', 0)}",
        f"- X: {counts.get('X', 0)}",
        f"- 👁: {counts.get('👁', 0)}",
        f"- ?: {counts.get('?', 0)}",
        f"- —: {counts.get('—', 0)}",
        "",
        f"## {localize('report.unresolved', language)}",
        "",
    ]
    unresolved = [
        result
        for result in summary["results"]
        if result["status"] in {"X", "👁", "?"}
    ]
    if not unresolved:
        lines.append(f"- {localize('report.none', language)}")
    for result in unresolved:
        lines.append(
            f"- {result['status']} `{result['id']}` — {result['name']} "
            f"(risk: {result['risk']})"
        )
        if result.get("artifact"):
            lines.append(f"  - {localize('report.artifact', language, artifact=result['artifact'])}")
        for instruction in result.get("instructions", []):
            lines.append(f"  - {localize('report.manual', language, instruction=instruction)}")
    lines.extend(["", f"## {localize('report.all_results', language)}", ""])
    for result in summary["results"]:
        lines.append(
            f"- {result['status']} `{result['id']}` — "
            f"{result['section']} / {result['name']}"
        )
        if result.get("mode") == "automated":
            lines.append(
                f"  - {localize('report.duration', language, duration=result['duration_seconds'])}"
            )
            lines.append(f"  - {localize('report.exit_code', language, exit_code=result['exit_code'])}")
            lines.append(f"  - {localize('report.artifact', language, artifact=result['artifact'])}")
    lines.extend([
        "",
        f"## {localize('report.artifact_directory', language)}",
        "",
        f"`{summary['artifact_directory']}`",
        "",
    ])
    return "\n".join(lines)


def count_statuses(results: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for result in results:
        status = result["status"]
        counts[status] = counts.get(status, 0) + 1
    return counts


def contained_path(path: Path, directory: Path, label: str) -> Path:
    resolved_directory = directory.resolve()
    resolved_path = path.resolve()
    try:
        resolved_path.relative_to(resolved_directory)
    except ValueError as exc:
        raise AssureError(
            f"{label} must be under {resolved_directory}"
        ) from exc
    return resolved_path


def manifest_identity(
    manifest_path: Path,
    manifest: Optional[dict[str, Any]] = None,
) -> dict[str, str]:
    loaded = manifest if manifest is not None else load_manifest(manifest_path)
    baseline_commit = loaded["baseline"].get("commit")
    if not isinstance(baseline_commit, str) or not baseline_commit:
        raise AssureError("manifest baseline commit is missing")
    return {
        "baseline_commit": baseline_commit,
        "manifest_sha256": sha256_file(manifest_path),
    }


def reports_directory_for_summary(summary_path: Path) -> Path:
    resolved_summary = summary_path.resolve()
    for parent in resolved_summary.parents:
        if parent.name == "reports" and parent.parent.name == ".assure":
            return parent
    raise AssureError(
        "summary path must be under a project .assure/reports directory"
    )


def record_manual_result(
    summary_path: Path,
    scenario_id: str,
    response: str,
    actor: str,
    reason: Optional[str],
    reports_directory: Optional[Path] = None,
) -> dict[str, Any]:
    response_status = {
        "confirmed": "O",
        "failed": "X",
        "indeterminate": "?",
        "excluded": "—",
    }
    if response not in response_status:
        raise AssureError(f"unsupported manual response: {response}")
    if not isinstance(actor, str) or not actor.strip():
        raise AssureError("manual result requires an actor")
    if response == "excluded" and not reason:
        raise AssureError("excluded manual result requires a reason")
    if reports_directory is None:
        reports_directory = reports_directory_for_summary(summary_path)
    resolved_reports = reports_directory.resolve()
    if (
        resolved_reports.name != "reports"
        or resolved_reports.parent.name != ".assure"
    ):
        raise AssureError(
            "reports directory must be a project .assure/reports directory"
        )
    summary_path = contained_path(
        summary_path,
        resolved_reports,
        "summary path",
    )
    project_root = resolved_reports.parent.parent
    state = classify_project(project_root)
    if state.kind != "approved-current":
        raise AssureError(
            f"project is not approved-current: {state.kind}"
        )
    current_identity = manifest_identity(Path(state.manifest_path))
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AssureError(f"cannot read verification summary: {exc}") from exc
    if not isinstance(summary, dict) or not isinstance(
        summary.get("results"),
        list,
    ):
        raise AssureError("verification summary is damaged")
    if summary.get("manifest_identity") != current_identity:
        raise AssureError(
            "verification summary manifest identity does not match "
            "the current approved manifest"
        )
    report_value = summary.get("report")
    if not isinstance(report_value, str) or not report_value:
        raise AssureError("verification summary report path is damaged")
    report_path = Path(report_value)
    report_path = contained_path(
        report_path,
        resolved_reports,
        "report path",
    )
    selected = None
    for result in summary["results"]:
        if isinstance(result, dict) and result.get("id") == scenario_id:
            selected = result
            break
    if selected is None:
        raise AssureError(f"scenario not found in summary: {scenario_id}")
    if selected.get("mode") != "manual":
        raise AssureError(f"scenario is not manual: {scenario_id}")
    selected["status"] = response_status[response]
    selected["confirmed_by"] = actor
    selected["confirmed_at"] = datetime.now(timezone.utc).isoformat()
    if reason:
        selected["reason"] = reason
    summary["counts"] = count_statuses(summary["results"])
    summary["verdict"] = apply_verdict(summary["results"])
    write_json(summary_path, summary)
    report_path.write_text(render_report(summary), encoding="utf-8")
    return summary


def execute_manifest(
    project_root: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    approved_manifest_identity = manifest_identity(manifest_path, manifest)
    scenarios = flatten_scenarios(manifest)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    assure_dir = project_root / ".assure"
    artifacts = assure_dir / "artifacts" / timestamp
    results: list[dict[str, Any]] = []
    sandbox = None
    mock_result = None
    automated = any(item["verification"]["mode"] == "automated" for item in scenarios)
    if automated:
        try:
            sandbox = prepare_sandbox(project_root)
            framework = next(
                test["runner"]
                for item in scenarios
                if item["verification"]["mode"] == "automated"
                for test in item["verification"]["tests"]
            )
            mock_result = inject_mocks(sandbox.root, framework)
        except SandboxUnavailable as exc:
            for scenario in scenarios:
                if scenario["verification"]["mode"] == "automated":
                    item = result_for_non_automated({
                        **scenario,
                        "verification": {"mode": "uncovered"},
                    })
                    item["reason"] = str(exc)
                    item["status"] = "?"
                    results.append(item)
                else:
                    results.append(result_for_non_automated(scenario))
    if not results:
        try:
            for scenario in scenarios:
                mode = scenario["verification"]["mode"]
                if mode == "automated":
                    results.append(run_automated(project_root, scenario, artifacts, sandbox))
                else:
                    results.append(result_for_non_automated(scenario))
        finally:
            if sandbox is not None:
                sandbox.cleanup()
    counts = count_statuses(results)
    summary = {
        "language": detect_language(project_root),
        "verdict": apply_verdict(results),
        "baseline_commit": manifest["baseline"]["commit"],
        "manifest_identity": approved_manifest_identity,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "artifact_directory": str(artifacts),
        "counts": counts,
        "results": results,
        "sandbox": {
            "provider": sandbox.provider if sandbox else None,
            "network": sandbox.network if sandbox else "not-run",
        },
        "automatic_mocks": {
            "injected": mock_result.injected if mock_result else [],
            "conflicts": mock_result.conflicts if mock_result else [],
            "unverifiable": mock_result.unverifiable if mock_result else [],
        },
    }
    report_path = (
        assure_dir / "reports" / f"{timestamp}-release-verification.md"
    )
    summary_path = (
        assure_dir / "reports" / f"{timestamp}-release-verification.json"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    summary["report"] = str(report_path)
    summary["summary_path"] = str(summary_path)
    report_path.write_text(render_report(summary), encoding="utf-8")
    write_json(summary_path, summary)
    return summary


def exit_code_for_verdict(verdict: str) -> int:
    return 1 if verdict in {"blocked", "approval-required"} else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--manual-result")
    parser.add_argument(
        "--response",
        choices=["confirmed", "failed", "indeterminate", "excluded"],
    )
    parser.add_argument("--actor")
    parser.add_argument("--reason")
    args = parser.parse_args()
    if args.manual_result:
        if not args.summary or not args.response or not args.actor:
            parser.error(
                "--manual-result requires --summary, --response, and --actor"
            )
    project = args.project.resolve()
    state = classify_project(project)
    if state.kind != "approved-current":
        emit_json({
            "state": state.kind,
            "reason": state.reason,
            "verdict": "not-run",
        })
        return 2
    if args.manual_result:
        reports_directory = project / ".assure" / "reports"
        try:
            summary = record_manual_result(
                args.summary,
                args.manual_result,
                args.response,
                args.actor,
                args.reason,
                reports_directory,
            )
        except AssureError as exc:
            emit_json({
                "state": "manual-update-failed",
                "reason": str(exc),
                "verdict": "not-run",
            })
            return 2
        emit_json(summary)
        return exit_code_for_verdict(summary["verdict"])

    try:
        summary = execute_manifest(project, Path(state.manifest_path))
    except AssureError as exc:
        emit_json({
            "state": "damaged",
            "reason": str(exc),
            "verdict": "not-run",
        })
        return 2
    emit_json(summary)
    return exit_code_for_verdict(summary["verdict"])


if __name__ == "__main__":
    raise SystemExit(main())
