# Assure

**Go beyond passing tests and verify full-product release readiness.**

Assure is a Codex plugin that discovers product features and user scenarios,
executes real product code with valid, invalid, and boundary inputs, and judges
full-product release readiness without production side effects.

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
Discover features → Derive inputs, outputs, and effects → Map existing tests
                  → Create Assure probes → Isolate and run → Judge release
```

## What makes it different?

| | Test runner | One-off agent verification | Assure |
|---|---|---|---|
| Starts from | Existing tests | Current request and conversation | Product features and user scenarios |
| Scope | Tests that were invoked | Scope selected in the session | Entire registered baseline |
| Missing coverage | Invisible | Easy to overlook | First exercised with an Assure probe |
| Manual checks | Managed elsewhere | Left in conversation | Stored in the baseline and results |
| Change tracking | Test-result focused | Lost with the session | Git plus a source snapshot |
| Execution safety | Depends on the host | Depends on the approach | Assure-owned temporary copy |
| External systems | Real connection or separate environment | Depends on the approach | Only unsafe boundaries are replaced |
| Final output | Pass/fail | Explanation or code changes | Risk-based release verdict |

Assure uses Vitest, Jest, pytest, and other existing runners, but it does not
send a scenario directly to manual confirmation just because no existing test
covers it. It creates an Assure-owned functional probe that calls real product
code, replaces only unsafe database, identity, payment, messaging, or API
boundaries, and verifies results and effects.

## Core principles

1. **Do not modify production source**: Never change the original worktree or
   production code.
2. **Do not touch production data**: Never read or write production databases,
   storage, or account data.
3. **Do not call production services**: Never send requests to production
   identity, payment, messaging, or external APIs.
4. **Work independently**: Run with Assure isolation and functional probes even
   without Docker, Podman, emulators, or browser drivers. When safely available,
   use them as providers that strengthen isolation and evidence realism.
5. **Minimize tokens and elapsed work**: Without sacrificing verification
   trust or full scope, use deterministic collectors first, read only necessary
   source and evidence, and avoid repeated commands, analysis, and reporting.
6. **Trace backward from behavior**: Do not read every source file in order.
   Build features and user scenarios from the full inventory, then trace only
   the entry points, state transitions, authorization boundaries, and effects
   needed by each scenario.
7. **Require execution evidence**: Use static analysis to design verification,
   never to declare a behavioral pass without execution.
8. **Verify outcomes and effects**: Check expected results, exact required
   writes, and the absence of forbidden writes or calls.
9. **Report honestly**: Record attempts and reasons for anything that cannot be
   verified. Reserve human confirmation for physical, perceptual, legal, or
   consent-dependent outcomes.
10. **Regress the complete baseline**: Run every approved feature scenario, not
   only changed files, to detect effects on other functionality.

## Verification flow

```text
User request
└─ Inspect Assure state
   ├─ Approved baseline is current ───────────────────────┐
   └─ Baseline absent, damaged, or changed                │
      └─ Collect project inventory                        │
         ├─ Stack, routes, schemas, and test relationships│
         └─ Do not read every source body sequentially    │
            └─ Build feature structure                    │
               └─ Feature                                 │
                  └─ User scenario                        │
                     └─ Trace required code backward      │
                        ├─ Real entry point                │
                        ├─ Accept/reject conditions        │
                        ├─ State transitions              │
                        ├─ Authorization boundaries       │
                        └─ Outbound effects               │
                           │                              │
                           ├─ Existing test proves it     │
                           │  └─ Map existing test        │
                           │                              │
                           └─ Existing test is insufficient
                              └─ Create Assure probe
                                 ├─ Success input
                                 ├─ Failure input
                                 ├─ Boundary input
                                 ├─ Execute real product code
                                 └─ Replace only unsafe boundaries
                                    with fakes or spies
                                       ├─ Assert result and state
                                       ├─ Assert required effects
                                       └─ Assert forbidden effects
                                             │
                              ┌──────────────┘
                              └─ Validate probe policy
                                 ├─ File and entry point exist
                                 ├─ Success/failure/boundary cases
                                 ├─ Result/effect assertions
                                 └─ Record attempts for unverified items
                                    └─ Approve baseline and snapshot
                                                        │
   ┌────────────────────────────────────────────────────┘
   └─ Execute every approved scenario
      └─ Select execution provider
         ├─ Docker or Podman available → stronger isolation
         └─ No helper → Assure local-isolated
            └─ Separate source, credentials, and production network
               └─ Collect evidence for every scenario
                  ├─ Passed
                  ├─ Failed
                  ├─ Confirm
                  ├─ Unverified
                  └─ Excluded
                     └─ Feature tree plus complete result table
                        └─ Release verdict
                           ├─ releasable
                           ├─ blocked
                           ├─ approval-required
                           └─ warning
