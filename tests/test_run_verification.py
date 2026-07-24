import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from scripts.assure_common import AssureError
from scripts.assure_sandbox import BootstrapResult
from scripts.run_verification import execute_manifest, record_manual_result, run_automated


class LocalTestSandbox:
    provider = "test"
    network = "disabled"

    def __init__(self, root: Path):
        self.root = root

    def bootstrap(self, runners: set[str]) -> BootstrapResult:
        return BootstrapResult("ready", "test dependencies")

    def wrap(self, argv: list[str], runner: str) -> list[str]:
        if runner == "pytest":
            return [sys.executable, *argv[3:]]
        return argv

    def execution_env(self) -> None:
        return None

    def cleanup(self) -> None:
        pass


class VerificationRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        patcher = patch(
            "scripts.run_verification.prepare_sandbox",
            side_effect=lambda root: LocalTestSandbox(root),
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def python_command(self, root: Path, source: str) -> str:
        commands = root / ".assure" / "test-commands"
        commands.mkdir(parents=True, exist_ok=True)
        script = commands / f"command-{len(list(commands.iterdir()))}.py"
        script.write_text(source, encoding="utf-8")
        return str(script)

    def make_repo(self) -> tuple[Path, str]:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(
            ["git", "-C", str(root), "config", "user.email", "test@example.com"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(root), "config", "user.name", "Test"],
            check=True,
        )
        (root / "tracked.txt").write_text("fixture\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "tracked.txt"], check=True)
        subprocess.run(
            ["git", "-C", str(root), "commit", "-qm", "fixture"],
            check=True,
        )
        commit = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            text=True,
        ).strip()
        (root / ".assure").mkdir()
        (root / ".assure" / "config.yaml").write_text(
            "language: en\n",
            encoding="utf-8",
        )
        return root, commit

    def write_manifest(
        self,
        root: Path,
        commit: str,
        scenarios: list[dict],
    ) -> Path:
        assure = root / ".assure"
        assure.mkdir(exist_ok=True)
        manifest = {
            "schema_version": 1,
            "baseline": {"status": "approved", "commit": commit},
            "sections": [{
                "id": "auth",
                "name": "인증",
                "scenarios": scenarios,
            }],
        }
        path = assure / "verification-manifest.yaml"
        path.write_text(
            yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        return path

    def make_manifest(
        self,
        root: Path,
        commit: str,
        command: str,
        risk: str = "critical",
    ) -> Path:
        return self.write_manifest(
            root,
            commit,
            [{
                "id": "auth.login",
                "name": "정상 로그인",
                "risk": risk,
                "verification": {
                    "mode": "automated",
                    "tests": [{"runner": "pytest", "args": [command]}],
                },
            }],
        )

    def run_cli(self, root: Path) -> subprocess.CompletedProcess:
        runner = Path(__file__).parents[1] / "scripts" / "run_verification.py"
        return subprocess.run(
            [sys.executable, "-X", "utf8", str(runner), "--project", str(root)],
            text=True,
            encoding="utf-8",
            capture_output=True,
        )

    def run_manual_cli(
        self,
        root: Path,
        summary_path: Path,
    ) -> subprocess.CompletedProcess:
        runner = Path(__file__).parents[1] / "scripts" / "run_verification.py"
        return subprocess.run(
            [
                sys.executable,
                "-X",
                "utf8",
                str(runner),
                "--project",
                str(root),
                "--summary",
                str(summary_path),
                "--manual-result",
                "auth.login",
                "--response",
                "confirmed",
                "--actor",
                "reviewer",
            ],
            text=True,
            encoding="utf-8",
            capture_output=True,
        )

    def make_manual_summary(self, root: Path, commit: str) -> dict:
        manifest_path = self.write_manifest(
            root,
            commit,
            [{
                "id": "auth.login",
                "name": "정상 로그인",
                "risk": "critical",
                "verification": {
                    "mode": "manual",
                    "instructions": ["보호 화면 접근을 확인한다."],
                },
            }],
        )
        return execute_manifest(root, manifest_path)

    def reapprove_current_manifest(
        self,
        root: Path,
        manifest_path: Path,
    ) -> str:
        (root / "tracked.txt").write_text("reapproved source\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "tracked.txt"], check=True)
        subprocess.run(
            ["git", "-C", str(root), "commit", "-qm", "reapproved source"],
            check=True,
        )
        commit = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            text=True,
        ).strip()
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        manifest["baseline"]["commit"] = commit
        manifest_path.write_text(
            yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        return commit

    def test_pass_does_not_embed_raw_log_in_summary(self):
        root, commit = self.make_repo()
        manifest = self.make_manifest(
            root,
            commit,
            self.python_command(root, "print('secret-success-log')\n"),
        )

        result = execute_manifest(root, manifest)

        self.assertEqual(result["verdict"], "releasable")
        self.assertEqual(result["results"][0]["status"], "O")
        self.assertNotIn("secret-success-log", str(result))
        artifact = Path(result["results"][0]["artifact"])
        self.assertIn("secret-success-log", artifact.read_text(encoding="utf-8"))
        report = Path(result["report"]).read_text(encoding="utf-8")
        saved_summary = Path(result["summary_path"]).read_text(encoding="utf-8")
        self.assertIn("| No. | Risk | Section | ID |", report)
        self.assertIn("| Automated | Passed | exit code: `0`<br>", report)
        self.assertNotIn("secret-success-log", report)
        self.assertNotIn("secret-success-log", saved_summary)

    def test_critical_failure_blocks_and_keeps_artifact_path(self):
        root, commit = self.make_repo()
        manifest = self.make_manifest(
            root,
            commit,
            self.python_command(
                root,
                "print('large-private-log')\nraise SystemExit(1)\n",
            ),
        )

        result = execute_manifest(root, manifest)

        self.assertEqual(result["verdict"], "blocked")
        self.assertEqual(result["results"][0]["status"], "X")
        artifact = Path(result["results"][0]["artifact"])
        self.assertTrue(artifact.exists())
        self.assertIn("large-private-log", artifact.read_text(encoding="utf-8"))
        self.assertNotIn("large-private-log", str(result))
        self.assertNotIn(
            "large-private-log",
            Path(result["report"]).read_text(encoding="utf-8"),
        )

    def test_timeout_terminates_child_process_before_it_can_write_a_marker(self):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        marker = root / ".assure" / "delayed-child-marker"
        child = (
            "import time\n"
            "from pathlib import Path\n"
            "time.sleep(1)\n"
            f"Path({str(marker)!r}).write_text('created', encoding='utf-8')\n"
        )
        command = self.python_command(
            root,
            "import subprocess, sys, time\n"
            f"subprocess.Popen([sys.executable, '-c', {child!r}])\n"
            "time.sleep(10)\n",
        )
        scenario = {
            "id": "timeout.child",
            "name": "Timeout child",
            "section_name": "Automated",
            "risk": "critical",
            "verification": {
                "tests": [{"runner": "pytest", "args": [command]}],
            },
        }

        with patch("scripts.run_verification.AUTOMATED_TIMEOUT_SECONDS", 0.2):
            result = run_automated(
                root,
                scenario,
                root / ".assure" / "artifacts",
                LocalTestSandbox(root),
            )
        time.sleep(1.2)

        self.assertEqual(result["exit_code"], 124)
        self.assertFalse(marker.exists())

    def test_explicit_manual_confirmation_updates_saved_summary(self):
        root, commit = self.make_repo()
        manifest_path = self.write_manifest(
            root,
            commit,
            [{
                "id": "auth.login",
                "name": "정상 로그인",
                "risk": "critical",
                "verification": {
                    "mode": "manual",
                    "instructions": ["로그아웃 후 보호 화면 접근을 확인한다."],
                },
            }],
        )
        initial = execute_manifest(root, manifest_path)
        self.assertEqual(initial["verdict"], "blocked")
        self.assertIn("manifest_identity", initial)
        self.assertEqual(
            initial["manifest_identity"],
            {
                "baseline_commit": commit,
                "manifest_sha256": hashlib.sha256(
                    manifest_path.read_bytes()
                ).hexdigest(),
            },
        )

        updated = record_manual_result(
            Path(initial["summary_path"]),
            "auth.login",
            "confirmed",
            "s1dev",
            None,
        )

        self.assertEqual(updated["results"][0]["status"], "O")
        self.assertEqual(updated["results"][0]["confirmed_by"], "s1dev")
        self.assertEqual(updated["verdict"], "releasable")
        saved = json.loads(
            Path(initial["summary_path"]).read_text(encoding="utf-8")
        )
        self.assertEqual(saved, updated)

    def test_manual_result_rejects_missing_actor(self):
        root, commit = self.make_repo()
        manifest_path = self.write_manifest(
            root,
            commit,
            [{
                "id": "auth.login",
                "name": "정상 로그인",
                "risk": "critical",
                "verification": {
                    "mode": "manual",
                    "instructions": ["보호 화면 접근을 확인한다."],
                },
            }],
        )
        initial = execute_manifest(root, manifest_path)

        with self.assertRaisesRegex(
            AssureError,
            "manual result requires an actor",
        ):
            record_manual_result(
                Path(initial["summary_path"]),
                "auth.login",
                "confirmed",
                "",
                None,
            )

    def test_all_registered_checks_run_after_an_earlier_failure(self):
        root, commit = self.make_repo()
        marker = root / ".assure" / "second-check-ran"
        manifest_path = self.write_manifest(
            root,
            commit,
            [{
                "id": "auth.login",
                "name": "정상 로그인",
                "risk": "critical",
                "verification": {
                    "mode": "automated",
                    "tests": [
                        {
                            "runner": "pytest",
                            "args": [self.python_command(
                                root,
                                "raise SystemExit(7)\n",
                            )],
                        },
                        {
                            "runner": "pytest",
                            "args": [self.python_command(
                                root,
                                "from pathlib import Path\n"
                                "Path('.assure/second-check-ran').write_text("
                                "'ran', encoding='utf-8')\n",
                            )],
                        },
                    ],
                },
            }],
        )

        result = execute_manifest(root, manifest_path)

        self.assertEqual(result["results"][0]["status"], "X")
        self.assertEqual(result["results"][0]["exit_code"], 7)
        self.assertEqual(marker.read_text(encoding="utf-8"), "ran")

    def test_summary_identity_binds_manifest_bytes_loaded_before_commands(self):
        root, commit = self.make_repo()
        manifest_path = self.make_manifest(
            root,
            commit,
            self.python_command(
                root,
                "from pathlib import Path\n"
                "with Path('.assure/verification-manifest.yaml').open("
                "'a', encoding='utf-8') as handle:\n"
                "    handle.write('\\n# changed by registered check\\n')\n",
            ),
        )
        expected_sha256 = hashlib.sha256(manifest_path.read_bytes()).hexdigest()

        result = execute_manifest(root, manifest_path)

        self.assertEqual(
            result["manifest_identity"]["manifest_sha256"],
            expected_sha256,
        )

    def test_invalid_automated_registration_prevents_any_execution(self):
        root, commit = self.make_repo()
        marker = root / ".assure" / "must-not-run"
        manifest_path = self.write_manifest(
            root,
            commit,
            [
                {
                    "id": "auth.login",
                    "name": "정상 로그인",
                    "risk": "critical",
                    "verification": {
                        "mode": "automated",
                        "tests": [{
                            "runner": "pytest",
                            "args": [self.python_command(
                                root,
                                "from pathlib import Path\n"
                                "Path('.assure/must-not-run').touch()\n",
                            )],
                        }],
                    },
                },
                {
                    "id": "auth.logout",
                    "name": "로그아웃",
                    "risk": "critical",
                    "verification": {"mode": "automated", "tests": []},
                },
            ],
        )

        with self.assertRaisesRegex(
            AssureError,
            "automated scenario requires at least one test",
        ):
            execute_manifest(root, manifest_path)

        self.assertFalse(marker.exists())

    def test_cli_returns_zero_with_json_for_releasable_result(self):
        root, commit = self.make_repo()
        self.write_manifest(root, commit, [])

        result = self.run_cli(root)

        self.assertEqual(result.returncode, 0)
        self.assertTrue(result.stdout)
        summary = json.loads(result.stdout)
        self.assertEqual(summary["verdict"], "releasable")

    def test_cli_returns_one_for_blocked_result(self):
        root, commit = self.make_repo()
        self.make_manifest(
            root,
            commit,
            self.python_command(root, "raise SystemExit(1)\n"),
        )

        result = self.run_cli(root)

        self.assertEqual(result.returncode, 1)
        self.assertTrue(result.stdout)
        self.assertEqual(json.loads(result.stdout)["verdict"], "blocked")

    def test_stale_baseline_cli_does_not_execute_registered_checks(self):
        root, commit = self.make_repo()
        marker = root / ".assure" / "stale-command-ran"
        self.make_manifest(
            root,
            commit,
            self.python_command(
                root,
                "from pathlib import Path\n"
                "Path('.assure/stale-command-ran').write_text("
                "'ran', encoding='utf-8')\n",
            ),
        )
        (root / "tracked.txt").write_text("changed\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "tracked.txt"], check=True)
        subprocess.run(
            ["git", "-C", str(root), "commit", "-qm", "source change"],
            check=True,
        )

        result = self.run_cli(root)

        self.assertEqual(result.returncode, 2)
        self.assertTrue(result.stdout)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["state"], "approved-stale")
        self.assertEqual(payload["verdict"], "not-run")
        self.assertFalse(marker.exists())

    def test_manual_cli_rejects_stale_project_without_mutating_saved_results(self):
        root, commit = self.make_repo()
        initial = self.make_manual_summary(root, commit)
        summary_path = Path(initial["summary_path"])
        report_path = Path(initial["report"])
        summary_before = summary_path.read_bytes()
        report_before = report_path.read_bytes()
        (root / "tracked.txt").write_text("changed\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "tracked.txt"], check=True)
        subprocess.run(
            ["git", "-C", str(root), "commit", "-qm", "source change"],
            check=True,
        )

        result = self.run_manual_cli(root, summary_path)

        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["state"], "approved-stale")
        self.assertEqual(summary_path.read_bytes(), summary_before)
        self.assertEqual(report_path.read_bytes(), report_before)

    def test_manual_cli_updates_contained_summary_for_current_project(self):
        root, commit = self.make_repo()
        initial = self.make_manual_summary(root, commit)
        summary_path = Path(initial["summary_path"])

        result = self.run_manual_cli(root, summary_path)

        self.assertEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["results"][0]["status"], "O")
        saved = json.loads(summary_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["results"][0]["confirmed_by"], "reviewer")
        self.assertIn(
            "| Verdict | releasable (`releasable`) |",
            Path(initial["report"]).read_text(encoding="utf-8"),
        )

    def test_manual_cli_rejects_summary_from_prior_approved_manifest(self):
        root, commit = self.make_repo()
        initial = self.make_manual_summary(root, commit)
        summary_path = Path(initial["summary_path"])
        report_path = Path(initial["report"])
        manifest_path = root / ".assure" / "verification-manifest.yaml"
        self.reapprove_current_manifest(root, manifest_path)
        summary_before = summary_path.read_bytes()
        report_before = report_path.read_bytes()

        result = self.run_manual_cli(root, summary_path)

        self.assertEqual(result.returncode, 2)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["state"], "manual-update-failed")
        self.assertIn("manifest identity", payload["reason"])
        self.assertEqual(summary_path.read_bytes(), summary_before)
        self.assertEqual(report_path.read_bytes(), report_before)

    def test_library_rejects_summary_from_prior_approved_manifest(self):
        root, commit = self.make_repo()
        initial = self.make_manual_summary(root, commit)
        summary_path = Path(initial["summary_path"])
        report_path = Path(initial["report"])
        manifest_path = root / ".assure" / "verification-manifest.yaml"
        self.reapprove_current_manifest(root, manifest_path)
        summary_before = summary_path.read_bytes()
        report_before = report_path.read_bytes()

        with self.assertRaisesRegex(AssureError, "manifest identity"):
            record_manual_result(
                summary_path,
                "auth.login",
                "confirmed",
                "reviewer",
                None,
            )

        self.assertEqual(summary_path.read_bytes(), summary_before)
        self.assertEqual(report_path.read_bytes(), report_before)

    def test_manual_cli_rejects_cross_project_summary_without_mutation(self):
        project_root, project_commit = self.make_repo()
        self.make_manifest(
            project_root,
            project_commit,
            self.python_command(project_root, "raise SystemExit(0)\n"),
        )
        other_root, other_commit = self.make_repo()
        other = self.make_manual_summary(other_root, other_commit)
        summary_path = Path(other["summary_path"])
        report_path = Path(other["report"])
        summary_before = summary_path.read_bytes()
        report_before = report_path.read_bytes()

        result = self.run_manual_cli(project_root, summary_path)

        self.assertEqual(result.returncode, 2)
        self.assertEqual(
            json.loads(result.stdout)["state"],
            "manual-update-failed",
        )
        self.assertEqual(summary_path.read_bytes(), summary_before)
        self.assertEqual(report_path.read_bytes(), report_before)

    def test_manual_cli_rejects_outside_report_path_before_any_write(self):
        root, commit = self.make_repo()
        initial = self.make_manual_summary(root, commit)
        summary_path = Path(initial["summary_path"])
        outside = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, outside)
        outside_report = outside / "outside-report.md"
        outside_report.write_text("must remain unchanged\n", encoding="utf-8")
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
        payload["report"] = str(outside_report)
        summary_path.write_text(json.dumps(payload), encoding="utf-8")
        summary_before = summary_path.read_bytes()
        report_before = outside_report.read_bytes()

        result = self.run_manual_cli(root, summary_path)

        self.assertEqual(result.returncode, 2)
        self.assertEqual(
            json.loads(result.stdout)["state"],
            "manual-update-failed",
        )
        self.assertEqual(summary_path.read_bytes(), summary_before)
        self.assertEqual(outside_report.read_bytes(), report_before)

    def test_distinct_scenario_ids_keep_distinct_artifacts(self):
        root, commit = self.make_repo()
        manifest_path = self.write_manifest(
            root,
            commit,
            [
                {
                    "id": "auth/login",
                    "name": "슬래시 로그인",
                    "risk": "critical",
                    "verification": {
                        "mode": "automated",
                        "tests": [{
                            "runner": "pytest",
                            "args": [self.python_command(
                                root,
                                "print('slash-artifact-content')\n",
                            )],
                        }],
                    },
                },
                {
                    "id": "auth_login",
                    "name": "밑줄 로그인",
                    "risk": "critical",
                    "verification": {
                        "mode": "automated",
                        "tests": [{
                            "runner": "pytest",
                            "args": [self.python_command(
                                root,
                                "print('underscore-artifact-content')\n",
                            )],
                        }],
                    },
                },
            ],
        )

        result = execute_manifest(root, manifest_path)

        first_artifact = Path(result["results"][0]["artifact"])
        second_artifact = Path(result["results"][1]["artifact"])
        self.assertNotEqual(first_artifact, second_artifact)
        self.assertIn(
            "slash-artifact-content",
            first_artifact.read_text(encoding="utf-8"),
        )
        self.assertIn(
            "underscore-artifact-content",
            second_artifact.read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
