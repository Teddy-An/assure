from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

if __package__:
    from .assure_common import sha256_file, write_json
    from .detect_environment import EXCLUDED_DIRECTORIES, detect_environment
else:
    from assure_common import sha256_file, write_json
    from detect_environment import EXCLUDED_DIRECTORIES, detect_environment


CANDIDATE_SUFFIXES = {
    ".go", ".java", ".js", ".jsx", ".kt", ".php", ".py", ".rb",
    ".rs", ".swift", ".ts", ".tsx", ".vue",
}


def load_hashes(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def run_adapter(adapter: Path, project_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    command = [str(adapter), "--project", str(project_root)]
    if adapter.suffix.lower() == ".py":
        command.insert(0, sys.executable)
    try:
        result = subprocess.run(
            command,
            cwd=project_root,
            capture_output=True,
            timeout=15,
        )
    except OSError as exc:
        return [], [{"adapter": adapter.name, "reason": str(exc) or type(exc).__name__}]
    except subprocess.TimeoutExpired:
        return [], [{"adapter": adapter.name, "reason": "timed out after 15 seconds"}]
    try:
        stdout = result.stdout.decode("utf-8")
    except UnicodeDecodeError:
        return [], [{"adapter": adapter.name, "reason": "invalid JSON: adapter output is not UTF-8"}]
    if result.returncode != 0:
        return [], [{
            "adapter": adapter.name,
            "reason": result.stderr.decode("utf-8", errors="replace").strip()
            or f"exit {result.returncode}",
        }]
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        return [], [{"adapter": adapter.name, "reason": f"invalid JSON: {exc}"}]
    if not isinstance(payload, dict):
        return [], [{"adapter": adapter.name, "reason": "invalid JSON: expected object"}]
    items = payload.get("items", [])
    failures = payload.get("failures", [])
    if not isinstance(items, list) or not isinstance(failures, list):
        return [], [{"adapter": adapter.name, "reason": "invalid JSON: items and failures must be arrays"}]
    return items, failures


def collect_inventory(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    assure = root / ".assure"
    cache_path = assure / "cache" / "file-hashes.json"
    previous = load_hashes(cache_path)
    current: dict[str, str] = {}
    candidate_files: list[dict[str, str]] = []

    for directory, names, files in os.walk(root):
        names[:] = sorted(name for name in names if name not in EXCLUDED_DIRECTORIES)
        base = Path(directory)
        for name in sorted(files):
            path = base / name
            if path.suffix.lower() not in CANDIDATE_SUFFIXES:
                continue
            relative = path.relative_to(root).as_posix()
            digest = sha256_file(path)
            current[relative] = digest
            candidate_files.append({"path": relative, "sha256": digest})

    changed = sorted(path for path, digest in current.items() if previous.get(path) != digest)
    unchanged = sorted(path for path, digest in current.items() if previous.get(path) == digest)
    deleted = sorted(path for path in previous if path not in current)

    adapter_items: list[dict[str, Any]] = []
    adapter_failures: list[dict[str, Any]] = []
    adapters_dir = assure / "adapters"
    if adapters_dir.exists():
        for adapter in sorted(path for path in adapters_dir.iterdir() if path.is_file()):
            if adapter.suffix.lower() != ".py" and not os.access(adapter, os.X_OK):
                adapter_failures.append({"adapter": adapter.name, "reason": "not executable"})
                continue
            items, failures = run_adapter(adapter, root)
            adapter_items.extend(items)
            adapter_failures.extend(failures)

    result = {
        "environment": detect_environment(root),
        "candidate_files": candidate_files,
        "changed_files": changed,
        "unchanged_files": unchanged,
        "deleted_files": deleted,
        "adapter_items": adapter_items,
        "adapter_failures": adapter_failures,
    }
    write_json(assure / "discovery-index.json", result)
    write_json(cache_path, current)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True, type=Path)
    args = parser.parse_args()
    result = collect_inventory(args.project)
    print(json.dumps({
        "candidate_count": len(result["candidate_files"]),
        "changed_count": len(result["changed_files"]),
        "unchanged_count": len(result["unchanged_files"]),
        "deleted_count": len(result["deleted_files"]),
        "adapter_failure_count": len(result["adapter_failures"]),
        "index": str(args.project.resolve() / ".assure" / "discovery-index.json"),
    }, ensure_ascii=False))
    return 2 if result["adapter_failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
