from __future__ import annotations

import json
import hashlib
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

if __package__:
    from .assure_probe_compatibility import probe_compatibility
else:
    from assure_probe_compatibility import probe_compatibility


@dataclass
class MockInjection:
    injected: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    unverifiable: list[str] = field(default_factory=list)
    pytest_plugins: list[str] = field(default_factory=list)


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


def _generated_adapters(
    sandbox_root: Path,
    framework: str,
) -> tuple[set[str], list[str], list[str]]:
    registry = sandbox_root / ".assure" / "adapters" / "registry.json"
    if not registry.is_file() or registry.is_symlink():
        return set(), [], []
    try:
        data = json.loads(registry.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return set(), [], [f"generated adapter registry is invalid: {exc}"]
    boundaries: set[str] = set()
    setups: list[str] = []
    errors: list[str] = []
    for item in data.get("adapters", []):
        if not isinstance(item, dict) or item.get("runner") != framework:
            continue
        relative = item.get("setup")
        expected = item.get("sha256")
        if not isinstance(relative, str) or not relative.startswith(
            ".assure/adapters/"
        ):
            errors.append("generated adapter setup path is invalid")
            continue
        path = sandbox_root / relative
        try:
            path.resolve().relative_to(
                (sandbox_root / ".assure/adapters").resolve()
            )
        except (OSError, ValueError):
            errors.append("generated adapter escapes its owned directory")
            continue
        if not path.is_file() or path.is_symlink():
            errors.append(f"generated adapter is missing: {relative}")
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if not isinstance(expected, str) or actual != expected:
            errors.append(f"generated adapter hash mismatch: {relative}")
            continue
        compatibility = probe_compatibility(path)
        if not compatibility["compatible"]:
            errors.append(
                f"generated adapter identity mismatch: {relative}: "
                f"{compatibility['reason']}"
            )
            continue
        declared = item.get("boundaries", [])
        if not isinstance(declared, list) or not all(
            isinstance(value, str) and value in OUTBOUND_PATTERNS
            for value in declared
        ):
            errors.append(f"generated adapter boundaries are invalid: {relative}")
            continue
        boundaries.update(declared)
        setups.append(relative)
    return boundaries, setups, errors


def inject_mocks(sandbox_root: Path, framework: str) -> MockInjection:
    result = MockInjection()
    sources = _project_sources(sandbox_root)
    outbound = _detected_outbound(sources)
    generated_boundaries, generated_setups, generated_errors = (
        _generated_adapters(sandbox_root, framework)
    )
    result.unverifiable.extend(generated_errors)
    outbound -= generated_boundaries
    if framework != "vitest":
        if outbound:
            result.unverifiable.append(
                "safe outbound adapter is unavailable for "
                f"{framework}: {', '.join(sorted(outbound))}"
            )
        if framework == "pytest":
            for index, setup in enumerate(generated_setups):
                source = sandbox_root / setup
                module = f"_assure_generated_pytest_adapter_{index}"
                target = sandbox_root / f"{module}.py"
                target.write_bytes(source.read_bytes())
                result.pytest_plugins.append(module)
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
            "const assureFirestore = vi.hoisted(() => ({\n"
            "  docs: new Map<string, Record<string, unknown>>(),\n"
            "  effects: [] as Array<Record<string, unknown>>,\n"
            "  nextId: 1,\n"
            "}))\n"
            "const assurePath = (parent: unknown, segments: string[]) => {\n"
            "  const base = parent && typeof parent === 'object' && 'path' in parent\n"
            "    ? String((parent as { path: unknown }).path) : ''\n"
            "  return [base, ...segments].filter(Boolean).join('/')\n"
            "}\n"
            "const assureSnapshot = (path: string, data: Record<string, unknown>) => ({\n"
            "  id: path.split('/').at(-1), ref: { path }, exists: () => true,\n"
            "  data: () => structuredClone(data),\n"
            "})\n"
            "Object.assign(globalThis, { __ASSURE_FIRESTORE__: {\n"
            "  contract: 'ASSURE_STATEFUL_FIRESTORE_V1',\n"
            "  reset: () => { assureFirestore.docs.clear(); assureFirestore.effects.length = 0; assureFirestore.nextId = 1 },\n"
            "  seed: (path: string, data: Record<string, unknown>) => assureFirestore.docs.set(path, structuredClone(data)),\n"
            "  effects: assureFirestore.effects,\n"
            "  snapshot: () => new Map(assureFirestore.docs),\n"
            "} })\n"
            "vi.mock('firebase/firestore', () => {\n"
            "  const collection = (parent: unknown, ...segments: string[]) => ({ path: assurePath(parent, segments), kind: 'collection' })\n"
            "  const doc = (parent: unknown, ...segments: string[]) => ({ path: assurePath(parent, segments), kind: 'doc' })\n"
            "  const where = (field: string, op: string, value: unknown) => ({ kind: 'where', field, op, value })\n"
            "  const orderBy = (field: string, direction = 'asc') => ({ kind: 'orderBy', field, direction })\n"
            "  const query = (ref: { path: string }, ...constraints: unknown[]) => ({ ...ref, constraints })\n"
            "  const rows = (ref: { path: string, constraints?: Array<Record<string, unknown>> }) => {\n"
            "    const prefix = `${ref.path}/`\n"
            "    let values = [...assureFirestore.docs.entries()].filter(([path]) => path.startsWith(prefix) && !path.slice(prefix.length).includes('/'))\n"
            "    for (const constraint of ref.constraints ?? []) {\n"
            "      if (constraint.kind === 'where' && constraint.op === '==') values = values.filter(([, data]) => data[String(constraint.field)] === constraint.value)\n"
            "      if (constraint.kind === 'orderBy') values.sort((a, b) => String(a[1][String(constraint.field)] ?? '').localeCompare(String(b[1][String(constraint.field)] ?? '')) * (constraint.direction === 'desc' ? -1 : 1))\n"
            "    }\n"
            "    return values.map(([path, data]) => assureSnapshot(path, data))\n"
            "  }\n"
            "  const materialize = (current: Record<string, unknown>, payload: Record<string, unknown>) => Object.fromEntries(Object.entries(payload).map(([key, value]) => {\n"
            "    if (value && typeof value === 'object' && (value as { __op?: string }).__op === 'arrayUnion') return [key, [...new Set([...(Array.isArray(current[key]) ? current[key] as unknown[] : []), ...((value as { values: unknown[] }).values)])]]\n"
            "    if (value && typeof value === 'object' && (value as { __op?: string }).__op === 'increment') return [key, Number(current[key] ?? 0) + Number((value as { value: unknown }).value)]\n"
            "    if (value && typeof value === 'object' && (value as { __op?: string }).__op === 'serverTimestamp') return [key, new Date(0)]\n"
            "    return [key, structuredClone(value)]\n"
            "  }))\n"
            "  const record = (target: string, operation: string, payload: unknown) => assureFirestore.effects.push({ target, operation, payload: structuredClone(payload), count: 1, blocked: false })\n"
            "  const setDoc = vi.fn(async (ref: { path: string }, payload: Record<string, unknown>, options?: { merge?: boolean }) => { const current = options?.merge ? (assureFirestore.docs.get(ref.path) ?? {}) : {}; assureFirestore.docs.set(ref.path, { ...current, ...materialize(current, payload) }); record(ref.path, 'set', payload) })\n"
            "  const addDoc = vi.fn(async (ref: { path: string }, payload: Record<string, unknown>) => { const id = `assure-${assureFirestore.nextId++}`; const path = `${ref.path}/${id}`; assureFirestore.docs.set(path, structuredClone(payload)); record(ref.path, 'create', payload); return { id, path } })\n"
            "  const updateDoc = vi.fn(async (ref: { path: string }, payload: Record<string, unknown>) => { const current = assureFirestore.docs.get(ref.path) ?? {}; assureFirestore.docs.set(ref.path, { ...current, ...materialize(current, payload) }); record(ref.path, 'update', payload) })\n"
            "  const deleteDoc = vi.fn(async (ref: { path: string }) => { assureFirestore.docs.delete(ref.path); record(ref.path, 'delete', null) })\n"
            "  const getDoc = vi.fn(async (ref: { path: string }) => { const data = assureFirestore.docs.get(ref.path); return data ? assureSnapshot(ref.path, data) : { id: ref.path.split('/').at(-1), ref, exists: () => false, data: () => undefined } })\n"
            "  const getDocs = vi.fn(async (ref: { path: string }) => { const docs = rows(ref); return { empty: docs.length === 0, docs, size: docs.length } })\n"
            "  const onSnapshot = vi.fn((target: { path: string }, callback: (value: unknown) => void) => { const docs = rows(target); callback({ empty: docs.length === 0, docs, size: docs.length }); return () => {} })\n"
            "  const arrayUnion = (...values: unknown[]) => ({ __op: 'arrayUnion', values })\n"
            "  const increment = (value: number) => ({ __op: 'increment', value })\n"
            "  const serverTimestamp = () => ({ __op: 'serverTimestamp' })\n"
            "  return { getFirestore: vi.fn(() => ({ kind: 'assure-firestore' })), collection, doc, query, where, orderBy, arrayUnion, increment, serverTimestamp, getDoc, getDocs, setDoc, addDoc, updateDoc, deleteDoc, onSnapshot }\n"
            "})\n"
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
    _write_vitest_config(sandbox_root, generated_setups)
    return result


def _write_vitest_config(
    sandbox_root: Path,
    generated_setups: list[str] | None = None,
) -> None:
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
        + "const assureConfig = defineConfig({ test: { setupFiles: "
        + json.dumps([
            "./.assure-auto-mocks.ts",
            *(f"./{path}" for path in (generated_setups or [])),
        ])
        + " } })\n"
        + export,
        encoding="utf-8",
    )
