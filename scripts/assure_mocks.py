from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class MockInjection:
    injected: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    unverifiable: list[str] = field(default_factory=list)


KNOWN_OUTBOUND = {"firebase", "fetch", "WebSocket", "node:http", "node:https"}


def inject_mocks(sandbox_root: Path, framework: str) -> MockInjection:
    result = MockInjection()
    if framework != "vitest":
        result.unverifiable.append(f"unsupported test framework: {framework}")
        return result
    sources = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in sandbox_root.rglob("*")
        if path.suffix in {".ts", ".tsx", ".js", ".jsx"}
    )
    if re.search(r"vi\.mock\(['\"]firebase/", sources):
        result.conflicts.append("firebase: user mock preserved")
    else:
        result.injected.append("firebase")
    result.injected.extend(["fetch", "WebSocket", "node:http", "node:https"])
    setup = sandbox_root / ".assure-auto-mocks.ts"
    setup.write_text(
        "import { vi } from 'vitest'\n"
        "globalThis.fetch = vi.fn(async () => { throw new Error('Assure blocked network') }) as typeof fetch\n"
        "globalThis.WebSocket = class { constructor() { throw new Error('Assure blocked WebSocket') } } as unknown as typeof WebSocket\n"
        "vi.mock('node:http', () => ({ request: () => { throw new Error('Assure blocked HTTP') } }))\n"
        "vi.mock('node:https', () => ({ request: () => { throw new Error('Assure blocked HTTPS') } }))\n",
        encoding="utf-8",
    )
    return result
