# Assure

**Go beyond passing tests and verify full-product release readiness.**

Assure is a Codex plugin that discovers product features and user scenarios,
executes real product code with valid, invalid, and boundary inputs, and judges
full-product release readiness without production side effects.

**English** | [한국어](README.md)

| Version identity | Value |
|---|---|
| Assure policy version | `0.2.0-dev` |
| Verification policy | `assure-generated-probes-v2` |
| Probe schema | `2` |
| Generator contract | `assure-llm-probe-v2` |

Installed builds use `<policy-version>+codex.<cachebuster>`. The cachebuster
only makes Codex reload an updated local plugin; the policy version is
`0.2.0-dev`. At runtime Assure computes a distribution SHA-256 from its
scripts and skills, records it in generated probes, and compares it with the
current installation.

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
Inspect environment → Build common Sandbox → Derive feature behavior
                    → Create Assure probes for every scenario
                    → Isolate and run → Judge release
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
| External systems | Real connection or separate environment | Depends on the approach | Replace supported boundaries and reject the rest |
| Final output | Pass/fail | Explanation or code changes | Risk-based release verdict |

Assure uses existing runners such as Vitest, Jest, and pytest, but it never
executes project-owned tests directly as release evidence. Existing tests are
supporting context for expected behavior only. For every automated scenario,
it creates an Assure-owned functional probe that calls real product
code, replaces only unsafe database, identity, payment, messaging, or API
boundaries when supported, and verifies results and effects. It does not
execute a boundary that cannot be replaced safely.

## Core principles

1. **Do not modify production source**: Never change the original worktree or
   production code.
2. **Do not touch production data**: Never read or write production databases,
   storage, or account data.
3. **Do not call production services**: Never send requests to production
   identity, payment, messaging, or external APIs.
4. **Work independently**: Run with a supported OS isolation provider and
   Assure functional probes even without Docker, Podman, emulators, or browser
   drivers. When safely available, use helpers to strengthen isolation and
   evidence realism. If neither a container nor supported OS isolation exists,
   keep the safety contract and report automated execution as Unverified.
5. **Minimize tokens and elapsed work**: Without sacrificing verification
   trust or full scope, use deterministic collectors first, read only necessary
   source and evidence, and avoid repeated commands, analysis, and reporting.
6. **Trace backward from behavior**: Do not read every source file in order.
   Build features and user scenarios from the full inventory, then trace only
   the entry points, state transitions, authorization boundaries, and effects
   needed by each scenario. Deterministic collectors may hash paths and bytes
   across all candidate files for change detection without placing those
   source bodies in model context.
7. **Require execution evidence**: Use static analysis to design verification,
   never to declare a behavioral pass without execution.
8. **Verify outcomes and effects**: Check expected results, exact required
   writes, and the absence of forbidden writes or calls.
9. **Report honestly**: Record attempts and reasons for anything that cannot be
   verified. Reserve human confirmation for physical, perceptual, legal, or
   consent-dependent outcomes.
10. **Regress the complete baseline**: Run every approved feature scenario, not
   only changed files, to detect effects on other functionality.
11. **Prepare once, approve once**: Before any scenario runs, inventory every
   dependency, generated file, permission, command, cleanup, and regeneration
   operation in one complete Sandbox plan. Obtain exactly one approval. After
   approval, perform the entire plan automatically and never prompt or pause
   while tests are running. If declined, do not start tests.

## User execution contract

Assure always enforces these three rules:

1. **Approval happens exactly once before testing.**
   After environment discovery, Assure presents one plan containing the stack,
   dependencies, permissions, Sandbox structure, every `.assure/` write,
   probes, adapters, commands, and cleanup. Approval authorizes the complete
   Sandbox construction and test-preparation procedure. No later item requests
   separate approval.
2. **Probes from an older policy are replaced automatically.**
   If the Assure version, distribution hash, probe schema, or generator
   contract differs, stale Assure-owned files under `.assure/probes/` are
   deleted without another question and regenerated through the current remap
   policy. Project-owned tests are never modified or deleted.
3. **Once testing starts, Assure continues to the final result.**
   Dependency installation, permissions, probe generation, and Sandbox health
   checks finish before testing. During tests, Assure never requests approval
   or another choice. It records Passed, Failed, Unverified, or Confirm results
   and continues to the final report.

### Isolation from other workflows

While Assure runs, use only Assure, Assure Map, and Assure Verify. Repository
documents may provide product constraints, but procedures, prompts, agents,
skills, MCP servers, planning systems, debugging systems, or deep source
analysis workflows referenced by them do not extend the Assure workflow.

Assure cannot override higher-priority system, developer, user, or project
instructions. If one requires an incompatible external workflow, Assure stops
and reports the instruction conflict instead of combining both workflows.

The root `AGENTS.md` and `CLAUDE.md` protect these principles while developing
Assure itself. Assure does not create either file in a target project. Those
files affect the entire project and do not provide runtime isolation for an
installed plugin.

### Enforcement levels

