from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__:
    from .assure_capabilities import assess_capabilities
    from .assure_common import AssureError, write_json
    from .assure_identity import current_identity
    from .assure_output import emit_json
else:
    from assure_capabilities import assess_capabilities
    from assure_common import AssureError, write_json
    from assure_identity import current_identity
    from assure_output import emit_json


PROFILE_SCHEMA_VERSION = 1
PROFILE_FILES = (
    "package.json",
    "package-lock.json",
    "npm-shrinkwrap.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "pyproject.toml",
    "poetry.lock",
    "requirements.txt",
    "uv.lock",
    "firestore.rules",
    "firebase.json",
    "vite.config.ts",
    "vite.config.js",
    "vitest.config.ts",
    "vitest.config.js",
)


def _file_fingerprint(root: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for name in PROFILE_FILES:
        path = root / name
        if path.is_file() and not path.is_symlink():
            values[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return values


def _environment_fingerprint(files: dict[str, str]) -> str:
    encoded = json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def build_sandbox_profile(
    project_root: Path,
    decisions: dict[str, str] | None = None,
    approved_by: str | None = None,
) -> dict[str, Any]:
    root = project_root.resolve()
    assessment = assess_capabilities(root)
    choices = decisions or {}
    capabilities = []
    unresolved = []
    for item in assessment["capabilities"]:
        capability = dict(item)
        capability_id = capability["id"]
        decision = choices.get(capability_id)
        if decision:
            capability["decision"] = decision
        status = capability["status"]
        if status in {
            "preparation-required",
            "permission-required",
            "unavailable",
        }:
            if decision == "unavailable":
                capability["resolution"] = "unverified-provider-unavailable"
            else:
                unresolved.append({
                    "capability": capability_id,
                    "status": status,
                    "reason": capability["reason"],
                    "preparation": capability.get("preparation"),
                })
        capabilities.append(capability)
    files = _file_fingerprint(root)
    profile = {
        "schema_version": PROFILE_SCHEMA_VERSION,
        "generated_by": current_identity(),
        "project_root": str(root),
        "environment_fingerprint": _environment_fingerprint(files),
        "environment_files": files,
        "environment": assessment["environment"],
        "host_policy": assessment["host"],
        "providers": assessment["providers"],
        "capabilities": capabilities,
        "status": "approval-required" if unresolved else "ready",
        "unresolved": unresolved,
        "sandbox_contract": {
            "source": "temporary-copy",
            "credentials": "stripped",
            "production_data": "forbidden",
            "production_services": "forbidden",
            "network": "os-blocked-required",
            "test_data": "sandbox-owned",
            "cleanup": "required",
        },
        "execution_order": [
            "validate-environment-fingerprint",
            "create-isolated-copy",
            "apply-approved-capabilities",
            "bootstrap-locked-dependencies",
            "verify-isolation-and-adapters",
            "initialize-test-data",
            "run-complete-scenario-population",
            "remove-sandbox",
        ],
    }
    plan_bytes = json.dumps(
        {
            "environment_fingerprint": profile["environment_fingerprint"],
            "capabilities": profile["capabilities"],
            "sandbox_contract": profile["sandbox_contract"],
            "execution_order": profile["execution_order"],
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    profile["plan_sha256"] = hashlib.sha256(plan_bytes).hexdigest()
    profile["approval"] = (
        {
            "status": "approved",
            "approved_by": approved_by,
            "approved_at": datetime.now(timezone.utc).isoformat(),
            "plan_sha256": profile["plan_sha256"],
            "scope": "complete-sandbox-plan",
        }
        if approved_by
        else {"status": "not-recorded"}
    )
    return profile


def validate_sandbox_profile(
    project_root: Path,
    profile: dict[str, Any],
) -> list[str]:
    current = build_sandbox_profile(project_root)
    errors = []
    if profile.get("schema_version") != PROFILE_SCHEMA_VERSION:
        errors.append("sandbox profile schema version is unsupported")
    if profile.get("project_root") != str(project_root.resolve()):
        errors.append("sandbox profile belongs to another project")
    if profile.get("environment_fingerprint") != current["environment_fingerprint"]:
        errors.append("sandbox profile is stale for the current project environment")
    if profile.get("status") != "ready":
        errors.append("sandbox profile has unresolved preparation requirements")
    approval = profile.get("approval", {})
    if approval.get("status") != "approved":
        errors.append("sandbox plan has no recorded user approval")
    elif approval.get("plan_sha256") != profile.get("plan_sha256"):
        errors.append("sandbox approval does not match the current plan")
    return errors


def load_sandbox_profile(project_root: Path) -> dict[str, Any]:
    path = project_root.resolve() / ".assure" / "sandbox-profile.json"
    if not path.is_file() or path.is_symlink():
        raise AssureError("sandbox profile is missing")
    try:
        profile = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AssureError(f"sandbox profile is invalid: {exc}") from exc
    errors = validate_sandbox_profile(project_root, profile)
    if errors:
        raise AssureError("; ".join(errors))
    return profile


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--approved-write", action="store_true")
    parser.add_argument(
        "--approved-by",
        help="actor recorded as approving the complete Sandbox plan",
    )
    parser.add_argument("--unavailable", action="append", default=[])
    args = parser.parse_args()
    if args.write and (not args.approved_write or not args.approved_by):
        emit_json({
            "status": "approval-required",
            "reason": (
                "one explicit approval and approving actor are required for "
                "the complete Sandbox plan"
            ),
        })
        return 3
    decisions = {item: "unavailable" for item in args.unavailable}
    profile = build_sandbox_profile(
        args.project,
        decisions,
        args.approved_by if args.write else None,
    )
    if args.write:
        path = args.project.resolve() / ".assure" / "sandbox-profile.json"
        write_json(path, profile)
        profile["profile_path"] = str(path)
    emit_json(profile)
    return 0 if profile["status"] == "ready" else 3


if __name__ == "__main__":
    raise SystemExit(main())
