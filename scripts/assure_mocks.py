from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class MockInjection:
    injected: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    unverifiable: list[str] = field(default_factory=list)


KNOWN_OUTBOUND = {"firebase", "fetch", "WebSocket", "node:http", "node:https"}
SOURCE_SUFFIXES = {".js", ".jsx", ".py", ".ts", ".tsx"}
OUTBOUND_PATTERNS = {
    "firebase": r"\bfirebase(?:_admin|/|\.)",
    "fetch": r"\bfetch\s*\(",
    "WebSocket": r"\bWebSocket\b",
    "node:http": (
        r"(?:from\s+|require\()\s*['\"](?:node:)?https?['\"]"
    ),
    "direct-socket": r"\b(?:socket|node:net|node:tls)\b",
    "python-http": r"\b(?:requests|httpx|aiohttp|urllib3?)\b",
    "node-http-client": r"\b(?:axios|got|undici)\b",
    "database-client": (
        r"\b(?:sqlalchemy|psycopg|pymongo|redis|mysql|postgres|mongodb|"
        r"google\.cloud|boto3)\b"
    ),
    "rpc-client": r"\b(?:grpc|amqp|kafka|celery)\b",
}
EXCLUDED_SOURCE_DIRECTORIES = {
    ".git", ".next", "build", "coverage", "dist", "node_modules", "vendor",
}
VITEST_CONFIG = ".assure-vitest.config.mjs"


def _project_sources(sandbox_root: Path) -> str:
    chunks: list[str] = []
    for directory, names, filenames in os.walk(sandbox_root):
        names[:] = [
            name for name in names if name not in EXCLUDED_SOURCE_DIRECTORIES
        ]
        base = Path(directory)
        for name in filenames:
            path = base / name
            if path.suffix in SOURCE_SUFFIXES:
                chunks.append(path.read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(chunks)


def _detected_outbound(source: str) -> set[str]:
    return {
        name
        for name, pattern in OUTBOUND_PATTERNS.items()
        if re.search(pattern, source, re.IGNORECASE)
    }


def inject_mocks(sandbox_root: Path, framework: str) -> MockInjection:
    result = MockInjection()
    sources = _project_sources(sandbox_root)
    outbound = _detected_outbound(sources)
    if framework != "vitest":
        if outbound:
            result.unverifiable.append(
                "safe outbound adapter is unavailable for "
                f"{framework}: {', '.join(sorted(outbound))}"
            )
        return result
    unsupported = outbound - KNOWN_OUTBOUND
    if unsupported:
        result.unverifiable.append(
            "safe outbound adapter is unavailable for vitest: "
            + ", ".join(sorted(unsupported))
        )
    if re.search(r"vi\.mock\(['\"]firebase/", sources):
        result.conflicts.append("firebase: user mock preserved")
        firebase_setup = ""
    else:
        result.injected.append("firebase")
        firebase_setup = (
            "vi.mock('firebase/auth', () => {\n"
            "  const user = { uid: 'assure-user', email: 'assure@example.invalid' }\n"
            "  return {\n"
            "    getAuth: vi.fn(() => ({ currentUser: user })),\n"
            "    onAuthStateChanged: vi.fn((_auth, callback) => { callback(user); return () => {} }),\n"
            "    signInWithEmailAndPassword: vi.fn(async () => ({ user })),\n"
            "    signOut: vi.fn(async () => undefined),\n"
            "  }\n"
            "})\n"
            "vi.mock('firebase/firestore', () => ({\n"
            "  getFirestore: vi.fn(() => ({})),\n"
            "  collection: vi.fn((...path) => ({ path })),\n"
            "  doc: vi.fn((...path) => ({ path })),\n"
            "  getDoc: vi.fn(async () => ({ exists: () => false, data: () => undefined })),\n"
            "  getDocs: vi.fn(async () => ({ empty: true, docs: [] })),\n"
            "  setDoc: vi.fn(async () => undefined),\n"
            "  addDoc: vi.fn(async () => ({ id: 'assure-doc' })),\n"
            "  updateDoc: vi.fn(async () => undefined),\n"
            "  deleteDoc: vi.fn(async () => undefined),\n"
            "  onSnapshot: vi.fn((_target, callback) => { callback({ empty: true, docs: [] }); return () => {} }),\n"
            "}))\n"
        )
    result.injected.extend(["fetch", "WebSocket", "node:http", "node:https"])
    setup = sandbox_root / ".assure-auto-mocks.ts"
    setup.write_text(
        "import { vi } from 'vitest'\n"
        + firebase_setup
        + "globalThis.fetch = vi.fn(async () => { throw new Error('Assure blocked network') }) as typeof fetch\n"
        "globalThis.WebSocket = class { constructor() { throw new Error('Assure blocked WebSocket') } } as unknown as typeof WebSocket\n"
        "vi.mock('node:http', async (load) => ({ ...(await load()), request: () => { throw new Error('Assure blocked HTTP') } }))\n"
        "vi.mock('node:https', async (load) => ({ ...(await load()), request: () => { throw new Error('Assure blocked HTTPS') } }))\n",
        encoding="utf-8",
    )
    _write_vitest_config(sandbox_root)
    return result


def _write_vitest_config(sandbox_root: Path) -> None:
    candidates = [
        "vitest.config.ts",
        "vitest.config.mts",
        "vitest.config.js",
        "vitest.config.mjs",
        "vite.config.ts",
        "vite.config.mts",
        "vite.config.js",
        "vite.config.mjs",
    ]
    existing = next(
        (name for name in candidates if (sandbox_root / name).exists()),
        None,
    )
    if existing:
        base_import = f"import baseConfig from {json.dumps(f'./{existing}')}\n"
        export = "export default mergeConfig(baseConfig, assureConfig)\n"
    else:
        base_import = ""
        export = "export default assureConfig\n"
    (sandbox_root / VITEST_CONFIG).write_text(
        "import { defineConfig, mergeConfig } from 'vitest/config'\n"
        + base_import
        + "const assureConfig = defineConfig({ test: { "
        "setupFiles: ['./.assure-auto-mocks.ts'] } })\n"
        + export,
        encoding="utf-8",
    )
