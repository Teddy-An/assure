from __future__ import annotations

import argparse
import re
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any

if __package__:
    from .assure_common import AssureError, load_manifest
    from .assure_output import emit_json
else:
    from assure_common import AssureError, load_manifest
    from assure_output import emit_json


POLICY = "functional-probes-v1"
PROBE_CASES = {"success", "failure", "boundary"}
PROBE_ASSERTIONS = {"result", "side-effects"}
UNAVAILABLE_BLOCKERS = {
    "cannot-observe-outcome",
    "no-executable-boundary",
    "unsafe-boundary",
    "unsupported-runner",
}


@dataclass(frozen=True)
class PolicyValidation:
    valid: bool
    policy: str | None
    probe_count: int
    unavailable_count: int
    errors: list[str]


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _scenario_id(scenario: dict[str, Any]) -> str:
    value = scenario.get("id")
    return value if isinstance(value, str) and value else "<unknown>"


def _probe_path(argument: str, project_root: Path) -> Path | None:
    normalized = argument.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts:
        return None
    if path.parts[:2] != (".assure", "probes"):
        return None
    candidate = project_root.joinpath(*path.parts)
    probes_root = (project_root / ".assure" / "probes").resolve()
    try:
        candidate.resolve().relative_to(probes_root)
    except (OSError, ValueError):
        return None
    return candidate


def _validate_entry_points(
    entry_points: list[str],
    project_root: Path,
    scenario_id: str,
) -> list[str]:
    errors: list[str] = []
    for entry_point in entry_points:
        path_value, separator, symbol = entry_point.partition("#")
        path = PurePosixPath(path_value.replace("\\", "/"))
        if (
            not separator
            or not symbol.strip()
            or path.is_absolute()
            or ".." in path.parts
            or path.parts[:1] == (".assure",)
        ):
            errors.append(
                f"{scenario_id}: invalid probe entry_point: {entry_point}"
            )
            continue
        candidate = project_root.joinpath(*path.parts)
        if not candidate.is_file() or candidate.is_symlink():
            errors.append(
                f"{scenario_id}: probe entry_point file is missing or unsafe: "
                f"{path.as_posix()}"
            )
    return errors


def _validate_probe_source(
    path: Path,
    runner: Any,
    entry_points: list[str],
    scenario_id: str,
) -> list[str]:
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"{scenario_id}: cannot read probe file: {exc}"]
    errors: list[str] = []
    if len(source.strip()) < 40:
        errors.append(f"{scenario_id}: probe file has no executable test body")
    if runner in {"vitest", "jest"}:
        if not re.search(r"\b(?:it|test)\s*\(", source):
            errors.append(f"{scenario_id}: probe has no test declaration")
        if not re.search(r"\bexpect\s*\(", source):
            errors.append(f"{scenario_id}: probe has no result assertion")
    elif runner == "pytest":
        if not re.search(r"(?m)^\s*def\s+test_[A-Za-z0-9_]*\s*\(", source):
            errors.append(f"{scenario_id}: probe has no pytest test function")
        if not re.search(r"(?m)^\s*assert\s+", source):
            errors.append(f"{scenario_id}: probe has no result assertion")
    for entry_point in entry_points:
        symbol = entry_point.partition("#")[2].strip()
        if symbol and symbol not in source:
            errors.append(
                f"{scenario_id}: probe does not reference entry point symbol: "
                f"{symbol}"
            )
    return errors


