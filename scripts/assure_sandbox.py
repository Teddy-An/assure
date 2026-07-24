from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
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


class PreparationRequired(AssureError):
    def __init__(self, requirements: list[dict[str, object]]):
        super().__init__("user approval is required before preparation")
        self.requirements = requirements


@dataclass(frozen=True)
class BootstrapResult:
    status: str
    detail: str
    network: str = "dependency-download-only"


@dataclass
class Sandbox:
    root: Path
    provider: str
    network: str = ""
    python_executable: str | None = None
    node_executable: str | None = None
    local_guard: str | None = None

    def __post_init__(self) -> None:
        if not self.network:
            self.network = (
                "os-blocked"
                if self.provider != "local-isolated" or self.local_guard
                else "runtime-guarded"
            )

    @property
    def is_container(self) -> bool:
        return self.provider not in {"local-isolated"}

    def _local_env(self, block_network: bool) -> dict[str, str] | None:
        if self.is_container:
            return None
        safe_home = self.root / ".assure-home"
        safe_temp = self.root / ".assure-tmp"
        safe_home.mkdir(exist_ok=True)
        safe_temp.mkdir(exist_ok=True)
        blocked = (
            "AWS_", "AZURE_", "GOOGLE_", "GCLOUD_", "FIREBASE_",
            "GITHUB_TOKEN", "GH_TOKEN", "NPM_TOKEN", "NODE_AUTH_TOKEN",
        )
        env = {
            key: value
            for key, value in os.environ.items()
            if not any(key.upper().startswith(prefix) for prefix in blocked)
        }
        env.update({
            "CI": "1",
            "HOME": str(safe_home),
            "USERPROFILE": str(safe_home),
            "TMPDIR": str(safe_temp),
            "TMP": str(safe_temp),
            "TEMP": str(safe_temp),
        })
        if block_network:
            env.update({
                "HTTP_PROXY": "http://127.0.0.1:9",
                "HTTPS_PROXY": "http://127.0.0.1:9",
                "ALL_PROXY": "http://127.0.0.1:9",
                "NO_PROXY": "",
            })
        return env

    def bootstrap_env(self) -> dict[str, str] | None:
        return self._local_env(block_network=False)

    def execution_env(self) -> dict[str, str] | None:
        return self._local_env(block_network=True)

    def preflight(self, runners: set[str] | None = None) -> None:
        if self.is_container:
            if not runners:
                return
            if runners == {"pytest"}:
                image = "python:3.13"
                probe = [
                    "python",
                    "-c",
                    (
                        "from pathlib import Path; "
                        "p=Path('/workspace/.assure-preflight'); "
                        "p.write_text('ok'); p.unlink()"
                    ),
                ]
            else:
                image = "node:22"
                probe = [
                    "node",
                    "-e",
                    (
                        "const fs=require('fs');"
                        "const p='/workspace/.assure-preflight';"
                        "fs.writeFileSync(p,'ok');fs.unlinkSync(p)"
                    ),
                ]
            try:
                completed = subprocess.run(
                    [
                        self.provider,
                        "run",
                        "--rm",
                        "--network",
                        "none",
                        "--volume",
                        f"{self.root}:/workspace",
                        "--workdir",
                        "/workspace",
                        image,
                        *probe,
                    ],
                    cwd=self.root,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=30,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise SandboxUnavailable(
                    f"container isolation preflight failed: {exc}"
                ) from exc
            if completed.returncode != 0:
                detail = (completed.stderr or completed.stdout).strip()
                raise SandboxUnavailable(
                    "container isolation preflight failed before scenario "
                    f"execution: {detail[-1000:] or completed.returncode}"
                )
            return
        if not self.local_guard:
            raise SandboxUnavailable(
                "local OS filesystem and network isolation is unavailable"
            )
        outside = self.root.parent / f"{self.root.name}-preflight-outside"
        source = (
            "import os, socket, sys, tempfile\n"
            "root = os.path.realpath(sys.argv[1])\n"
            "outside = sys.argv[2]\n"
            "handle, temporary = tempfile.mkstemp(prefix='assure-preflight-')\n"
            "os.write(handle, b'ok')\n"
            "os.close(handle)\n"
            "if os.path.commonpath([root, os.path.realpath(temporary)]) != root:\n"
            "    raise SystemExit('temporary path escaped sandbox')\n"
            "os.unlink(temporary)\n"
            "try:\n"
            "    open(outside, 'w', encoding='utf-8').write('unsafe')\n"
            "except OSError:\n"
            "    pass\n"
            "else:\n"
            "    os.unlink(outside)\n"
            "    raise SystemExit('outside write was not blocked')\n"
            "network = socket.socket()\n"
            "try:\n"
            "    network.bind(('127.0.0.1', 0))\n"
            "except OSError:\n"
            "    pass\n"
            "else:\n"
            "    network.close()\n"
            "    raise SystemExit('network bind was not blocked')\n"
            "network.close()\n"
        )
        try:
            completed = subprocess.run(
                [
                    self.local_guard,
                    "-f",
                    str(self.root / ".assure-sandbox.sb"),
                    sys.executable,
                    "-c",
                    source,
                    str(self.root),
                    str(outside),
                ],
                cwd=self.root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=15,
                env=self.execution_env(),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise SandboxUnavailable(f"isolation preflight failed: {exc}") from exc
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout).strip()
            raise SandboxUnavailable(
                "isolation preflight failed before scenario execution: "
                f"{detail[-1000:] or f'exit code {completed.returncode}'}"
            )

    def required_preparations(
        self,
        runners: set[str],
        approved: set[str],
    ) -> list[dict[str, object]]:
        if "dependency-download" in approved:
            return []
        if self.is_container or runners & {"vitest", "jest"}:
            node_runners = sorted(runners & {"vitest", "jest"})
            if node_runners:
                stack = ["Node.js"]
                package_json = self.root / "package.json"
                if package_json.exists():
                    try:
                        package = json.loads(
                            package_json.read_text(encoding="utf-8")
                        )
                    except (OSError, json.JSONDecodeError):
                        package = {}
                    runtime_dependencies = package.get("dependencies", {})
                    development_dependencies = package.get(
                        "devDependencies",
                        {},
                    )
                    dependencies = {
                        **(
                            runtime_dependencies
                            if isinstance(runtime_dependencies, dict)
                            else {}
                        ),
                        **(
                            development_dependencies
                            if isinstance(development_dependencies, dict)
                            else {}
                        ),
                    }
                    frameworks = (
                        ("react", "React"),
                        ("vue", "Vue"),
                        ("@angular/core", "Angular"),
                        ("svelte", "Svelte"),
                    )
                    stack.extend(
                        label
                        for package_name, label in frameworks
                        if package_name in dependencies
                    )
                command = (
                    "npm ci --ignore-scripts --no-bin-links "
                    "--no-audit --no-fund"
                )
                evidence = "package-lock.json"
                reason = (
                    f"{', '.join(node_runners)} executes the project's "
                    "JavaScript/TypeScript tests and its locked packages are "
                    "not copied from the original node_modules directory"
                )
                affected_runners = node_runners
            else:
                stack = ["Python"]
                command = (
                    "python -m pip install --only-binary=:all: "
                    "--require-hashes -r requirements.txt"
                )
                evidence = "requirements.txt"
                reason = (
                    "pytest executes the project's Python tests inside the "
                    "isolated container"
                )
                affected_runners = sorted(runners)
            return [{
                "id": "dependency-download",
                "stack": stack,
                "runners": affected_runners,
                "provider": self.provider,
                "evidence": evidence,
                "command": command,
                "reason": reason,
                "action": (
                    "download and install locked test dependencies in an "
                    "Assure-owned temporary copy"
                ),
                "impact": (
                    "network is enabled only during dependency preparation; "
                    "the original project and production services are not modified"
                ),
            }]
        return []

    def bootstrap(self, runners: set[str]) -> BootstrapResult:
        if not self.is_container:
            return self._bootstrap_local(runners)
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

    def _bootstrap_local(self, runners: set[str]) -> BootstrapResult:
        if runners & {"vitest", "jest"}:
            if not (self.root / "package-lock.json").exists():
                return BootstrapResult(
                    "unavailable",
                    "package-lock.json is required for isolated Node dependency bootstrap",
                )
            npm = shutil.which("npm")
            node = shutil.which("node")
            if not npm or not node:
                return BootstrapResult(
                    "unavailable",
                    "Node.js and npm are required for local isolated Node verification",
                )
            self.node_executable = node
            command = [
                npm,
                "ci",
                "--ignore-scripts",
                "--no-bin-links",
                "--no-audit",
                "--no-fund",
                "--cache",
                str(self.root / ".assure-npm-cache"),
            ]
            result = _run_bootstrap(command, self.root, self.bootstrap_env())
            if result is not None:
                return result
        if "pytest" in runners:
            try:
                probe = subprocess.run(
                    [sys.executable, "-m", "pytest", "--version"],
                    cwd=self.root,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=15,
                    env=self.execution_env(),
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                return BootstrapResult("failed", str(exc))
            if probe.returncode != 0:
                return BootstrapResult(
                    "unavailable",
                    "pytest is required for local isolated Python verification",
                )
            self.python_executable = sys.executable
        return BootstrapResult(
            "ready",
            "dependencies prepared in an Assure-owned temporary copy",
        )

    def wrap(self, argv: list[str], runner: str) -> list[str]:
        if not self.is_container:
            if runner == "pytest":
                command = [
                    self.python_executable or sys.executable,
                    "-m",
                    "pytest",
                    *argv[3:],
                ]
            else:
                node = self.node_executable or shutil.which("node")
                if not node:
                    raise AssureError("Node.js is unavailable after bootstrap")
                package = (
                    "vitest/vitest.mjs"
                    if runner == "vitest"
                    else "jest/bin/jest.js"
                )
                command = [
                    node,
                    str(self.root / "node_modules" / package),
                    *argv[3:],
                ]
                if runner == "vitest":
                    command.append("--config=.assure-vitest.config.mjs")
            if not self.local_guard:
                raise SandboxUnavailable(
                    "local OS filesystem and network isolation is unavailable"
                )
            return [
                self.local_guard,
                "-f",
                str(self.root / ".assure-sandbox.sb"),
                *command,
            ]
        image = "python:3.13" if runner == "pytest" else "node:22"
        if runner == "pytest":
            container_argv = ["python", "-m", "pytest", *argv[3:]]
        elif runner == "vitest":
            container_argv = [
                "node",
                "node_modules/vitest/vitest.mjs",
                *argv[3:],
            ]
            container_argv.append("--config=.assure-vitest.config.mjs")
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
    if root.is_symlink():
        return True
    for path in root.rglob("*"):
        if path.is_symlink():
            return True
        if os.name == "nt":
            attributes = getattr(os.lstat(path), "st_file_attributes", 0)
            if attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                return True
    return False


def _unsafe_source_link(root: Path) -> Path | None:
    for directory, names, filenames in os.walk(root, followlinks=False):
        base = Path(directory)
        kept_names: list[str] = []
        for name in names:
            if _excluded_name(name):
                continue
            path = base / name
            if path.is_symlink():
                return path
            if os.name == "nt":
                attributes = getattr(os.lstat(path), "st_file_attributes", 0)
                if attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                    return path
            kept_names.append(name)
        names[:] = kept_names
        for name in filenames:
            if _excluded_name(name):
                continue
            path = base / name
            if path.is_symlink():
                return path
            if os.name == "nt":
                attributes = getattr(os.lstat(path), "st_file_attributes", 0)
                if attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                    return path
    return None


def _write_macos_profile(root: Path, source: Path) -> None:
    profile = (
        "(version 1)\n"
        "(allow default)\n"
        "(deny network*)\n"
        "(deny file-read* (subpath \"/Users\"))\n"
        "(deny file-read* (subpath \"/Volumes\"))\n"
        "(deny file-read* (subpath \"/Network\"))\n"
        f"(deny file-read* (subpath {json.dumps(str(source))}))\n"
        f"(allow file-read* (subpath {json.dumps(str(root))}))\n"
        "(deny file-write*)\n"
        f"(allow file-write* (subpath {json.dumps(str(root))}))\n"
        "(allow file-write* (literal \"/dev/null\"))\n"
    )
    (root / ".assure-sandbox.sb").write_text(profile, encoding="utf-8")


def _copy_functional_probes(source: Path, sandbox_root: Path) -> None:
    probes = source / ".assure" / "probes"
    if not probes.exists():
        return
    if not probes.is_dir() or _contains_link(probes):
        raise SandboxUnavailable(
            "Assure functional probes must be a link-free directory"
        )
    target = sandbox_root / ".assure" / "probes"
    target.parent.mkdir()
    shutil.copytree(probes, target, ignore=_copy_ignore)


def _run_bootstrap(
    command: list[str],
    root: Path,
    env: dict[str, str] | None = None,
) -> BootstrapResult | None:
    try:
        completed = subprocess.run(
            command,
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return BootstrapResult("failed", str(exc))
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        return BootstrapResult(
            "failed",
            detail[-2000:] or "dependency bootstrap failed",
        )
    return None


def _runtime_ready(executable: str) -> bool:
    try:
        completed = subprocess.run(
            [executable, "info"],
            capture_output=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0


def prepare_sandbox(project_root: Path) -> Sandbox:
    provider = None
    for name in ("docker", "podman"):
        candidate = shutil.which(name)
        if candidate and _runtime_ready(candidate):
            provider = Path(candidate).name
            break
    local_guard = None
    if provider is None and sys.platform == "darwin":
        local_guard = shutil.which("sandbox-exec")
    if provider is None and not local_guard:
        raise SandboxUnavailable(
            "Docker, Podman, or a supported local OS isolation provider is required"
        )
    source = project_root.resolve()
    unsafe_link = _unsafe_source_link(source)
    if unsafe_link is not None:
        relative = unsafe_link.relative_to(source).as_posix()
        raise SandboxUnavailable(f"source link is not allowed: {relative}")
    root = Path(tempfile.mkdtemp(prefix="assure-sandbox-")).resolve()
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
    try:
        _copy_functional_probes(source, root)
        if local_guard:
            _write_macos_profile(root, source)
    except BaseException:
        cleanup_sandbox(root)
        raise
    return Sandbox(
        root=root,
        provider=provider or "local-isolated",
        local_guard=local_guard,
    )


def cleanup_sandbox(root: Path) -> None:
    resolved = root.resolve()
    temp_root = Path(tempfile.gettempdir()).resolve()
    if resolved.parent != temp_root or not resolved.name.startswith("assure-sandbox-"):
        raise AssureError("sandbox cleanup target is not Assure-owned")
    if _contains_link(resolved):
        raise AssureError("sandbox cleanup refused a reparse point")
    shutil.rmtree(resolved)
