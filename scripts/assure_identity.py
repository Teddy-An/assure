from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

if __package__:
    from .assure_output import emit_json
else:
    from assure_output import emit_json


ASSURE_VERSION = "0.2.0-dev"
PROBE_SCHEMA_VERSION = 2
GENERATOR_CONTRACT = "assure-llm-probe-v2"
VERIFICATION_POLICY = "assure-generated-probes-v2"
IDENTITY_PREFIX = "ASSURE_GENERATED:"


def plugin_root() -> Path:
    return Path(__file__).resolve().parent.parent


def distribution_sha256(root: Path | None = None) -> str:
    base = (root or plugin_root()).resolve()
    candidates = [
        base / "AGENTS.md",
        base / "CLAUDE.md",
        *sorted((base / "scripts").glob("*.py")),
        *sorted((base / "skills").glob("**/*.md")),
    ]
    digest = hashlib.sha256()
    for path in candidates:
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(base).as_posix().encode("utf-8")
        content = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def current_identity(root: Path | None = None) -> dict[str, Any]:
    return {
        "assure_version": ASSURE_VERSION,
        "distribution_sha256": distribution_sha256(root),
        "probe_schema": PROBE_SCHEMA_VERSION,
        "generator_contract": GENERATOR_CONTRACT,
        "verification_policy": VERIFICATION_POLICY,
    }


def generation_marker(comment: str = "//", root: Path | None = None) -> str:
    identity = current_identity(root)
    return (
        f"{comment} {IDENTITY_PREFIX} "
        f"version={identity['assure_version']} "
        f"distribution_sha256={identity['distribution_sha256']} "
        f"probe_schema={identity['probe_schema']} "
        f"generator_contract={identity['generator_contract']}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--comment",
        choices=["//", "#"],
        help="also return the exact generated-test marker for this comment style",
    )
    args = parser.parse_args()
    result = current_identity()
    if args.comment:
        result["generation_marker"] = generation_marker(args.comment)
    emit_json(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
