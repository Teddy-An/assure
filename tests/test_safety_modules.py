import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.assure_common import AssureError
from scripts.assure_mocks import inject_mocks
from scripts.assure_runners import build_runner_command
from scripts.assure_sandbox import SandboxUnavailable, prepare_sandbox
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

    def test_missing_sandbox_runtime_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch("scripts.assure_sandbox.shutil.which", return_value=None):
                with self.assertRaises(SandboxUnavailable):
                    prepare_sandbox(Path(folder))

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
