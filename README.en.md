# Assure

**Go beyond passing tests and verify full-product release readiness.**

Assure is a Codex plugin that discovers product features and user scenarios,
connects them to existing tests, exposes missing verification, runs the full
registered baseline, and produces an evidence-based release verdict.

**English** | [한국어](README.md)

> **Early beta:** Assure is usable today, but its manifest format and
> installation flow may change.

## Why use Assure?

A test runner tells you **whether the tests you registered passed**.

A release decision needs answers to broader questions:

- Are the product's important features and user journeys represented?
- Which features still have no verification?
- Does the baseline still match the current source?
- Which checks require a person or a real environment?
- Considering risk and unresolved evidence, is the product ready to release?

Assure turns those questions into a repeatable, full-project verification
baseline.

```text
Discover features → Define scenarios → Map existing tests → Expose gaps
                  → Run the full baseline → Produce a risk-based verdict
```

## What makes it different?

| | Test runner | One-off agent verification | Assure |
|---|---|---|---|
| Starts from | Existing tests | Current request and conversation | Product features and user scenarios |
| Scope | Tests that were invoked | Scope selected in the session | Entire registered baseline |
| Missing coverage | Invisible | Easy to overlook | Explicitly marked `uncovered` |
| Manual checks | Managed elsewhere | Left in conversation | Stored in the baseline and results |
| Change tracking | Test-result focused | Lost with the session | Git plus a source snapshot |
| Execution safety | Depends on the host | Depends on the approach | Assure-owned temporary copy |
| Final output | Pass/fail | Explanation or code changes | Risk-based release verdict |

Assure does not replace Vitest, Jest, pytest, or CI. It adds **verification
scope, visible gaps, manual evidence, and release decisions** on top of them.

## One request, end to end

Open a project in Codex and ask:

```text
Run Assure for this project.
```

Assure automatically follows the workflow required by the project state:

1. Inspect the project structure and test environment.
2. Organize user scenarios by product feature.
3. Map existing tests before generating anything.
4. Add missing tests only when they can be generated safely.
5. Record the current source snapshot as the verification baseline.
6. Run the complete registered automated population.
7. Report manual checks and uncovered scenarios.
8. Return a release verdict.

Assure does not automatically edit production code. When a test exposes an
existing defect, Assure reports it as verification evidence.

## Example result

```text
Release verdict: blocked

| Result | Count |
|---|---:|
| Passed | 18 |
| Failed | 1 |
| Confirm | 2 |
| Unverified | 1 |

| No. | Risk | Section | ID | Scenario | Mode | Result | Detail |
|---:|---|---|---|---|---|---|---|
| 1 | critical | Payments | `payments.refund-idempotency` | Refunds are idempotent | Automated | Failed | Exit code 1 |
| 2 | critical | Security | `security.admin-access` | Confirm administrator access | Manual | Confirm | Confirmation pending |
```

Each scenario has one of these states:

| Status | Meaning |
|---|---|
| `O` | Automated verification passed or a manual check was confirmed |
| `X` | Verification failed |
| `👁` | Manual confirmation is pending |
| `?` | Environment, permission, data, or missing coverage prevented a conclusion |
| `—` | Explicitly excluded with a reason and approver |

The final verdict is `releasable`, `blocked`, `approval-required`, or `warning`
according to scenario risk and unresolved evidence.

## Safe execution

Assure's safety principles apply to every execution provider.

- Run automated checks from an Assure-owned temporary project copy.
- Never run tests from the original working tree or edit production code.
- Do not copy or inherit `.env` files, cloud credentials, or private keys.
- Prepare lockfile-pinned dependencies only inside the temporary copy.
- Disable package lifecycle scripts and binary links.
- Execute only supported test runners with validated argument arrays.
- Block ordinary network access during test execution.
- Terminate child processes when a timeout occurs.
- Remove only temporary directories created by Assure.

When a healthy Docker or Podman daemon is available, Assure prefers it for
stronger isolation. Without one, Assure remains functional through its own
`local-isolated` runner.

External tools are optional providers, not requirements for Assure to work.

## Run a specific workflow

Update or create the verification map:

```text
Update this project's Assure verification map.
```

Run the current approved baseline:

```text
Run the approved full verification baseline.
```

## Requirements

- Git
- Python 3.9 or newer
- A Codex CLI version that provides `codex plugin`
- A Git repository for the project being verified
- The project's test runner and lockfile

Docker and Podman are optional.

## Installation

Assure is currently installed through a local Codex marketplace.

```bash
git clone https://github.com/Teddy-An/assure.git \
  ~/codex-marketplaces/assure-local/plugins/assure
mkdir -p ~/codex-marketplaces/assure-local/.agents/plugins
```

<details>
<summary>Show marketplace.json</summary>

Create
`~/codex-marketplaces/assure-local/.agents/plugins/marketplace.json`:

```json
{
  "name": "assure-local",
  "interface": {
    "displayName": "Assure Local"
  },
  "plugins": [
    {
      "name": "assure",
      "source": {
        "source": "local",
        "path": "./plugins/assure"
      },
      "policy": {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL"
      },
      "category": "Developer Tools"
    }
  ]
}
```

</details>

Register the marketplace and install the plugin:

```bash
codex plugin marketplace add ~/codex-marketplaces/assure-local
codex plugin add assure@assure-local
```

Start a new Codex thread after installation so the Assure skills are loaded.

## Project files

```text
.assure/
├── verification-manifest.yaml  # Features, scenarios, risks, baseline
├── discovery-index.json        # Full and incremental inventory
├── adapters/                   # Optional read-only collectors
├── artifacts/                  # Automated verification evidence
└── reports/                    # JSON and Markdown results
```

An approved baseline records both Git provenance and a deterministic source
snapshot. When product or test files change, Assure detects the stale baseline
and updates the map before verification.

The verification baseline is stored in
`.assure/verification-manifest.yaml`, and the discovery inventory is stored in
`.assure/discovery-index.json`.

## Current limitations

- Assure is early beta, and its manifest format may change.
- Dynamic structures and custom frameworks may require project adapters.
- Browser usability, real permissions, and production data may remain manual.
- Assure cannot guarantee coverage for structures it cannot discover.
- Failure diagnosis and production fixes are separate from verification.

## Development

```bash
python3 -m unittest discover -s tests -v
```

## License

[MIT License](LICENSE)

Copyright (c) 2026 Teddy An
