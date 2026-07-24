from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

if __package__:
    from .assure_common import candidate_source_files, sha256_file, source_snapshot, write_json
    from .detect_environment import detect_environment
    from .assure_output import emit_json
else:
    from assure_common import candidate_source_files, sha256_file, source_snapshot, write_json
    from detect_environment import detect_environment
    from assure_output import emit_json


def load_hashes(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def collect_inventory(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    assure = root / ".assure"
    cache_path = assure / "cache" / "file-hashes.json"
    previous = load_hashes(cache_path)
    current: dict[str, str] = {}
    candidate_files: list[dict[str, str]] = []

    for path in candidate_source_files(root):
        relative = path.relative_to(root).as_posix()
        digest = sha256_file(path)
        current[relative] = digest
        candidate_files.append({"path": relative, "sha256": digest})

    changed = sorted(path for path, digest in current.items() if previous.get(path) != digest)
    unchanged = sorted(path for path, digest in current.items() if previous.get(path) == digest)
    deleted = sorted(path for path in previous if path not in current)

    adapter_failures: list[dict[str, Any]] = []
    adapters_dir = assure / "adapters"
    if adapters_dir.exists():
        for adapter in sorted(path for path in adapters_dir.iterdir() if path.is_file()):
            adapter_failures.append({
                "adapter": adapter.name,
                "reason": (
                    "project-provided discovery adapters are disabled; "
                    "Assure executes only built-in collectors"
                ),
            })

    result = {
        "environment": detect_environment(root),
        "source_snapshot": source_snapshot(root),
        "candidate_files": candidate_files,
        "changed_files": changed,
        "unchanged_files": unchanged,
        "deleted_files": deleted,
        "adapter_items": [],
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
    emit_json({
        "candidate_count": len(result["candidate_files"]),
        "changed_count": len(result["changed_files"]),
        "unchanged_count": len(result["unchanged_files"]),
        "deleted_count": len(result["deleted_files"]),
        "adapter_failure_count": len(result["adapter_failures"]),
        "index": str(args.project.resolve() / ".assure" / "discovery-index.json"),
    })
    return 2 if result["adapter_failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