def _validate_functional_probe(
    scenario: dict[str, Any],
    verification: dict[str, Any],
    project_root: Path,
) -> list[str]:
    scenario_id = _scenario_id(scenario)
    errors: list[str] = []
    evidence = verification.get("probe")
    if not isinstance(evidence, dict):
        return [f"{scenario_id}: functional probe evidence is missing"]
    entry_points = _strings(evidence.get("entry_points"))
    if not entry_points:
        errors.append(f"{scenario_id}: probe entry_points are missing")
    else:
        errors.extend(
            _validate_entry_points(entry_points, project_root, scenario_id)
        )
    cases = set(_strings(evidence.get("cases")))
    missing_cases = sorted(PROBE_CASES - cases)
    if missing_cases:
        errors.append(
            f"{scenario_id}: probe cases are missing: {', '.join(missing_cases)}"
        )
    assertions = set(_strings(evidence.get("assertions")))
    missing_assertions = sorted(PROBE_ASSERTIONS - assertions)
    if missing_assertions:
        errors.append(
            f"{scenario_id}: probe assertions are missing: "
            f"{', '.join(missing_assertions)}"
        )
    tests = verification.get("tests")
    if not isinstance(tests, list) or not tests:
        errors.append(f"{scenario_id}: functional probe tests are missing")
        return errors
    for index, test in enumerate(tests, start=1):
        if not isinstance(test, dict):
            errors.append(f"{scenario_id}: probe test {index} is invalid")
            continue
        selector = test.get("selector")
        if not isinstance(selector, str) or not selector.strip():
            errors.append(f"{scenario_id}: probe test {index} selector is missing")
        args = _strings(test.get("args"))
        paths = [
            candidate
            for argument in args
            if (candidate := _probe_path(argument, project_root)) is not None
        ]
        if len(paths) != 1:
            errors.append(
                f"{scenario_id}: probe test {index} must reference exactly one "
                ".assure/probes file"
            )
            continue
        path = paths[0]
        if not path.is_file() or path.is_symlink():
            errors.append(
                f"{scenario_id}: probe file is missing or unsafe: "
                f"{path.relative_to(project_root).as_posix()}"
            )
            continue
        errors.extend(
            _validate_probe_source(
                path,
                test.get("runner"),
                entry_points,
                scenario_id,
            )
        )
    return errors


def _validate_unavailable(
    scenario: dict[str, Any],
    verification: dict[str, Any],
) -> list[str]:
    scenario_id = _scenario_id(scenario)
    attempt = verification.get("probe_attempt")
    if not isinstance(attempt, dict):
        return [f"{scenario_id}: uncovered scenario has no probe_attempt evidence"]
    errors: list[str] = []
    if not _strings(attempt.get("entry_points")):
        errors.append(f"{scenario_id}: probe_attempt entry_points are missing")
    if not _strings(attempt.get("strategies")):
        errors.append(f"{scenario_id}: probe_attempt strategies are missing")
    blocker = attempt.get("blocker")
    if blocker not in UNAVAILABLE_BLOCKERS:
        errors.append(f"{scenario_id}: probe_attempt blocker is invalid")
    reason = attempt.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        errors.append(f"{scenario_id}: probe_attempt reason is missing")
    return errors


def validate_probe_policy(
    manifest: dict[str, Any],
    project_root: Path,
) -> PolicyValidation:
    policy = manifest["baseline"].get("verification_policy")
    errors: list[str] = []
    probe_count = 0
    unavailable_count = 0
    if policy != POLICY:
        errors.append(f"baseline verification_policy must be {POLICY}")
    for section in manifest.get("sections", []):
        if not isinstance(section, dict):
            errors.append("manifest section is invalid")
            continue
        for scenario in section.get("scenarios", []):
            if not isinstance(scenario, dict):
                errors.append("manifest scenario is invalid")
                continue
            verification = scenario.get("verification")
            if not isinstance(verification, dict):
                errors.append(f"{_scenario_id(scenario)}: verification is missing")
                continue
            mode = verification.get("mode")
            strategy = verification.get("strategy")
            if mode == "automated" and strategy == "functional-probe":
                probe_count += 1
                errors.extend(
                    _validate_functional_probe(
                        scenario,
                        verification,
                        project_root,
                    )
                )
            elif mode == "uncovered":
                unavailable_count += 1
                errors.extend(_validate_unavailable(scenario, verification))
    return PolicyValidation(
        valid=not errors,
        policy=policy if isinstance(policy, str) else None,
        probe_count=probe_count,
        unavailable_count=unavailable_count,
        errors=errors,
    )


def require_valid_probe_policy(
    manifest: dict[str, Any],
    project_root: Path,
) -> PolicyValidation:
    validation = validate_probe_policy(manifest, project_root)
    if not validation.valid:
        raise AssureError(
            "functional probe policy is invalid: " + "; ".join(validation.errors)
        )
    return validation


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True, type=Path)
    args = parser.parse_args()
    root = args.project.resolve()
    try:
        manifest = load_manifest(root / ".assure" / "verification-manifest.yaml")
        validation = validate_probe_policy(manifest, root)
    except AssureError as exc:
        emit_json({
            "valid": False,
            "policy": None,
            "probe_count": 0,
            "unavailable_count": 0,
            "errors": [str(exc)],
        })
        return 2
    emit_json(asdict(validation))
    return 0 if validation.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
