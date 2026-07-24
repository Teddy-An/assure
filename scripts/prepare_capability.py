from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

if __package__:
    from .assure_common import AssureError
    from .assure_output import emit_json
else:
    from assure_common import AssureError
    from assure_output import emit_json


CAPABILITY_PACKAGES = {
    "react-dom-execution": [
        "jsdom",
        "@testing-library/react",
        "@testing-library/user-event",
    ],
}


PACKAGE_NAME = re.compile(
    r"^(?:@[a-z0-9][a-z0-9._-]*/)?[a-z0-9][a-z0-9._-]*$",
    re.IGNORECASE,
)


def prepare_capability(
    project_root: Path,
    capability: str,
    requested_packages: list[str] | None = None,
) -> dict[str, object]:
    root = project_root.resolve()
    packages = CAPABILITY_PACKAGES.get(capability) or requested_packages
    if not packages:
        raise AssureError(
            "a capability without a built-in recipe requires an explicit "
            "approved package plan"
        )
    if any(not PACKAGE_NAME.fullmatch(package) for package in packages):
        raise AssureError("capability package plan contains an invalid package name")
    package_json = root / "package.json"
    package_lock = root / "package-lock.json"
    if not package_json.is_file() or not package_lock.is_file():
        raise AssureError(
            "package.json and package-lock.json are required for locked "
            "capability preparation"
        )
    npm = shutil.which("npm")
    if not npm:
        raise AssureError("npm is required for this approved capability preparation")
    output = root / ".assure" / "capabilities" / "node"
    existing_capabilities: set[str] = set()
    existing_packages: set[str] = set()
    base_package_json = package_json
    base_package_lock = package_lock
    existing_metadata_path = output / "metadata.json"
    if existing_metadata_path.is_file():
        try:
            existing_metadata = json.loads(
                existing_metadata_path.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError):
            existing_metadata = {}
        current_source_hash = hashlib.sha256(package_lock.read_bytes()).hexdigest()
        if (
            existing_metadata.get("source_package_lock_sha256")
            == current_source_hash
            and (output / "package.json").is_file()
            and (output / "package-lock.json").is_file()
        ):
            base_package_json = output / "package.json"
            base_package_lock = output / "package-lock.json"
            existing_capabilities.update(
                str(item)
                for item in existing_metadata.get("capabilities", [])
                if isinstance(item, str)
            )
            existing_packages.update(
                str(item)
                for item in existing_metadata.get("packages", [])
                if isinstance(item, str)
            )
    with tempfile.TemporaryDirectory(prefix="assure-capability-") as directory:
        temporary = Path(directory)
        shutil.copy2(base_package_json, temporary / "package.json")
        shutil.copy2(base_package_lock, temporary / "package-lock.json")
        command = [
            npm,
            "install",
            "--package-lock-only",
            "--ignore-scripts",
            "--no-audit",
            "--no-fund",
            "--save-dev",
            *packages,
        ]
        completed = subprocess.run(
            command,
            cwd=temporary,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout).strip()
            raise AssureError(
                "capability dependency resolution failed: "
                + (detail[-2000:] or f"exit code {completed.returncode}")
            )
        output.mkdir(parents=True, exist_ok=True)
        resolved_package = output / "package.json"
        resolved_lock = output / "package-lock.json"
        shutil.copy2(temporary / "package.json", resolved_package)
        shutil.copy2(temporary / "package-lock.json", resolved_lock)
    lock_sha256 = hashlib.sha256(resolved_lock.read_bytes()).hexdigest()
    metadata = {
        "schema_version": 1,
        "capabilities": sorted(existing_capabilities | {capability}),
        "packages": sorted(existing_packages | set(packages)),
        "package_lock_sha256": lock_sha256,
        "source_package_lock_sha256": hashlib.sha256(
            package_lock.read_bytes()
        ).hexdigest(),
    }
    (output / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "status": "prepared",
        "capability": capability,
        "scope": "Assure-owned .assure/capabilities/node overlay",
        "packages": packages,
        "package_lock_sha256": lock_sha256,
        "original_project_files_modified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument(
        "--capability",
        required=True,
    )
    parser.add_argument(
        "--package",
        action="append",
        default=[],
        help="exact package from an approved LLM-generated capability plan",
    )
    parser.add_argument(
        "--approved",
        action="store_true",
        help="required acknowledgement that the user approved network resolution",
    )
    args = parser.parse_args()
    if not args.approved:
        emit_json({
            "status": "refused",
            "capability": args.capability,
            "packages": CAPABILITY_PACKAGES.get(args.capability) or args.package,
            "reason": (
                "the one complete Sandbox approval must already be recorded; "
                "this command never opens a separate approval step"
            ),
        })
        return 2
    try:
        result = prepare_capability(
            args.project,
            args.capability,
            args.package or None,
        )
    except AssureError as exc:
        emit_json({"status": "failed", "reason": str(exc)})
        return 2
    emit_json(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
