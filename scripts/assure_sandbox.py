from __future__ import annotations

import os
import shutil
import stat
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

if __package__:
    from .assure_common import AssureError
else:
    from assure_common import AssureError


EXCLUDED = {
    ".assure", ".aws", ".azure", ".env", ".git", ".gcloud", ".netrc",
    ".next", ".npmrc", ".pypirc", "build", "coverage", "dist",
    "node_modules", "target", "vendor",
}
SENSITIVE_NAMES = {
    "credentials.json",
    "service-account.json",
    "service_account.json",
}
SENSITIVE_SUFFIXES = {".key", ".p12", ".pem", ".pfx"}


class SandboxUnavailable(AssureError):
    pass


@dataclass(frozen=True)
class BootstrapResult:
    status: str
    detail: str
    network: str = "dependency-download-only"


@dataclass
class Sandbox:
    root: Path
    provider: str
    network: str = "disabled"

    def bootstrap(self, runners: set[str]) -> BootstrapResult:
        commands: list[list[str]] = []
        if runners & {"vitest", "jest"}:
            if not (self.root / "package-lock.json").exists():
                return BootstrapResult(
                    "unavailable",
                    "package-lock.json is required for isolated Node dependency bootstrap",
                )
            commands.append([
                self.provider,
                "run",
                "--rm",
                "--network",
                "bridge",
                "--env",
                "CI=1",
                "--volume",
                f"{self.root}:/workspace",
                "--workdir",
                "/workspace",
                "node:22",
                "npm",
                "ci",
                "--ignore-scripts",
                "--no-bin-links",
                "--no-audit",
                "--no-fund",
            ])
        if "pytest" in runners:
            requirements = self.root / "requirements.txt"
            if not requirements.exists():
                return BootstrapResult(
                    "unavailable",
                    "requirements.txt with hashes is required for isolated Python dependency bootstrap",
                )
            commands.append([
                self.provider,
                "run",
                "--rm",
                "--network",
                "bridge",
                "--volume",
                f"{self.root}:/workspace",
                "--workdir",
                "/workspace",
                "python:3.13",
                "python",
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-input",
                "--only-binary=:all:",
                "--require-hashes",
                "-r",
                "requirements.txt",
            ])
        for command in commands:
            try:
                completed = subprocess.run(
                    command,
                    cwd=self.root,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=300,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                return BootstrapResult("failed", str(exc))
            if completed.returncode != 0:
                detail = (completed.stderr or completed.stdout).strip()
                return BootstrapResult(
                    "failed",
                    detail[-2000:] or "dependency bootstrap failed",
                )
        return BootstrapResult("ready", "dependencies installed without lifecycle scripts")

    def wrap(self, argv: list[str], runner: str) -> list[str]:
        image = "python:3.13" if runner == "pytest" else "node:22"
        if runner == "pytest":
            container_argv = ["python", "-m", "pytest", *argv[3:]]
        elif runner == "vitest":
            container_argv = [
                "node",
                "node_modules/vitest/vitest.mjs",
                *argv[3:],
            ]
            container_argv.append("--setupFiles=.assure-auto-mocks.ts")
        elif runner == "jest":
            container_argv = [
                "node",
                "node_modules/jest/bin/jest.js",
                *argv[3:],
            ]
        else:
            raise AssureError(f"unsupported sandbox runner: {runner}")
        return [
            self.provider,
            "run",
            "--rm",
            "--network",
            "none",
            "--env",
            "CI=1",
            "--volume",
            f"{self.root}:/workspace",
            "--workdir",
            "/workspace",
            image,
            *container_argv,
        ]

    def cleanup(self) -> None:
        cleanup_sandbox(self.root)


def _excluded_name(name: str) -> bool:
    lowered = name.lower()
    compact = lowered.replace("-", "").replace("_", "")
    return (
        lowered in EXCLUDED
        or lowered.startswith(".env")
        or lowered in SENSITIVE_NAMES
        or "serviceaccount" in compact
        or "firebase-adminsdk" in lowered
        or Path(lowered).suffix in SENSITIVE_SUFFIXES
    )


def _copy_ignore(_directory: str, names: list[str]) -> set[str]:
    return {name for name in names if _excluded_name(name)}


def _contains_link(root: Path) -> bool:
    for path in root.rglob("*"):
        if path.is_symlink():
            return True
        if os.name == "nt":
            attributes = getattr(os.lstat(path), "st_file_attributes", 0)
            if attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                return True
    return False


def prepare_sandbox(project_root: Path) -> Sandbox:
    provider = shutil.which("docker") or shutil.which("podman")
    if not provider:
        raise SandboxUnavailable("sandbox runtime is unavailable")
    root = Path(tempfile.mkdtemp(prefix="assure-sandbox-")).resolve()
    source = project_root.resolve()
    for item in source.iterdir():
        if _excluded_name(item.name):
            continue
        target = root / item.name
        if item.is_symlink():
            cleanup_sandbox(root)
            raise SandboxUnavailable(f"source link is not allowed: {item.name}")
        if item.is_dir():
            shutil.copytree(item, target, ignore=_copy_ignore)
        else:
            shutil.copy2(item, target)
    return Sandbox(root=root, provider=Path(provider).name)


def cleanup_sandbox(root: Path) -> None:
    resolved = root.resolve()
    temp_root = Path(tempfile.gettempdir()).resolve()
    if resolved.parent != temp_root or not resolved.name.startswith("assure-sandbox-"):
        raise AssureError("sandbox cleanup target is not Assure-owned")
    if _contains_link(resolved):
        raise AssureError("sandbox cleanup refused a reparse point")
    shutil.rmtree(resolved)
