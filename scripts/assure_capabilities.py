from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

if __package__:
    from .assure_output import emit_json
    from .detect_environment import detect_environment
else:
    from assure_output import emit_json
    from detect_environment import detect_environment


def _package_dependencies(root: Path) -> set[str]:
    path = root / "package.json"
    if not path.exists():
        return set()
    try:
        package = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    names: set[str] = set()
    for field in ("dependencies", "devDependencies"):
        value = package.get(field, {})
        if isinstance(value, dict):
            names.update(str(name) for name in value)
    return names


def _container_access(provider: str, executable: str | None) -> dict[str, Any]:
    if not executable:
        return {"status": "absent", "reason": f"{provider} is not installed"}
    try:
        result = subprocess.run(
            [executable, "info"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status": "unavailable", "reason": str(exc)}
    if result.returncode == 0:
        return {"status": "ready", "reason": f"{provider} runtime is accessible"}
    detail = (result.stderr or result.stdout).strip()
    lowered = detail.lower()
    status = (
        "permission-required"
        if "permission denied" in lowered or "access is denied" in lowered
        else "unavailable"
    )
    return {"status": status, "reason": detail[-500:]}


def assess_capabilities(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    environment = detect_environment(root)
    dependencies = _package_dependencies(root)
    react = "react" in dependencies
    dom_packages = sorted(
        dependencies
        & {
            "jsdom",
            "happy-dom",
            "react-test-renderer",
            "@testing-library/react",
            "@playwright/test",
            "cypress",
        }
    )
    prepared_node = root / ".assure" / "capabilities" / "node" / "metadata.json"
    prepared_capabilities: set[str] = set()
    prepared_metadata: dict[str, Any] = {}
    if prepared_node.is_file() and not prepared_node.is_symlink():
        try:
            metadata = json.loads(prepared_node.read_text(encoding="utf-8"))
            prepared_metadata = metadata if isinstance(metadata, dict) else {}
            prepared_capabilities = {
                str(item)
                for item in metadata.get("capabilities", [])
                if isinstance(item, str)
            }
        except (OSError, json.JSONDecodeError):
            prepared_capabilities = set()
    docker = _container_access("Docker", shutil.which("docker"))
    podman = _container_access("Podman", shutil.which("podman"))
    local_guard = shutil.which("sandbox-exec") if os.sys.platform == "darwin" else None
    isolation_ready = (
        docker["status"] == "ready"
        or podman["status"] == "ready"
        or bool(local_guard)
    )
    write_target = root / ".assure" if (root / ".assure").exists() else root
    capabilities = [
        {
            "id": "os-isolation",
            "status": "ready" if isolation_ready else "unavailable",
            "reason": (
                "container or supported OS isolation is available"
                if isolation_ready
                else "no container or supported OS isolation provider is available"
            ),
        },
        {
            "id": "project-assure-write",
            "status": "ready" if os.access(write_target, os.W_OK) else "permission-required",
            "reason": f"write access for {write_target}",
            "admin_required": False,
        },
    ]
    if react:
        dom_ready = bool(dom_packages) or "react-dom-execution" in prepared_capabilities
        capabilities.append({
            "id": "react-dom-execution",
            "status": "ready" if dom_ready else "preparation-required",
            "reason": (
                f"DOM-capable packages detected: {', '.join(dom_packages)}"
                if dom_packages
                else "Assure-owned locked DOM capability overlay is prepared"
                if dom_ready
                else "React behavior is present but no DOM-capable test environment is declared"
            ),
            "preparation": None if dom_ready else {
                "action": "prepare a DOM-capable React test adapter in the Assure temporary copy",
                "scope": "temporary-copy-only",
                "requires_user_approval": True,
            },
        })
    return {
        "project_root": str(root),
        "environment": environment,
        "host": {
            "effective_uid": os.geteuid() if hasattr(os, "geteuid") else None,
            "is_administrator": (
                os.geteuid() == 0 if hasattr(os, "geteuid") else None
            ),
            "administrator_required": False,
            "policy": "least-privilege; request elevation only for a proven capability gap",
        },
        "providers": {
            "docker": docker,
            "podman": podman,
            "sandbox_exec": {
                "status": "ready" if local_guard else "absent",
                "path": local_guard,
            },
        },
        "capabilities": capabilities,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True, type=Path)
    args = parser.parse_args()
    emit_json(assess_capabilities(args.project))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
