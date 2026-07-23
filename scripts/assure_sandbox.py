from __future__ import annotations

import os
import shutil
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path

if __package__:
    from .assure_common import AssureError
else:
    from assure_common import AssureError


EXCLUDED = {
    ".assure", ".env", ".git", ".next", "build", "coverage", "dist",
    "node_modules", "target", "vendor",
}


class SandboxUnavailable(AssureError):
    pass


@dataclass
class Sandbox:
    root: Path
    provider: str
    network: str = "disabled"

    def wrap(self, argv: list[str], runner: str) -> list[str]:
        image = "python:3.13" if runner == "pytest" else "node:22"
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
            *argv,
        ]

    def cleanup(self) -> None:
        cleanup_sandbox(self.root)


def _contains_link(root: Path) -> bool:
    return any(path.is_symlink() or bool(path.stat(follow_symlinks=False).st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
               if os.name == "nt" else path.is_symlink()
               for path in root.rglob("*"))


def prepare_sandbox(project_root: Path) -> Sandbox:
    provider = shutil.which("docker") or shutil.which("podman")
    if not provider:
        raise SandboxUnavailable("sandbox runtime is unavailable")
    root = Path(tempfile.mkdtemp(prefix="assure-sandbox-")).resolve()
    source = project_root.resolve()
    for item in source.iterdir():
        if item.name in EXCLUDED or item.name.startswith(".env"):
            continue
        target = root / item.name
        if item.is_symlink():
            cleanup_sandbox(root)
            raise SandboxUnavailable(f"source link is not allowed: {item.name}")
        if item.is_dir():
            shutil.copytree(item, target, ignore=shutil.ignore_patterns(*EXCLUDED))
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