| Level | Applied controls |
|---|---|
| Enforced by code | Temporary copy, original read/write protection, credential stripping, OS network denial, pre-execution permission checks, refusal of unapproved dependency preparation, runner allowlist, outbound fail-closed checks, probe hashes, complete-baseline execution, verdict policy |
| Enforced by skill workflow | Explain preparation targets, reasons, and impact and obtain user approval; behavior-first reverse tracing, existing-test mapping, minimal probe design, token and duplicate-work minimization |
| Higher-priority boundary | Stop Assure and report a conflict when system, developer, user, or project instructions are incompatible |

Safety does not rely on skill prose alone. Deterministic scripts recheck
production-impact and baseline-integrity controls. Anything those scripts
cannot guarantee is Unverified, never Passed.

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
                           └─ Existing tests are context only
                              └─ Use the one approved Sandbox plan
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
                                 ├─ File, entry point, and SHA-256 match
                                 ├─ Success/failure/boundary cases
                                 ├─ Result/effect assertions
                                 └─ Record attempts for unverified items
                                    └─ Record baseline and snapshot
                                                        │
   ┌────────────────────────────────────────────────────┘
   └─ Preflight verification preparation
      ├─ Write and remove an internal temporary file
      ├─ Confirm outside writes and network are blocked
      ├─ Check runner, dependencies, and permissions
      └─ Download, install, or creation required
         ├─ No → continue
         └─ Yes → already covered by Sandbox approval
                   └─ perform preparation automatically
   └─ Execute every approved scenario
      └─ Select execution provider
         ├─ Docker or Podman available → stronger isolation
         └─ No helper
            ├─ Supported OS isolation → Assure local-isolated
            └─ No OS isolation → reject execution as Unverified
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
                           └─ warning
```

## One request, end to end

Open a project in Codex and ask:

```text
Run Assure for this project.
```

Assure presents one Sandbox approval before testing. It shows the detected
stack, runner, lockfiles, every dependency and `.assure/` write, permissions,
commands, cleanup, reason, and impact. That approval authorizes the complete
preparation plan. There are no later approval prompts.

1. Inspect the project structure and test environment.
2. Define the project-wide Sandbox profile and required preparations.
3. Prepare the approved Sandbox and pass its health checks.
4. Organize scenarios by feature and read existing tests only as context.
5. Derive valid, invalid, and boundary inputs and expected outcomes.
6. Create every approved `.assure/` file and probe automatically.
7. Block unsafe external connections and record attempted effects.
8. Record the current source snapshot as the verification baseline.
9. Preflight isolation permissions, temporary paths, and runners; complete all
   approved preparation; then run the complete population without pausing.
10. Report only irreducibly human and uncovered items.

Before execution, Assure inventories the detected stack, test runners,
isolation providers, `.assure` write access, and scenario capabilities. It
does not request administrator privileges globally. Elevation is requested
only for a proven required operation, with its exact target and reason.

For capabilities that require preparation, including React DOM, the one
Sandbox approval creates a locked overlay under `.assure/capabilities`
and applies it only to the temporary project copy. Original package files are
not changed. When no fixed recipe exists, the user's LLM
creates a bounded project-specific preparation plan and adapter, then Assure
requires a health check. Missing built-in installation logic alone is never an
Unverified result.
External stores and identity providers are not baseline verification targets.
Assure uses mocks and an effect ledger to prove that real product logic reaches
the pre-write or pre-send boundary with the exact request, while rejected input
produces no outbound effect.
When a boundary has no built-in adapter, the user's LLM creates a
project-specific adapter under `.assure/adapters/`. Its registry records the
runner, covered boundaries, file SHA-256, and current Assure generation
identity. Only adapters that pass static validation and a Sandbox health check
are injected into the runner.

Test-environment, adapter, mock, and runner failures are not product failures.
They are separated as Unverified preparation failures, while product assertion
failures remain release evidence. Assure-generated Firestore fakes must satisfy
the validated stateful read-after-write contract; obsolete stateless fakes are
rejected during baseline validation.

Assure does not design a separate Sandbox for every feature. It creates one
project-level Sandbox profile, and every functional probe uses the same
isolation, mock, and temporary-data contract. Before product scenarios start,
Assure validates the environment fingerprint, runner startup, network denial,
mock injection, and stateful storage contract. A failed Sandbox health check
produces Unverified infrastructure results, never product failures. No
preparation choice exists after testing begins.

Every Assure-generated test records the creating Assure version, distribution
source SHA-256, probe schema, and generator contract near the start of the
file. Before execution, all four values must match the current installation.
A missing or mismatched marker forces remapping without another prompt.
Stale files under `.assure/probes/` are automatically deleted and regenerated from the
current plugin guide. Project-owned tests remain read-only context and are
never stamped or deleted.

```text
// ASSURE_GENERATED: version=0.2.0-dev distribution_sha256=<sha256> probe_schema=2 generator_contract=assure-llm-probe-v2
```
11. Return a release verdict.

The functional-probe policy cannot pass by name alone. Before baseline recording or
execution, Assure validates the probe file, product-code entry point,
success/failure/boundary cases, and result/side-effect assertions. A scenario
that cannot support a probe must record the strategies attempted and a
technical blocker; otherwise Assure marks the baseline stale and remaps it.

Every test `selector` is passed to the real command as Vitest/Jest `-t` or
pytest `-k`. A failure in another test from a shared probe file is not recorded
as a failure of the selected scenario.

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

Automatic failures include more than an exit code when the runner exposes the
evidence: failure type, stable failure ID, failed test, assertion message,
source location, and passed/failed counts. Repeated failure IDs identify a
common cause across scenarios. Environment failures before test collection are
reported as Unverified rather than product failures.

The final verdict is `releasable`, `blocked`, or `warning`
according to scenario risk and unresolved evidence.

## Safe execution

Assure's safety principles apply to every execution provider.

- Run automated checks from an Assure-owned temporary project copy.
- Never run tests from the original working tree or edit production code.
- Do not copy or inherit `.env` files, cloud credentials, or private keys.
- Preflight internal temporary writes and cleanup plus outside-write and
  network denial before scenario execution.
- Prepare lockfile-pinned dependencies only inside the temporary copy and
  include all of them in the one pre-test Sandbox approval.
- Disable package lifecycle scripts and binary links.
- Execute only supported test runners with validated argument arrays.
- Block ordinary network access during test execution.
- Terminate child processes when a timeout occurs.
- Remove only temporary directories created by Assure.

When a healthy Docker or Podman daemon is available, Assure prefers it. Without
one, Assure uses a supported OS isolation provider for `local-isolated`.
The current built-in local OS provider is macOS `sandbox-exec`. Without a
container or supported OS provider, Assure does not execute automated tests.

External tools are optional providers, not requirements for Assure to work.

### Safety assurance levels

Assure never reports a stronger network guarantee than the active isolation
actually provides.

| Label | Meaning |
|---|---|
| `os-blocked` | External connections are blocked at the OS or container layer, such as Docker or Podman `network none` |
| `runtime-guarded` | Runtime defenses only; insufficient to authorize automated execution |
| `not-run` | Automated verification did not run, so no network guarantee was applied |

Current macOS `local-isolated` uses `sandbox-exec` to restrict writes to the
temporary copy and deny network access, so it is `os-blocked`. Assure does not
run automated tests in a `runtime-guarded`-only state.

```text
Functional probe
├─ Product result and state assertions
├─ Common effect ledger
│  ├─ Required calls, writes, and events
│  └─ Forbidden calls, writes, and events
├─ Runner adapter
│  ├─ Vitest: built-in vi.mock and setup
│  ├─ Jest: currently Unverified when outbound boundaries exist
│  ├─ pytest: currently Unverified when outbound boundaries exist
│  └─ Other: reject unsupported runners
├─ Runtime guard
│  ├─ Stripped credentials
│  ├─ Separate HOME
│  └─ Blocked HTTP, WebSocket, and SDK boundaries
└─ Execution provider
   ├─ Docker or Podman → os-blocked
   ├─ macOS local-isolated → os-blocked
   └─ No supported OS isolation → reject execution