```

## One request, end to end

Open a project in Codex and ask:

```text
Run Assure for this project.
```

Assure automatically follows the workflow required by the project state:

1. Inspect the project structure and test environment.
2. Organize user scenarios by product feature.
3. Map existing tests before generating anything.
4. Derive valid, invalid, and boundary inputs and expected outcomes.
5. Create project-specific functional probes under `.assure/probes/`.
6. Block unsafe external connections and record attempted effects.
7. Record the current source snapshot as the verification baseline.
8. Run the complete automated population in the isolated copy.
9. Report only irreducibly human and uncovered items.
10. Return a release verdict.

The functional-probe policy cannot pass by name alone. Before approval or
execution, Assure validates the probe file, product-code entry point,
success/failure/boundary cases, and result/side-effect assertions. A scenario
that cannot support a probe must record the strategies attempted and a
technical blocker; otherwise Assure marks the baseline stale and remaps it.

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
| 1 | critical | Authentication | `authentication.login` | Sign in with valid credentials | Automated | Failed | Exit code 1 |
| 2 | high | Interface | `interface.visual-review` | Review the visual quality of key screens | Manual | Confirm | Reviewer confirmation pending |
```

Each scenario has one of these results:

| Result | Meaning |
|---|---|
| Passed | Automated verification passed or a reviewer confirmed a manual check |
| Failed | Verification failed |
| Confirm | Human confirmation is required and remains pending |
| Unverified | Environment, permission, data, or missing coverage prevented a conclusion |
| Excluded | Removed from verification with a recorded reason and approver |

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

### Safety assurance levels

Assure never reports a stronger network guarantee than the active isolation
actually provides.

| Label | Meaning |
|---|---|
| `os-blocked` | External connections are blocked at the OS or container layer, such as Docker or Podman `network none` |
| `runtime-guarded` | Known outbound boundaries are guarded with a temporary HOME, stripped credentials, blocking proxies, and supported runtime mocks |
| `not-run` | Automated verification did not run, so no network guarantee was applied |

`local-isolated` is `runtime-guarded`, not an OS-level network block. Without
OS isolation, Assure replaces supported runtime boundaries fail-closed. If it
cannot build a safe replacement for an outbound scenario, it does not execute
that scenario and reports it as Unverified.

```text
Functional probe
├─ Product result and state assertions
├─ Common effect ledger
│  ├─ Required calls, writes, and events
│  └─ Forbidden calls, writes, and events
├─ Runner adapter
│  ├─ Vitest: built-in vi.mock and setup
│  ├─ Jest: project mock or dedicated jest.mock and setup
│  ├─ pytest: project fixture or dedicated monkeypatch
│  └─ Other: project mock or Assure-owned adapter
├─ Runtime guard
│  ├─ Stripped credentials
│  ├─ Separate HOME
│  └─ Blocked HTTP, WebSocket, and SDK boundaries
└─ Execution provider
   ├─ Docker or Podman → os-blocked
   └─ local-isolated → runtime-guarded
```

Assure does not reimplement every language or external SDK. It uses the
smallest adapter needed for the discovered runner and product boundary.
Existing project mocks are preserved. An adapter records controlled responses,
targets, payloads, counts, and blocking decisions—not product decision logic.

```text
Outbound boundary found
├─ Official runner adapter   → replace and record effects
├─ Existing project mock     → preserve, connect, and record
├─ Small adapter is feasible → create it under .assure
└─ No safe replacement       → forbid the call and record Unverified evidence
```

## Functional verification without helper tools

Assure is not tied to Firebase, a particular database, OAuth, an internal
identity system, or any other technology. It derives input conditions, success
and rejection paths, state changes, and outbound effects from feature code,
then executes the real code path.

For a system with login, it checks successful authentication and session
creation with an accepted value, then rejection without a session for invalid
or unauthorized values. For data persistence, it checks that valid input is
written exactly once and that invalid or unauthorized requests cause no write.

Assure never connects these probes to a production database or identity
provider. In the isolated run, only unsafe boundaries are replaced with
in-memory fakes or spies. The probe verifies both:

- the user-visible result and state transition;
- required outbound effects and the absence of forbidden effects.

Docker, emulators, and browser drivers can provide stronger evidence when
available. Assure-owned probes must still work without them, and a missing
helper or test account alone is not a reason for manual verification.

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
├── probes/                     # Assure-owned project-specific functional checks
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
- Physical-device perception, human visual judgment or consent, and legally
  controlled real-world actions may remain manual when they cannot be
  represented by controlled input and observable output.
- Assure cannot guarantee coverage for structures it cannot discover.
- Failure diagnosis and production fixes are separate from verification.

## Development

```bash
python3 -m unittest discover -s tests -v
```

## License

[MIT License](LICENSE)

Copyright (c) 2026 Teddy An
