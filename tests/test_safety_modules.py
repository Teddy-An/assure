import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.assure_common import AssureError
from scripts.assure_mocks import inject_mocks
from scripts.assure_runners import build_runner_command
from scripts.assure_sandbox import Sandbox, SandboxUnavailable, prepare_sandbox
from scripts.run_verification import execute_manifest


class SafetyModuleTests(unittest.TestCase):
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
            with patch("scripts.assure_sandbox.shutil.which", return_value=None):
                sandbox = prepare_sandbox(Path(folder))
            try:
                self.assertEqual(sandbox.provider, "local-isolated")
                self.assertNotEqual(sandbox.root, Path(folder))
            finally:
                sandbox.cleanup()

    def test_stopped_container_runtime_uses_local_isolation(self):
        with tempfile.TemporaryDirectory() as folder:
            with (
                patch(
                    "scripts.assure_sandbox.shutil.which",
                    side_effect=lambda name: f"/usr/bin/{name}",
                ),
                patch("scripts.assure_sandbox._runtime_ready", return_value=False),
            ):
                sandbox = prepare_sandbox(Path(folder))
            try:
                self.assertEqual(sandbox.provider, "local-isolated")
            finally:
                sandbox.cleanup()

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
            )
            command = sandbox.wrap(
                ["npx", "--no-install", "vitest", "run", "x.test.ts"],
                "vitest",
            )
            self.assertEqual(command[0], "/usr/bin/node")
            self.assertEqual(
                command[1],
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
                side_effect=lambda name: "docker.exe" if name == "docker" else None,
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

            with patch("scripts.assure_sandbox.shutil.which", return_value=None):
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
                patch("scripts.assure_sandbox.shutil.which", return_value=None),
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
