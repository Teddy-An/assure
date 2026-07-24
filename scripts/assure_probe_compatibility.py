from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

if __package__:
    from .assure_common import AssureError, load_manifest
    from .assure_identity import (
        ASSURE_VERSION,
        GENERATOR_CONTRACT,
        IDENTITY_PREFIX,
        PROBE_SCHEMA_VERSION,
        VERIFICATION_POLICY,
        distribution_sha256,
    )
    from .assure_output import emit_json
else:
    from assure_common import AssureError, load_manifest
    from assure_identity import (
        ASSURE_VERSION,
        GENERATOR_CONTRACT,
        IDENTITY_PREFIX,
        PROBE_SCHEMA_VERSION,
        VERIFICATION_POLICY,
        distribution_sha256,
    )
    from assure_output import emit_json


MARKER_PATTERN = re.compile(
    rf"{re.escape(IDENTITY_PREFIX)}\s+"
    r"version=(?P<version>\S+)\s+"
    r"distribution_sha256=(?P<distribution>[0-9a-f]{64})\s+"
    r"probe_schema=(?P<schema>\d+)\s+"
    r"generator_contract=(?P<contract>\S+)"
)


def probe_compatibility(path: Path) -> dict[str, Any]:
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        return {"compatible": False, "reason": f"cannot read probe: {exc}"}
    match = MARKER_PATTERN.search(source[:2000])
    if not match:
        return {
            "compatible": False,
            "reason": "Assure generation marker is missing",
        }
    expected_distribution = distribution_sha256()
    actual = match.groupdict()
    mismatches = []
    if actual["version"] != ASSURE_VERSION:
        mismatches.append("Assure version")
    if actual["distribution"] != expected_distribution:
        mismatches.append("Assure distribution hash")
    if int(actual["schema"]) != PROBE_SCHEMA_VERSION:
        mismatches.append("probe schema")
    if actual["contract"] != GENERATOR_CONTRACT:
        mismatches.append("generator contract")
    return {
        "compatible": not mismatches,
        "reason": (
            "current Assure generation identity"
            if not mismatches
            else "incompatible " + ", ".join(mismatches)
        ),
        "generated_by": {
            "assure_version": actual["version"],
            "distribution_sha256": actual["distribution"],
            "probe_schema": int(actual["schema"]),
            "generator_contract": actual["contract"],
        },
    }


def stale_probe_files(project_root: Path) -> list[dict[str, Any]]:
    root = project_root.resolve()
    probes = root / ".assure" / "probes"
    if not probes.exists():
        return []
    if not probes.is_dir() or probes.is_symlink():
        raise AssureError("Assure probes path must be a real directory")
    stale = []
    legacy_policy = False
    manifest_path = root / ".assure" / "verification-manifest.yaml"
    if manifest_path.is_file() and not manifest_path.is_symlink():
        try:
            manifest = load_manifest(manifest_path)
            legacy_policy = (
                manifest.get("baseline", {}).get("verification_policy")
                != VERIFICATION_POLICY
            )
        except AssureError:
            legacy_policy = True
    for path in sorted(probes.rglob("*")):
        if path.is_symlink():
            raise AssureError("linked Assure probe is unsafe")
        if not path.is_file():
            continue
        compatibility = (
            {
                "compatible": False,
                "reason": "legacy verification policy requires full regeneration",
            }
            if legacy_policy
            else probe_compatibility(path)
        )
        if not compatibility["compatible"]:
            stale.append({
                "path": path.relative_to(root).as_posix(),
                "reason": compatibility["reason"],
            })
    return stale


def delete_stale_probes(project_root: Path) -> list[dict[str, Any]]:
    root = project_root.resolve()
    stale = stale_probe_files(root)
    for item in stale:
        path = root / item["path"]
        path.unlink()
    probes = root / ".assure" / "probes"
    if probes.exists():
        for directory in sorted(
            (path for path in probes.rglob("*") if path.is_dir()),
            reverse=True,
        ):
            try:
                directory.rmdir()
            except OSError:
                pass
    return stale


def current_policy(project_root: Path) -> bool:
    manifest_path = (
        project_root.resolve() / ".assure" / "verification-manifest.yaml"
    )
    if not manifest_path.is_file() or manifest_path.is_symlink():
        return False
    try:
        manifest = load_manifest(manifest_path)
    except AssureError:
        return False
    return (
        manifest.get("baseline", {}).get("verification_policy")
        == VERIFICATION_POLICY
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--delete-stale", action="store_true")
    args = parser.parse_args()
    try:
        stale = (
            delete_stale_probes(args.project)
            if args.delete_stale
            else stale_probe_files(args.project)
        )
    except AssureError as exc:
        emit_json({"status": "failed", "reason": str(exc)})
        return 2
    policy_current = current_policy(args.project)
    emit_json({
        "status": "deleted" if args.delete_stale else "checked",
        "compatible": policy_current and not stale,
        "verification_policy_current": policy_current,
        "stale": stale,
        "regeneration_required": bool(stale) or not policy_current,
    })
    return 1 if (stale or not policy_current) and not args.delete_stale else 0


if __name__ == "__main__":
    raise SystemExit(main())
