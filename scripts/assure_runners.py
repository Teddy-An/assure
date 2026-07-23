from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

if __package__:
    from .assure_common import AssureError
else:
    from assure_common import AssureError


@dataclass(frozen=True)
class RunnerCommand:
    executable: str
    args: list[str]

    def argv(self) -> list[str]:
        return [self.executable, *self.args]


def _validated_args(value: Any) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(arg, str) for arg in value):
        raise AssureError("runner args must be a string array")
    if any("\0" in arg for arg in value):
        raise AssureError("runner args contain a NUL byte")
    return list(value)


def build_runner_command(entry: dict[str, Any], project_root: Path) -> RunnerCommand:
    del project_root
    runner = entry.get("runner")
    args = _validated_args(entry.get("args", []))
    if runner == "pytest":
        return RunnerCommand(sys.executable, ["-m", "pytest", *args])
    if runner in {"vitest", "jest"}:
        executable = "npx.cmd" if os.name == "nt" else "npx"
        return RunnerCommand(executable, ["--no-install", runner, *args])
    raise AssureError(f"unsupported automated test runner: {runner}")
