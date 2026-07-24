import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.assure_common import AssureError
from scripts.assure_sandbox import SandboxUnavailable, prepare_sandbox
from scripts.assure_sandbox_profile import (
    build_sandbox_profile,
    load_sandbox_profile,
    validate_sandbox_profile,
)


class SandboxProfileTests(unittest.TestCase):
    def make_project(self) -> Path:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        (root / "package.json").write_text(
            '{"dependencies":{"react":"19.0.0"},'
            '"devDependencies":{"vitest":"4.0.0","jsdom":"26.0.0"}}',
            encoding="utf-8",
        )
        return root

    def test_profile_is_one_project_level_contract(self):
        root = self.make_project()
        with patch(
            "scripts.assure_capabilities.shutil.which",
            side_effect=lambda name: (
                "/usr/bin/sandbox-exec" if name == "sandbox-exec" else None
            ),
        ):
            profile = build_sandbox_profile(root)

        self.assertEqual(profile["status"], "ready")
        self.assertEqual(profile["sandbox_contract"]["source"], "temporary-copy")
        self.assertEqual(profile["sandbox_contract"]["production_data"], "forbidden")
        self.assertIn(
            "run-complete-scenario-population",
            profile["execution_order"],
        )
        self.assertEqual(profile["unresolved"], [])

    def test_external_providers_do_not_prevent_ready_profile(self):
        root = self.make_project()
        with patch(
            "scripts.assure_capabilities.shutil.which",
            side_effect=lambda name: (
                "/usr/bin/sandbox-exec" if name == "sandbox-exec" else None
            ),
        ):
            profile = build_sandbox_profile(root)

        self.assertEqual(profile["status"], "ready")
        self.assertEqual(profile["unresolved"], [])

    def test_environment_change_invalidates_profile_before_execution(self):
        root = self.make_project()
        with patch(
            "scripts.assure_capabilities.shutil.which",
            side_effect=lambda name: (
                "/usr/bin/sandbox-exec" if name == "sandbox-exec" else None
            ),
        ):
            profile = build_sandbox_profile(root)
        assure = root / ".assure"
        assure.mkdir()
        (assure / "sandbox-profile.json").write_text(
            json.dumps(profile),
            encoding="utf-8",
        )
        (root / "package.json").write_text(
            '{"dependencies":{"react":"20.0.0"}}',
            encoding="utf-8",
        )

        self.assertIn(
            "stale",
            validate_sandbox_profile(root, profile)[0],
        )
        with self.assertRaisesRegex(AssureError, "stale"):
            load_sandbox_profile(root)
        with self.assertRaisesRegex(SandboxUnavailable, "before execution"):
            prepare_sandbox(root)


if __name__ == "__main__":
    unittest.main()