```

Assure does not reimplement every language or external SDK. Built-in automatic
boundary replacement currently covers Firebase, fetch, WebSocket, and Node
HTTP/HTTPS under Vitest. When an outbound boundary is detected in Jest or
pytest, Assure rejects execution and reports Unverified because no official
safe adapter exists. It never reports broader support than it implements.

```text
Outbound boundary found
├─ Official runner adapter   → replace and record effects
├─ Existing Vitest mock      → preserve, connect, and record
└─ No official replacement   → reject and record Unverified evidence
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
available. Assure-owned probes use supported OS isolation without them, and a
missing helper or test account alone is not a reason for manual verification.
When safe OS isolation itself is unavailable, Assure reports Unverified rather
than moving the check to manual execution.

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
├── sandbox-profile.json         # Project-wide Sandbox contract and environment fingerprint
├── verification-manifest.yaml  # Features, scenarios, risks, baseline
├── discovery-index.json        # Full and incremental inventory
├── adapters/                   # LLM-generated Sandbox adapters and registry
├── probes/                     # Assure-owned project-specific functional checks
├── artifacts/                  # Automated verification evidence
└── reports/                    # JSON and Markdown results
```

An approved baseline records Git provenance, a deterministic source snapshot,
and the SHA-256 of every functional probe. When product, test, or probe files
change, Assure detects the stale baseline and updates the map before
verification.

The verification baseline is stored in
`.assure/verification-manifest.yaml`, and the discovery inventory is stored in
`.assure/discovery-index.json`.

## Current limitations

- Assure is early beta, and its manifest format may change.
- Unsupported dynamic structures remain unresolved; project-provided discovery
  adapters are never executed.
- Built-in local OS isolation without a container currently supports macOS
  `sandbox-exec`.
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
