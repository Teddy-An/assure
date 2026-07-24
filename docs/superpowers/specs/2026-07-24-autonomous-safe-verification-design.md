# Autonomous, Safe Assure Verification

## Goal

Make `$assure:assure` a non-interactive, end-to-end verification workflow by
default. It must produce a final verdict rather than asking the user to select
tests, approve a baseline, commit files, or supply routine environment
decisions. It must never allow an automated test run to contact production
services or mutate the original project.

## Default workflow

1. Detect the project and execution capabilities.
2. Build or incrementally update the verification inventory and baseline.
3. Map existing tests and generate missing tests where this is safe.
4. Automatically approve the generated baseline, recording a source snapshot
   in addition to Git provenance.
5. Provision an isolated test environment and run the complete approved
   population once.
6. Return a localized final verdict. Manual scenarios remain pending in the
   result; they never pause the automated workflow.

The workflow may not modify production code. A test finding remains a result,
not an automatic production fix.

## Safety model

### Source and dependency isolation

- Run tests only from an independent temporary source snapshot.
- Do not mount, symlink, or junction-link the original project, `.env` files,
  credential files, home configuration, or `node_modules` into that snapshot.
- Install dependencies in the snapshot from a pinned cache or approved image,
  with package lifecycle scripts disabled by default.
- Delete only a sandbox directory created and identity-checked by Assure. Do
  not recursively remove a directory containing a reparse point.

### Network and credentials

- Prefer a cross-platform container runtime with network disabled when one is
  healthy, but keep containers optional. Assure must remain independently
  functional through its local-isolated temporary-copy runner.
- Strip credentials and cloud-service environment variables before execution.
- Treat non-interference with the original project and production systems as
  an invariant of every provider, not as a reason to require one provider.
- If neither the preferred provider nor Assure's own isolated runner can
  safely execute a scenario, finish that scenario as unavailable; never run
  tests from the original host project.
- Bootstrap dependencies automatically where permissions allow it. A failed
  bootstrap is a final environment result, not a conversational question.

### Automatic mocks

- Inject an Assure-owned mock setup into the sandbox only; never rewrite user
  test or product files.
- Preserve project mocks when present.
- Auto-mock outbound boundaries such as `fetch`, WebSocket, Node HTTP/HTTPS,
  Firebase Auth, and Firestore with deterministic in-memory or no-op behavior.
- Record injected mocks and conflicts in the summary.
- If a test requires behavior that the automatic mock cannot reproduce, mark
  that scenario `unverifiable`; do not request input mid-run.

### Command execution

- Replace arbitrary `shell=True` manifest commands with validated runner
  adapters and argument arrays.
- Permit only detected/supported test runners and their explicit selectors.

## Baseline identity

Approved baselines store both the Git commit (provenance) and a deterministic
source snapshot hash. A project is current when its relevant product and test
files match the stored hash, even before the user makes a commit. `.assure`
artifacts remain excluded from the source identity.

## Localization

- Detect the process locale once. A Korean locale selects a global `ko`
  default; other locales select `en`.
- Allow `.assure/config.yaml` to override the language per project.
- Keep JSON keys, scenario IDs, and status codes stable. Localize verdicts,
  reports, manual instructions, and assistant-facing summaries.
- Use a single JSON output function. It first writes UTF-8; if stdout cannot
  encode the output, it emits ASCII-escaped JSON rather than raising. This
  works with Windows CP949 consoles and UTF-8 macOS/Linux terminals.

## Results and verdicts

- Treat uncertain prerequisites as result states, not questions.
- Include automatic-mock usage, sandbox provider, bootstrap outcome, and
  unresolved/manual scenario IDs in the summary.
- Preserve the existing risk policy: unresolved critical work blocks release;
  unresolved high-risk work requires approval; unresolved normal work warns.

## Validation

- Unit-test state classification with clean, dirty, and uncommitted snapshots.
- Unit-test command validation and reject shell metacharacters.
- Test automatic mock injection precedence and unsupported mock behavior.
- Test sandbox path validation without symlinks/junctions and with rejected
  reparse points.
- Test JSON output using UTF-8 and a simulated CP949 text stream.
- Forward-test a mocked Firebase project and a project whose external call is
  unsupported; verify that neither contacts a network and both produce final
  summaries.
