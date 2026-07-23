from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

class AssureError(RuntimeError):
    pass


def run_text(
    command: list[str],
    cwd: Path,
    timeout_seconds: float = 15,
) -> str:
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise AssureError(
            f"command timed out after {timeout_seconds} seconds"
        ) from exc
    if result.returncode != 0:
        raise AssureError(result.stderr.strip() or "command failed")
    return result.stdout.strip()


def git_head(project_root: Path) -> str:
    return run_text(["git", "rev-parse", "HEAD"], project_root)


def source_changed_since(project_root: Path, baseline_commit: str) -> bool:
    try:
        committed = subprocess.run(
            [
                "git", "diff", "--quiet", baseline_commit, "HEAD", "--", ".",
                ":(exclude).assure",
            ],
            cwd=project_root,
            timeout=15,
        )
        working = subprocess.run(
            [
                "git", "status", "--porcelain=v1", "-z",
                "--untracked-files=all", "--", ".",
            ],
            cwd=project_root,
            capture_output=True,
            timeout=15,
        )
    except subprocess.TimeoutExpired as exc:
        raise AssureError("Git command timed out after 15 seconds") from exc
    if committed.returncode not in {0, 1}:
        raise AssureError("baseline commit cannot be compared")
    if working.returncode != 0:
        detail = working.stderr.decode(errors="replace").strip()
        raise AssureError(detail or "working tree cannot be inspected")
    records = iter(working.stdout.split(b"\0"))
    for record in records:
        if not record:
            continue
        if len(record) < 3:
            raise AssureError("working tree status cannot be parsed")
        paths = [record[3:]]
        if b"R" in record[:2] or b"C" in record[:2]:
            try:
                paths.append(next(records))
            except StopIteration as exc:
                raise AssureError("working tree status cannot be parsed") from exc
        if not all(path.startswith(b".assure/") for path in paths):
            return True
    return committed.returncode == 1


def load_manifest(path: Path) -> dict[str, Any]:
    import yaml

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise AssureError(f"cannot read manifest: {exc}") from exc
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise AssureError("unsupported or damaged manifest")
    if not isinstance(data.get("baseline"), dict):
        raise AssureError("manifest baseline is missing")
    if not isinstance(data.get("sections"), list):
        raise AssureError("manifest sections must be a list")
    return data


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()
