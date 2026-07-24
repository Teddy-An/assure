import hashlib
import json
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.assure_common import AssureError
from scripts.assure_identity import generation_marker
from scripts.assure_mocks import inject_mocks
from scripts.assure_runners import build_runner_command
from scripts.assure_sandbox import (
    Sandbox,
    SandboxUnavailable,
    _apply_node_capability_overlay,
    prepare_sandbox,
)
from scripts.prepare_capability import prepare_capability
from scripts.run_verification import execute_manifest


class SafetyModuleTests(unittest.TestCase):
    def test_capability_preparation_changes_only_assure_owned_overlay(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            original_package = '{"devDependencies":{"vitest":"4.0.0"}}\n'
            original_lock = '{"lockfileVersion":3,"packages":{}}\n'
            (root / "package.json").write_text(original_package, encoding="utf-8")
            (root / "package-lock.json").write_text(original_lock, encoding="utf-8")
            with (
                patch("scripts.prepare_capability.shutil.which", return_value="/usr/bin/npm"),
                patch(
                    "scripts.prepare_capability.subprocess.run",
                    return_value=subprocess.CompletedProcess([], 0, "", ""),
                ),
            ):
                result = prepare_capability(root, "react-dom-execution")

            self.assertEqual(result["status"], "prepared")
            self.assertEqual(
                (root / "package.json").read_text(encoding="utf-8"),
                original_package,
            )
            self.assertEqual(
                (root / "package-lock.json").read_text(encoding="utf-8"),
                original_lock,
            )
            self.assertTrue(
                (root / ".assure/capabilities/node/metadata.json").is_file()
            )

    def test_node_capability_overlay_applies_only_to_sandbox_copy(self):
        with tempfile.TemporaryDirectory() as source_dir, tempfile.TemporaryDirectory() as sandbox_dir:
            source = Path(source_dir)
            sandbox = Path(sandbox_dir)
            overlay = source / ".assure/capabilities/node"
            overlay.mkdir(parents=True)
            for name, content in {
                "package.json": '{"prepared":true}\n',
                "package-lock.json": '{"lockfileVersion":3}\n',
                "metadata.json": '{"schema_version":1}\n',
            }.items():
                (overlay / name).write_text(content, encoding="utf-8")
            (source / "package.json").write_text('{"original":true}\n', encoding="utf-8")

            _apply_node_capability_overlay(source, sandbox)

            self.assertEqual(
                (sandbox / "package.json").read_text(encoding="utf-8"),
                '{"prepared":true}\n',
            )
            self.assertEqual(
                (source / "package.json").read_text(encoding="utf-8"),
                '{"original":true}\n',
            )

    def test_sandbox_health_failure_stops_before_product_scenarios(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            sandbox = Sandbox(
                root,
                "local-isolated",
                local_guard="/usr/bin/sandbox-exec",
            )
            with (
                patch.object(sandbox, "wrap", return_value=["false"]),
                self.assertRaisesRegex(
                    SandboxUnavailable,
                    "before product scenarios",
                ),
            ):
                sandbox.validate_test_environment({"vitest"})

    def test_local_execution_temp_directories_stay_inside_sandbox(self):
        with tempfile.TemporaryDirectory() as folder:
            sandbox = Sandbox(
                Path(folder),
                "local-isolated",
                local_guard="/usr/bin/sandbox-exec",
            )

            env = sandbox.execution_env()

            expected = str(Path(folder) / ".assure-tmp")
            self.assertEqual(env["TMPDIR"], expected)
            self.assertEqual(env["TMP"], expected)
            self.assertEqual(env["TEMP"], expected)
            self.assertTrue(Path(expected).is_dir())

    def test_macos_local_preflight_checks_permissions_before_scenarios(self):
        guard = shutil.which("sandbox-exec")
        if sys.platform != "darwin" or not guard:
            self.skipTest("macOS sandbox-exec is unavailable")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch(
                "scripts.assure_sandbox.shutil.which",
                side_effect=lambda name: (
                    guard if name == "sandbox-exec" else None
                ),
            ):
                sandbox = prepare_sandbox(root)
            try:
                sandbox.preflight()
                self.assertTrue((sandbox.root / ".assure-tmp").is_dir())
            finally:
                sandbox.cleanup()

    def test_shell_runner_is_rejected(self):
        with self.assertRaisesRegex(AssureError, "unsupported"):
            build_runner_command({"runner": "shell", "command": "echo bad"}, Path.cwd())

    def test_vitest_runner_is_an_argument_array(self):
        command = build_runner_command(
            {"runner": "vitest", "args": ["run", "a.test.ts"]},
            Path.cwd(),
        )
        self.assertIn("vitest", command.args)
        self.assertNotIn("shell", command.args)

    def test_builtin_firestore_mock_is_stateful_and_exposes_contract(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "src.ts").write_text(
                "import { getDocs } from 'firebase/firestore'\n",
                encoding="utf-8",
            )

            result = inject_mocks(root, "vitest")

            setup = (root / ".assure-auto-mocks.ts").read_text(
                encoding="utf-8"
            )
            self.assertIn("ASSURE_STATEFUL_FIRESTORE_V1", setup)
            self.assertIn("assureFirestore.docs.set", setup)
            self.assertIn("assureFirestore.docs.get", setup)
            self.assertIn("assureFirestore.docs.delete", setup)
            self.assertIn("blocked: false", setup)
            self.assertIn("const materialize", setup)
            self.assertIn("const increment", setup)
            self.assertIn("firebase", result.injected)

    def test_llm_generated_adapter_covers_new_boundary_after_hash_validation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "src.ts").write_text(
                "import axios from 'axios'\n",
                encoding="utf-8",
            )
            adapters = root / ".assure/adapters"
            adapters.mkdir(parents=True)
            setup = adapters / "axios.setup.ts"
            setup.write_text(
                generation_marker("//")
                + "\nimport { vi } from 'vitest'\n"
                + "vi.mock('axios', () => ({ default: { get: vi.fn() } }))\n",
                encoding="utf-8",
            )
            (adapters / "registry.json").write_text(
                json.dumps({
                    "schema_version": 1,
                    "adapters": [{
                        "id": "axios",
                        "runner": "vitest",
                        "setup": ".assure/adapters/axios.setup.ts",
                        "boundaries": ["node-http-client"],
                        "sha256": hashlib.sha256(setup.read_bytes()).hexdigest(),
                    }],
                }),
                encoding="utf-8",
            )

            result = inject_mocks(root, "vitest")

            self.assertEqual(result.unverifiable, [])
            config = (root / ".assure-vitest.config.mjs").read_text(
                encoding="utf-8"
            )
            self.assertIn("axios.setup.ts", config)

    def test_runner_selectors_are_passed_to_supported_runners(self):
        vitest = build_runner_command(
            {
                "runner": "vitest",
                "args": ["run", "flow.test.ts"],
                "selector": "submits only earned effects",
            },
            Path.cwd(),
        )
        pytest = build_runner_command(
            {
                "runner": "pytest",
                "args": ["test_flow.py"],
                "selector": "test_submits_effects",
            },
            Path.cwd(),
        )
        self.assertEqual(
            vitest.args[-2:],
            ["-t", "submits only earned effects"],
        )
        self.assertEqual(pytest.args[-2:], ["-k", "test_submits_effects"])
    def test_windows_host_executables_are_mapped_inside_linux_container(self):
        sandbox = Sandbox(root=Path("C:/sandbox"), provider="docker.exe")
        vitest = sandbox.wrap(
            ["npx.cmd", "--no-install", "vitest", "run"],
            "vitest",
        )
        pytest = sandbox.wrap(
            ["C:/Python/python.exe", "-m", "pytest", "-q"],
            "pytest",
        )
        self.assertEqual(
            vitest[-4:-1],
            ["node", "node_modules/vitest/vitest.mjs", "run"],
        )
        self.assertEqual(vitest[-1], "--config=.assure-vitest.config.mjs")
        self.assertEqual(pytest[-4:], ["python", "-m", "pytest", "-q"])

    def test_missing_container_runtime_uses_local_isolation(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch(
                "scripts.assure_sandbox.shutil.which",
                side_effect=lambda name: (
                    "/usr/bin/sandbox-exec"
                    if name == "sandbox-exec"
                    else None
                ),
            ):
                sandbox = prepare_sandbox(Path(folder))
            try:
                self.assertEqual(sandbox.provider, "local-isolated")
                self.assertNotEqual(sandbox.root, Path(folder))
                self.assertEqual(sandbox.network, "os-blocked")
                self.assertTrue(
                    (sandbox.root / ".assure-sandbox.sb").exists()
                )
            finally:
                sandbox.cleanup()

    def test_stopped_container_runtime_uses_local_isolation(self):
        with tempfile.TemporaryDirectory() as folder:
            with (
                patch(
                    "scripts.assure_sandbox.shutil.which",
                    side_effect=lambda name: (
                        "/usr/bin/sandbox-exec"
                        if name == "sandbox-exec"
                        else f"/usr/bin/{name}"
                    ),
                ),
                patch("scripts.assure_sandbox._runtime_ready", return_value=False),
            ):
                sandbox = prepare_sandbox(Path(folder))
            try:
                self.assertEqual(sandbox.provider, "local-isolated")
                self.assertEqual(sandbox.network, "os-blocked")
            finally:
                sandbox.cleanup()

    def test_missing_all_os_isolation_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            with (
                patch("scripts.assure_sandbox.shutil.which", return_value=None),
                self.assertRaisesRegex(
                    SandboxUnavailable,
                    "supported local OS isolation provider",
                ),
            ):
                prepare_sandbox(Path(folder))

    def test_macos_local_profile_blocks_writes_outside_copy(self):
        guard = shutil.which("sandbox-exec")
        if sys.platform != "darwin" or not guard:
            self.skipTest("macOS sandbox-exec is unavailable")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch(
                "scripts.assure_sandbox.shutil.which",
                side_effect=lambda name: (
                    guard if name == "sandbox-exec" else None
                ),
            ):
                sandbox = prepare_sandbox(root)
            outside = root / "outside.txt"
            inside = sandbox.root / "inside.txt"
            try:
                result = subprocess.run(
                    [
                        guard,
                        "-f",
                        str(sandbox.root / ".assure-sandbox.sb"),
                        "/bin/sh",
                        "-c",
                        'echo inside > "$1"; echo outside > "$2"',
                        "assure-test",
                        str(inside),
                        str(outside),
                    ],
                    capture_output=True,
                    text=True,
                    cwd=sandbox.root,
                    env=sandbox.execution_env(),
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertTrue(inside.exists())
                self.assertFalse(outside.exists())
            finally:
                sandbox.cleanup()

    def test_macos_local_profile_blocks_loopback_network(self):
        guard = shutil.which("sandbox-exec")
        if sys.platform != "darwin" or not guard:
            self.skipTest("macOS sandbox-exec is unavailable")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch(
                "scripts.assure_sandbox.shutil.which",
                side_effect=lambda name: (
                    guard if name == "sandbox-exec" else None
                ),
            ):
                sandbox = prepare_sandbox(root)
            listener = socket.socket()
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            port = listener.getsockname()[1]
            try:
                result = subprocess.run(
                    [
                        guard,
                        "-f",
                        str(sandbox.root / ".assure-sandbox.sb"),
                        sys.executable,
                        "-c",
                        (
                            "import socket, sys; "
                            "socket.create_connection(('127.0.0.1', "
                            "int(sys.argv[1])), timeout=1)"
                        ),
                        str(port),
                    ],
                    capture_output=True,
                    text=True,
                )
                self.assertNotEqual(result.returncode, 0)
            finally:
                listener.close()
                sandbox.cleanup()

    def test_macos_profile_blocks_provider_loopback_port(self):
        guard = shutil.which("sandbox-exec")
        if sys.platform != "darwin" or not guard:
            self.skipTest("macOS sandbox-exec is unavailable")
        availability = socket.socket()
        try:
            availability.bind(("127.0.0.1", 18080))
        except OSError:
            availability.close()
            self.skipTest("Firestore provider test port is already in use")
        availability.close()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch(
                "scripts.assure_sandbox.shutil.which",
                side_effect=lambda name: (
                    guard if name == "sandbox-exec" else None
                ),
            ):
                sandbox = prepare_sandbox(root)
            try:
                result = subprocess.run(
                    [
                        guard,
                        "-f",
                        str(sandbox.root / ".assure-sandbox.sb"),
                        shutil.which("node") or "node",
                        "-e",
                        (
                            "const net=require('node:net');"
                            "const s=net.createServer();"
                            "s.listen(18080,'127.0.0.1',()=>s.close())"
                        ),
                    ],
                    capture_output=True,
                    text=True,
                )
                self.assertNotEqual(result.returncode, 0)
            finally:
                sandbox.cleanup()

    def test_macos_local_profile_blocks_reads_outside_copy(self):
        guard = shutil.which("sandbox-exec")
        if sys.platform != "darwin" or not guard:
            self.skipTest("macOS sandbox-exec is unavailable")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            secret = root / "production-data.txt"
            secret.write_text("secret\n", encoding="utf-8")
            with patch(
                "scripts.assure_sandbox.shutil.which",
                side_effect=lambda name: (
                    guard if name == "sandbox-exec" else None
                ),
            ):
                sandbox = prepare_sandbox(root)
            try:
                result = subprocess.run(
                    [
                        guard,
                        "-f",
                        str(sandbox.root / ".assure-sandbox.sb"),
                        sys.executable,
                        "-c",
                        "from pathlib import Path; import sys; Path(sys.argv[1]).read_text()",
                        str(secret),
                    ],
                    capture_output=True,
                    text=True,
                )
                self.assertNotEqual(result.returncode, 0)
            finally:
                sandbox.cleanup()

    def test_macos_local_provider_runs_verification_inside_os_sandbox(self):
        guard = shutil.which("sandbox-exec")
        if sys.platform != "darwin" or not guard:
            self.skipTest("macOS sandbox-exec is unavailable")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "test_safe.py").write_text(
                "def test_safe():\n    assert 2 + 2 == 4\n",
                encoding="utf-8",
            )
            pytest_package = root / "pytest"
            pytest_package.mkdir()
            (pytest_package / "__init__.py").write_text("", encoding="utf-8")
            (pytest_package / "__main__.py").write_text(
                "import runpy, sys\n"
                "if '--version' in sys.argv:\n"
                "    print('pytest test-double')\n"
                "else:\n"
                "    namespace = runpy.run_path(sys.argv[-1])\n"
                "    namespace['test_safe']()\n",
                encoding="utf-8",
            )
            assure = root / ".assure"
            assure.mkdir()
            manifest = assure / "verification-manifest.yaml"
            manifest.write_text(
                "schema_version: 1\n"
                "baseline:\n"
                "  status: approved\n"
                "  commit: '0000000000000000000000000000000000000000'\n"
                "  verification_policy: functional-probes-v1\n"
                "sections:\n"
                "  - id: core\n"
                "    name: Core\n"
                "    scenarios:\n"
                "      - id: core.safe\n"
                "        name: Safe calculation\n"
                "        risk: high\n"
                "        verification:\n"
                "          mode: automated\n"
                "          tests:\n"
                "            - runner: pytest\n"
                "              args: [test_safe.py]\n",
                encoding="utf-8",
            )
            with (
                patch(
                    "scripts.assure_sandbox.shutil.which",
                    side_effect=lambda name: (
                        guard if name == "sandbox-exec" else None
                    ),
                ),
                patch(
                    "scripts.assure_sandbox._runtime_ready",
                    return_value=False,
                ),
            ):
                summary = execute_manifest(root, manifest)

            self.assertEqual(
                summary["results"][0]["status"],
                "O",
                summary,
            )
            self.assertEqual(summary["sandbox"]["provider"], "local-isolated")
            self.assertEqual(summary["sandbox"]["network"], "os-blocked")
            report = Path(summary["report"]).read_text(encoding="utf-8")
            self.assertIn("Feature verification structure", report)

    def test_container_reports_os_blocked_network(self):
        sandbox = Sandbox(Path("/tmp/assure-test"), "docker")
        self.assertEqual(sandbox.network, "os-blocked")

    def test_local_execution_environment_strips_credentials(self):
        with tempfile.TemporaryDirectory() as folder:
            sandbox = Sandbox(Path(folder), "local-isolated")
            with patch.dict(
                "scripts.assure_sandbox.os.environ",
                {"PATH": "/bin", "AWS_SECRET_ACCESS_KEY": "secret"},
                clear=True,
            ):
                env = sandbox.execution_env()
            self.assertEqual(env["PATH"], "/bin")
            self.assertNotIn("AWS_SECRET_ACCESS_KEY", env)
            self.assertEqual(env["CI"], "1")

    def test_local_bootstrap_allows_dependency_network_only(self):
        with tempfile.TemporaryDirectory() as folder:
            sandbox = Sandbox(Path(folder), "local-isolated")
            with patch.dict(
                "scripts.assure_sandbox.os.environ",
                {"PATH": "/bin", "HTTPS_PROXY": "http://proxy.example"},
                clear=True,
            ):
                bootstrap_env = sandbox.bootstrap_env()
                execution_env = sandbox.execution_env()
            self.assertEqual(
                bootstrap_env["HTTPS_PROXY"],
                "http://proxy.example",
            )
            self.assertEqual(
                execution_env["HTTPS_PROXY"],
                "http://127.0.0.1:9",
            )

    def test_local_vitest_runner_uses_temporary_dependencies_directly(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            sandbox = Sandbox(
                root,
                "local-isolated",
                node_executable="/usr/bin/node",
                local_guard="/usr/bin/sandbox-exec",
            )
            command = sandbox.wrap(
                ["npx", "--no-install", "vitest", "run", "x.test.ts"],
                "vitest",
            )
            self.assertEqual(command[0], "/usr/bin/sandbox-exec")
            self.assertEqual(command[1:3], [
                "-f",
                str(root / ".assure-sandbox.sb"),
            ])
            self.assertEqual(command[3], "/usr/bin/node")
            self.assertEqual(
                command[4],
                str(root / "node_modules" / "vitest" / "vitest.mjs"),
            )
            self.assertIn("--config=.assure-vitest.config.mjs", command)

    def test_dependency_bootstrap_requires_a_lockfile(self):
        with tempfile.TemporaryDirectory() as folder:
            result = Sandbox(Path(folder), "docker").bootstrap({"vitest"})
        self.assertEqual(result.status, "unavailable")
        self.assertIn("package-lock.json", result.detail)

    def test_nested_credentials_are_not_copied_into_the_sandbox(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            nested = root / "config"
            nested.mkdir()
            (nested / ".env.local").write_text("SECRET=x", encoding="utf-8")
            (nested / "firebase-adminsdk-key.json").write_text(
                "{}",
                encoding="utf-8",
            )
            (nested / "app.ts").write_text("export {}", encoding="utf-8")
            with patch(
                "scripts.assure_sandbox.shutil.which",
                side_effect=lambda name: (
                    "/usr/bin/sandbox-exec"
                    if name == "sandbox-exec"
                    else None
                ),
            ):
                sandbox = prepare_sandbox(root)
            try:
                self.assertFalse((sandbox.root / "config" / ".env.local").exists())
                self.assertFalse(
                    (sandbox.root / "config" / "firebase-adminsdk-key.json").exists()
                )
                self.assertTrue((sandbox.root / "config" / "app.ts").exists())
            finally:
                sandbox.cleanup()

    def test_nested_source_link_is_refused_before_copy(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "src"
            source.mkdir()
            outside = root.parent / f"{root.name}-outside.txt"
            outside.write_text("outside\n", encoding="utf-8")
            self.addCleanup(outside.unlink, missing_ok=True)
            try:
                (source / "outside.txt").symlink_to(outside)
            except OSError as exc:
                self.skipTest(f"symlink unavailable: {exc}")

            with (
                patch(
                    "scripts.assure_sandbox.shutil.which",
                    side_effect=lambda name: (
                        "/usr/bin/sandbox-exec"
                        if name == "sandbox-exec"
                        else None
                    ),
                ),
                self.assertRaisesRegex(
                    SandboxUnavailable,
                    "source link is not allowed: src/outside.txt",
                ),
            ):
                prepare_sandbox(root)

    def test_only_assure_functional_probes_are_copied_from_assure_state(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            probes = root / ".assure" / "probes"
            probes.mkdir(parents=True)
            (probes / "login.assure.test.ts").write_text(
                "export {}",
                encoding="utf-8",
            )
            (root / ".assure" / "verification-manifest.yaml").write_text(
                "secret manifest state",
                encoding="utf-8",
            )
            (root / ".assure" / "reports").mkdir()
            (root / ".assure" / "reports" / "report.md").write_text(
                "private report",
                encoding="utf-8",
            )

            with patch(
                "scripts.assure_sandbox.shutil.which",
                side_effect=lambda name: (
                    "/usr/bin/sandbox-exec"
                    if name == "sandbox-exec"
                    else None
                ),
            ):
                sandbox = prepare_sandbox(root)
            try:
                self.assertTrue(
                    (
                        sandbox.root
                        / ".assure"
                        / "probes"
                        / "login.assure.test.ts"
                    ).exists()
                )
                self.assertFalse(
                    (
                        sandbox.root
                        / ".assure"
                        / "verification-manifest.yaml"
                    ).exists()
                )
                self.assertFalse(
                    (sandbox.root / ".assure" / "reports").exists()
                )
            finally:
                sandbox.cleanup()

    def test_linked_assure_functional_probes_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            assure = root / ".assure"
            assure.mkdir()
            external = root / "external-probes"
            external.mkdir()
            try:
                (assure / "probes").symlink_to(
                    external,
                    target_is_directory=True,
                )
            except OSError:
                self.skipTest("directory symlinks are unavailable")

            with (
                patch(
                    "scripts.assure_sandbox.shutil.which",
                    side_effect=lambda name: (
                        "/usr/bin/sandbox-exec"
                        if name == "sandbox-exec"
                        else None
                    ),
                ),
                self.assertRaisesRegex(
                    SandboxUnavailable,
                    "link-free directory",
                ),
            ):
                prepare_sandbox(root)

    def test_user_firebase_mock_wins_and_network_guards_are_injected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "x.test.ts").write_text(
                "import { vi } from 'vitest'; vi.mock('firebase/firestore')",
                encoding="utf-8",
            )
            result = inject_mocks(root, "vitest")
            self.assertIn("firebase: user mock preserved", result.conflicts)
            self.assertTrue((root / ".assure-auto-mocks.ts").exists())
            self.assertTrue((root / ".assure-vitest.config.mjs").exists())

    def test_missing_firebase_mock_gets_an_in_memory_setup(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "x.test.ts").write_text(
                "import { getFirestore } from 'firebase/firestore'",
                encoding="utf-8",
            )
            result = inject_mocks(root, "vitest")
            setup = (root / ".assure-auto-mocks.ts").read_text(encoding="utf-8")
            config = (root / ".assure-vitest.config.mjs").read_text(
                encoding="utf-8",
            )
            self.assertIn("firebase", result.injected)
            self.assertIn("getFirestore", setup)
            self.assertIn("getDocs", setup)
            self.assertIn("setupFiles", config)

    def test_dependency_sources_do_not_override_project_mock_detection(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            dependency = root / "node_modules" / "dependency"
            dependency.mkdir(parents=True)
            (dependency / "index.js").write_text(
                "vi.mock('firebase/firestore')",
                encoding="utf-8",
            )
            (root / "x.test.ts").write_text(
                "import { getFirestore } from 'firebase/firestore'",
                encoding="utf-8",
            )
            result = inject_mocks(root, "vitest")
            self.assertIn("firebase", result.injected)
            self.assertNotIn("firebase: user mock preserved", result.conflicts)

    def test_pytest_outbound_client_fails_closed_without_adapter(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "service.py").write_text(
                "import requests\n"
                "def load(): return requests.get('https://example.invalid')\n",
                encoding="utf-8",
            )

            result = inject_mocks(root, "pytest")

            self.assertTrue(result.unverifiable)
            self.assertIn("python-http", result.unverifiable[0])

    def test_jest_database_client_fails_closed_without_adapter(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "service.ts").write_text(
                "import { MongoClient } from 'mongodb'\n",
                encoding="utf-8",
            )

            result = inject_mocks(root, "jest")

            self.assertTrue(result.unverifiable)
            self.assertIn("database-client", result.unverifiable[0])

    def test_vitest_unknown_socket_boundary_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "service.ts").write_text(
                "import net from 'node:net'\n",
                encoding="utf-8",
            )

            result = inject_mocks(root, "vitest")

            self.assertTrue(result.unverifiable)
            self.assertIn("direct-socket", result.unverifiable[0])

    def test_missing_sandbox_still_returns_a_final_summary(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            assure = root / ".assure"
            assure.mkdir()
            manifest = assure / "verification-manifest.yaml"
            manifest.write_text(
                "schema_version: 1\n"
                "baseline:\n"
                "  status: approved\n"
                "  commit: '0000000000000000000000000000000000000000'\n"
                "  verification_policy: functional-probes-v1\n"
                "sections:\n"
                "  - id: app\n"
                "    name: App\n"
                "    scenarios:\n"
                "      - id: app.test\n"
                "        name: Test\n"
                "        risk: critical\n"
                "        verification:\n"
                "          mode: automated\n"
                "          tests:\n"
                "            - runner: vitest\n"
                "              args: [run]\n",
                encoding="utf-8",
            )
            with patch("scripts.run_verification.prepare_sandbox", side_effect=SandboxUnavailable("sandbox runtime is unavailable")):
                summary = execute_manifest(root, manifest)
            self.assertEqual(summary["verdict"], "blocked")
            self.assertEqual(summary["results"][0]["status"], "?")
            self.assertEqual(summary["sandbox"]["network"], "not-run")


if __name__ == "__main__":
    unittest.main()
