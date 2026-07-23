from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

if __package__:
    from .assure_common import AssureError, load_manifest, source_changed_since
else:
    from assure_common import AssureError, load_manifest, source_changed_since


@dataclass(frozen=True)
class ProjectState:
    kind: str
    project_root: str
    assure_dir: str
    manifest_path: str
    reason: str


def classify_project(project_root: Path) -> ProjectState:
    root = project_root.resolve()
    assure_dir = root / ".assure"
    manifest_path = assure_dir / "verification-manifest.yaml"
    adapters_dir = assure_dir / "adapters"
    base = {
        "project_root": str(root),
        "assure_dir": str(assure_dir),
        "manifest_path": str(manifest_path),
    }
    if not assure_dir.exists():
        return ProjectState("absent", **base, reason="no .assure directory")
    if not manifest_path.exists():
        reason = "collector exists without manifest" if adapters_dir.exists() else "manifest missing"
        return ProjectState("incomplete", **base, reason=reason)
    try:
        manifest = load_manifest(manifest_path)
    except AssureError as exc:
        return ProjectState("damaged", **base, reason=str(exc))
    status = manifest["baseline"].get("status")
    if status in {"draft", "review"}:
        return ProjectState(status, **base, reason=f"baseline status is {status}")
    if status != "approved":
        return ProjectState("damaged", **base, reason=f"unknown baseline status: {status}")
    baseline_commit = manifest["baseline"].get("commit")
    if not isinstance(baseline_commit, str) or not baseline_commit:
        return ProjectState("damaged", **base, reason="approved baseline commit is missing")
    try:
        changed = source_changed_since(root, baseline_commit)
    except AssureError as exc:
        return ProjectState("damaged", **base, reason=f"git state unavailable: {exc}")
    if not changed:
        return ProjectState(
            "approved-current",
            **base,
            reason="no product-source changes since baseline",
        )
    return ProjectState(
        "approved-stale",
        **base,
        reason=f"product source changed since {baseline_commit}",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(asdict(classify_project(args.project)), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
