import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.assure_common import AssureError
from scripts.assure_identity import generation_marker
from scripts.assure_probe_policy import (
    require_valid_probe_policy,
    validate_probe_policy,
)

PROBE_SOURCE = (
    generation_marker("//")
    + "\nimport { expect, test } from 'vitest'\n"
    "import { login } from '../../../src/auth'\n"
    "test('login success failure boundary', () => {\n"
    "  expect(login()).toBe(true)\n"
    "})\n"
)


class ProbePolicyTests(unittest.TestCase):
    def make_root(self) -> Path:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(
            lambda: __import__("shutil").rmtree(root, ignore_errors=True)
        )
        product = root / "src" / "auth.ts"
        product.parent.mkdir()
        product.write_text(
            "export function login() { return true }\n",
            encoding="utf-8",
        )
        return root

    def manifest(self, verification: dict) -> dict:
        return {
            "schema_version": 1,
            "baseline": {
                "status": "approved",
                "verification_policy": "functional-probes-v1",
            },
            "sections": [{
                "id": "auth",
                "name": "Authentication",
                "scenarios": [{
                    "id": "auth.login",
                    "name": "Login",
                    "risk": "critical",
                    "verification": verification,
                }],
            }],
        }

    def functional_probe(self) -> dict:
        return {
            "mode": "automated",
            "strategy": "functional-probe",
            "probe": {
                "entry_points": ["src/auth.ts#login"],
                "cases": ["success", "failure", "boundary"],
                "assertions": ["result", "side-effects"],
            },
            "tests": [{
                "runner": "vitest",
                "args": ["run", ".assure/probes/auth/login.test.ts"],
                "selector": "accepts valid and rejects invalid credentials",
                "sha256": hashlib.sha256(
                    PROBE_SOURCE.encode("utf-8")
                ).hexdigest(),
            }],
        }

    def write_probe(self, root: Path) -> None:
        probe = root / ".assure" / "probes" / "auth" / "login.test.ts"
        probe.parent.mkdir(parents=True)
        probe.write_text(PROBE_SOURCE, encoding="utf-8")

    def test_valid_functional_probe_requires_real_file_and_evidence(self):
        root = self.make_root()
        self.write_probe(root)

        validation = validate_probe_policy(
            self.manifest(self.functional_probe()),
            root,
        )

        self.assertTrue(validation.valid)
        self.assertEqual(validation.probe_count, 1)

    def test_missing_probe_file_is_rejected(self):
        root = self.make_root()

        validation = validate_probe_policy(
            self.manifest(self.functional_probe()),
            root,
        )

        self.assertFalse(validation.valid)
        self.assertIn("probe file is missing or unsafe", str(validation.errors))

    def test_placeholder_probe_file_is_rejected(self):
        root = self.make_root()
        probe = root / ".assure" / "probes" / "auth" / "login.test.ts"
        probe.parent.mkdir(parents=True)
        probe.write_text("export {}\n", encoding="utf-8")

        validation = validate_probe_policy(
            self.manifest(self.functional_probe()),
            root,
        )

        self.assertFalse(validation.valid)
        self.assertIn("no executable test body", str(validation.errors))
        self.assertIn("no test declaration", str(validation.errors))
        self.assertIn("no result assertion", str(validation.errors))
        self.assertIn("sha256 does not match", str(validation.errors))

    def test_probe_changed_after_approval_is_rejected(self):
        root = self.make_root()
        self.write_probe(root)
        manifest = self.manifest(self.functional_probe())
        probe = root / ".assure" / "probes" / "auth" / "login.test.ts"
        probe.write_text(PROBE_SOURCE + "// changed\n", encoding="utf-8")

        validation = validate_probe_policy(manifest, root)

        self.assertFalse(validation.valid)
        self.assertIn("sha256 does not match", str(validation.errors))

    def test_inline_firestore_fake_requires_stateful_contract(self):
        root = self.make_root()
        probe = root / ".assure" / "probes" / "auth" / "login.test.ts"
        probe.parent.mkdir(parents=True)
        source = (
            PROBE_SOURCE
            + "\nvi.mock('firebase/firestore', () => ({ getDocs: vi.fn() }))\n"
        )
        probe.write_text(source, encoding="utf-8")
        verification = self.functional_probe()
        verification["tests"][0]["sha256"] = hashlib.sha256(
            source.encode("utf-8")
        ).hexdigest()

        validation = validate_probe_policy(self.manifest(verification), root)

        self.assertFalse(validation.valid)
        self.assertIn("stateful read-after-write contract", str(validation.errors))

    def test_probe_without_required_cases_and_assertions_is_rejected(self):
        root = self.make_root()
        self.write_probe(root)
        verification = self.functional_probe()
        verification["probe"]["cases"] = ["success"]
        verification["probe"]["assertions"] = ["result"]

        validation = validate_probe_policy(
            self.manifest(verification),
            root,
        )

        self.assertFalse(validation.valid)
        self.assertIn("failure", str(validation.errors))
        self.assertIn("boundary", str(validation.errors))
        self.assertIn("side-effects", str(validation.errors))

    def test_uncovered_without_probe_attempt_is_rejected(self):
        root = self.make_root()

        validation = validate_probe_policy(
            self.manifest({"mode": "uncovered"}),
            root,
        )

        self.assertFalse(validation.valid)
        self.assertIn("no probe_attempt evidence", str(validation.errors))

    def test_unavailable_probe_requires_structured_attempt_evidence(self):
        root = self.make_root()
        verification = {
            "mode": "uncovered",
            "probe_attempt": {
                "entry_points": ["native/device.ts#readSensor"],
                "strategies": ["direct-call", "boundary-spy"],
                "blocker": "cannot-observe-outcome",
                "reason": "The result requires physical sensor behavior.",
                "resolution": {
                    "capability": "physical-sensor",
                    "status": "not-applicable",
                    "reason": "Physical sensor behavior cannot be virtualized.",
                },
            },
        }

        validation = validate_probe_policy(
            self.manifest(verification),
            root,
        )

        self.assertTrue(validation.valid)
        self.assertEqual(validation.unavailable_count, 1)

    def test_recoverable_gap_cannot_be_approved_without_capability_resolution(self):
        root = self.make_root()
        verification = {
            "mode": "uncovered",
            "probe_attempt": {
                "entry_points": ["src/auth.ts#login"],
                "strategies": ["dom-render"],
                "blocker": "unsupported-runner",
                "reason": "DOM runner is missing.",
            },
        }

        validation = validate_probe_policy(self.manifest(verification), root)

        self.assertFalse(validation.valid)
        self.assertIn("capability resolution is missing", str(validation.errors))

    def test_tampered_or_stale_capability_overlay_is_rejected(self):
        root = self.make_root()
        source_lock = '{"lockfileVersion":3}\n'
        (root / "package-lock.json").write_text(source_lock, encoding="utf-8")
        overlay = root / ".assure" / "capabilities" / "node"
        overlay.mkdir(parents=True)
        (overlay / "package.json").write_text("{}\n", encoding="utf-8")
        (overlay / "package-lock.json").write_text("{}\n", encoding="utf-8")
        (overlay / "metadata.json").write_text(
            json.dumps({
                "package_lock_sha256": "0" * 64,
                "source_package_lock_sha256": "1" * 64,
            }),
            encoding="utf-8",
        )

        validation = validate_probe_policy(
            self.manifest({
                "mode": "uncovered",
                "probe_attempt": {
                    "entry_points": ["src/auth.ts#login"],
                    "strategies": ["dom-render"],
                    "blocker": "unsupported-runner",
                    "reason": "The user declined adapter preparation.",
                    "resolution": {
                        "capability": "react-dom-execution",
                        "status": "declined",
                        "reason": "Dependency download was declined.",
                    },
                },
            }),
            root,
        )

        self.assertFalse(validation.valid)
        self.assertIn("integrity check failed", str(validation.errors))
        self.assertIn("stale for the current project", str(validation.errors))

    def test_require_valid_policy_raises_before_verification(self):
        root = self.make_root()

        with self.assertRaisesRegex(
            AssureError,
            "uncovered scenario has no probe_attempt evidence",
        ):
            require_valid_probe_policy(
                self.manifest({"mode": "uncovered"}),
                root,
            )

    def test_current_policy_rejects_project_owned_automated_test(self):
        root = self.make_root()
        manifest = self.manifest({
            "mode": "automated",
            "tests": [{
                "runner": "vitest",
                "args": ["run", "tests/login.test.ts"],
                "selector": "login",
            }],
        })
        manifest["baseline"]["verification_policy"] = (
            "assure-generated-probes-v2"
        )

        validation = validate_probe_policy(manifest, root)

        self.assertFalse(validation.valid)
        self.assertIn(
            "every automated scenario must use an Assure-generated",
            str(validation.errors),
        )


if __name__ == "__main__":
    unittest.main()
