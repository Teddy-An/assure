from __future__ import annotations

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
EXCLUDED_SOURCE_DIRECTORIES = {
    ".git", ".next", "build", "coverage", "dist", "node_modules", "vendor",
}


def _project_sources(sandbox_root: Path) -> str:
    chunks: list[str] = []
    for directory, names, filenames in os.walk(sandbox_root):
        names[:] = [
            name for name in names if name not in EXCLUDED_SOURCE_DIRECTORIES
        ]
        base = Path(directory)
        for name in filenames:
            path = base / name
            if path.suffix in {".ts", ".tsx", ".js", ".jsx"}:
                chunks.append(path.read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(chunks)


def inject_mocks(sandbox_root: Path, framework: str) -> MockInjection:
    result = MockInjection()
    sources = _project_sources(sandbox_root)
    if framework != "vitest":
        if re.search(r"firebase|fetch\s*\(|WebSocket|node:(?:http|https)", sources):
            result.unverifiable.append(
                f"automatic outbound mocks are unavailable for {framework}"
            )
        return result
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
    return result
