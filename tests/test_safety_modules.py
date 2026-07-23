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
        self.assertEqual(vitest[-1], "--setupFiles=.assure-auto-mocks.ts")
        self.assertEqual(pytest[-4:], ["python", "-m", "pytest", "-q"])

    def test_missing_sandbox_runtime_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch("scripts.assure_sandbox.shutil.which", return_value=None):
                with self.assertRaises(SandboxUnavailable):
                    prepare_sandbox(Path(folder))

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

    def test_missing_firebase_mock_gets_an_in_memory_setup(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "x.test.ts").write_text(
                "import { getFirestore } from 'firebase/firestore'",
                encoding="utf-8",
            )
            result = inject_mocks(root, "vitest")
            setup = (root / ".assure-auto-mocks.ts").read_text(encoding="utf-8")
            self.assertIn("firebase", result.injected)
            self.assertIn("getFirestore", setup)
            self.assertIn("getDocs", setup)

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
