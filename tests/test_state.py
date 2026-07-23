import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.assure_common import AssureError, run_text, source_snapshot
from scripts.assure_state import classify_project


class ProjectStateTests(unittest.TestCase):
    def test_run_text_converts_a_timeout_to_assure_error(self):
        with patch(
            "scripts.assure_common.subprocess.run",
            side_effect=subprocess.TimeoutExpired(["git"], 0.01),
        ):
            with self.assertRaisesRegex(AssureError, "timed out"):
                run_text(["git", "rev-parse", "HEAD"], Path.cwd(), 0.01)

    def make_repo(self) -> Path:
        root = Path(tempfile.mkdtemp())
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.com"], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
        (root / "tracked.py").write_text("print('v1')\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "tracked.py"], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-qm", "baseline"], check=True)
        return root

    def write_approved_manifest(self, root: Path, commit: str, snapshot: str) -> None:
        assure = root / ".assure"
        assure.mkdir(exist_ok=True)
        (assure / "verification-manifest.yaml").write_text(
            "schema_version: 1\nbaseline:\n"
            f"  status: approved\n  commit: {commit}\n  source_snapshot: {snapshot}\n"
            "sections: []\n",
            encoding="utf-8",
        )

    def update_manifest_snapshot(self, root: Path, snapshot: str) -> None:
        path = root / ".assure" / "verification-manifest.yaml"
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                "source_snapshot: " + source_snapshot(root),
                f"source_snapshot: {snapshot}",
            ),
            encoding="utf-8",
        )

    def test_absent_when_no_assure_state_exists(self):
        root = self.make_repo()
        self.assertEqual(classify_project(root).kind, "absent")

    def test_approved_current_when_commit_matches(self):
        root = self.make_repo()
        commit = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
        ).strip()
        self.write_approved_manifest(root, commit, source_snapshot(root))
        self.assertEqual(classify_project(root).kind, "approved-current")

    def test_approved_current_with_uncommitted_files_matching_snapshot(self):
        root = self.make_repo()
        commit = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
        ).strip()
        self.write_approved_manifest(root, commit, source_snapshot(root))
        (root / "uncommitted.txt").write_text("same", encoding="utf-8")
        self.update_manifest_snapshot(root, source_snapshot(root))
        self.assertEqual(classify_project(root).kind, "approved-current")

    def test_approved_stale_when_commit_differs(self):
        root = self.make_repo()
        baseline_commit = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
        ).strip()
        (root / "tracked.py").write_text("print('v2')\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "tracked.py"], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-qm", "source change"], check=True)
        self.write_approved_manifest(root, baseline_commit, source_snapshot(root))
        self.assertEqual(classify_project(root).kind, "approved-stale")

    def test_approved_stale_when_working_tree_product_changes(self):
        root = self.make_repo()
        commit = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
        ).strip()
        self.write_approved_manifest(root, commit, source_snapshot(root))
        (root / "tracked.py").write_text("print('v2')\n", encoding="utf-8")
        self.assertEqual(classify_project(root).kind, "approved-stale")

    def test_assure_only_changes_do_not_make_product_source_stale(self):
        root = self.make_repo()
        commit = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
        ).strip()
        self.write_approved_manifest(root, commit, source_snapshot(root))
        assure = root / ".assure"
        (assure / "notes.txt").write_text("local result\n", encoding="utf-8")
        self.assertEqual(classify_project(root).kind, "approved-current")

    def test_approved_stale_when_assure_file_is_renamed_to_product_source(self):
        root = self.make_repo()
        assure = root / ".assure"
        assure.mkdir()
        (assure / "source.py").write_text("internal\n", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(root), "add", ".assure/source.py"], check=True
        )
        subprocess.run(
            ["git", "-C", str(root), "commit", "-qm", "add assure source"], check=True
        )
        commit = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
        ).strip()
        self.write_approved_manifest(root, commit, source_snapshot(root))
        subprocess.run(
            ["git", "-C", str(root), "mv", ".assure/source.py", "product.py"],
            check=True,
        )
        self.assertEqual(classify_project(root).kind, "approved-stale")

    def test_approved_current_when_assure_file_is_renamed_within_assure(self):
        root = self.make_repo()
        assure = root / ".assure"
        assure.mkdir()
        (assure / "source.py").write_text("internal\n", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(root), "add", ".assure/source.py"], check=True
        )
        subprocess.run(
            ["git", "-C", str(root), "commit", "-qm", "add assure source"], check=True
        )
        commit = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
        ).strip()
        self.write_approved_manifest(root, commit, source_snapshot(root))
        subprocess.run(
            ["git", "-C", str(root), "mv", ".assure/source.py", ".assure/renamed.py"],
            check=True,
        )
        self.assertEqual(classify_project(root).kind, "approved-current")

    def test_incomplete_when_manifest_is_missing(self):
        root = self.make_repo()
        (root / ".assure").mkdir()
        self.assertEqual(classify_project(root).kind, "incomplete")

    def test_damaged_when_manifest_is_invalid(self):
        root = self.make_repo()
        assure = root / ".assure"
        assure.mkdir()
        (assure / "verification-manifest.yaml").write_text(
            "schema_version: [\n",
            encoding="utf-8",
        )
        self.assertEqual(classify_project(root).kind, "damaged")

    def test_draft_manifest_returns_draft(self):
        root = self.make_repo()
        assure = root / ".assure"
        assure.mkdir()
        (assure / "verification-manifest.yaml").write_text(
            "schema_version: 1\nbaseline:\n  status: draft\nsections: []\n",
            encoding="utf-8",
        )
        self.assertEqual(classify_project(root).kind, "draft")

    def test_review_manifest_returns_review(self):
        root = self.make_repo()
        assure = root / ".assure"
        assure.mkdir()
        (assure / "verification-manifest.yaml").write_text(
            "schema_version: 1\nbaseline:\n  status: review\nsections: []\n",
            encoding="utf-8",
        )
        self.assertEqual(classify_project(root).kind, "review")

    def test_damaged_when_baseline_commit_does_not_exist(self):
        root = self.make_repo()
        assure = root / ".assure"
        assure.mkdir()
        (assure / "verification-manifest.yaml").write_text(
            "schema_version: 1\nbaseline:\n  status: approved\n"
            "  commit: 0000000000000000000000000000000000000000\nsections: []\n",
            encoding="utf-8",
        )
        self.assertEqual(classify_project(root).kind, "damaged")


if __name__ == "__main__":
    unittest.main()
