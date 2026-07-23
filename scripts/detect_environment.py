from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


EXCLUDED_DIRECTORIES = [
    ".git",
    ".next",
    ".assure",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "target",
    "vendor",
]

TOML_SECTION_HEADER = re.compile(
    r"^\s*\[([A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*)\]\s*(?:#.*)?$"
)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def toml_section_name(line: str) -> str | None:
    match = TOML_SECTION_HEADER.match(line)
    return match.group(1) if match else None


def toml_section_text(text: str, section: str) -> str:
    lines: list[str] = []
    in_section = False
    for line in text.splitlines():
        name = toml_section_name(line)
        if name is not None:
            in_section = name == section
            continue
        if in_section:
            lines.append(line)
    return "\n".join(lines)


def has_toml_section(text: str, section: str) -> bool:
    prefix = f"{section}."
    for line in text.splitlines():
        name = toml_section_name(line)
        if name == section or (name is not None and name.startswith(prefix)):
            return True
    return False


def project_dependencies_text(text: str) -> str:
    match = re.search(
        r"(?ms)^\s*dependencies\s*=\s*\[(.*?)\]",
        toml_section_text(text, "project"),
    )
    return match.group(1).lower() if match else ""


def detect_environment(project_root: Path) -> dict[str, list[str]]:
    languages: set[str] = set()
    frameworks: set[str] = set()
    test_runners: set[str] = set()
    metadata: list[str] = []

    package_json = project_root / "package.json"
    if package_json.exists():
        package = read_json(package_json)
        metadata.append("package.json")
        deps = {
            **package.get("dependencies", {}),
            **package.get("devDependencies", {}),
        }
        if "typescript" in deps:
            languages.add("typescript")
        else:
            languages.add("javascript")
        framework_keys = {
            "next": "nextjs",
            "@nestjs/core": "nestjs",
            "express": "express",
            "react": "react",
        }
        runner_keys = {
            "jest": "jest",
            "vitest": "vitest",
            "@playwright/test": "playwright",
            "cypress": "cypress",
        }
        for key, name in framework_keys.items():
            if key in deps:
                frameworks.add(name)
        for key, name in runner_keys.items():
            if key in deps:
                test_runners.add(name)

    pyproject = project_root / "pyproject.toml"
    if pyproject.exists():
        pyproject_text = pyproject.read_text(encoding="utf-8")
        metadata.append("pyproject.toml")
        languages.add("python")
        if has_toml_section(pyproject_text, "tool.pytest"):
            test_runners.add("pytest")
        dependencies = project_dependencies_text(pyproject_text)
        if "fastapi" in dependencies:
            frameworks.add("fastapi")
        if "django" in dependencies:
            frameworks.add("django")

    return {
        "languages": sorted(languages),
        "frameworks": sorted(frameworks),
        "test_runners": sorted(test_runners),
        "metadata_files": sorted(metadata),
        "excluded_directories": EXCLUDED_DIRECTORIES,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(detect_environment(args.project), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
