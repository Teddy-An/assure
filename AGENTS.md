# Assure repository rules

- Treat README safety, isolation, evidence, efficiency, and reporting claims as
  contracts. Every unconditional claim must have an implementation and a
  regression test; otherwise label it as a limitation or future direction.
- Keep Assure self-contained. Do not add dependencies on external workflow
  skills, code-analysis plugins, MCP servers, agents, or remote prompt sources.
- Do not combine Assure runtime verification with another workflow system.
  Repository maintenance may use platform-required packaging and validation
  tools, but they must not become Assure runtime dependencies.
- Prefer deterministic scripts and compact outputs before model-driven source
  reading. Do not introduce whole-repository semantic analysis as a required
  step.
- Never weaken temporary-copy execution, credential stripping, outbound
  fail-closed behavior, or probe-policy validation to improve pass rates.
- Complete preparation and isolation preflight before scenario execution.
  Present one complete Sandbox plan and obtain exactly one explicit approval.
  That approval covers every listed dependency, `.assure/` file, generated
  probe, adapter, permission, bootstrap, cleanup, and regeneration operation.
  Never ask again after that approval or while tests are running.
- Run `assure_capabilities.py` before mapping to inspect the stack, runner,
  isolation, write permission, and executable capabilities. Administrator
  access is not a default requirement; request it only for a proven required
  operation that reports `permission-required`.
- Prepare supported capabilities only under `.assure/capabilities` under the
  one Sandbox approval and apply them only to the temporary copy. Never report an
  unimplemented provider as ready.
- Create one project-level `.assure/sandbox-profile.json` before probes. All
  tests use that common Sandbox contract; never design one Sandbox per feature.
  A changed environment fingerprint or failed Sandbox health check must stop
  product scenarios before they can be classified as product failures.
- If the user declines the one Sandbox plan, do not begin testing. Report the
  affected coverage as Unverified. There are no per-capability declines after
  the plan is approved.
- Treat stale Assure-owned probes as invalid implementation artifacts. Delete
  and regenerate them automatically under the existing Sandbox approval.
- Classify test-environment, runner, adapter, and mock failures separately from
  product assertion failures.
- Never execute project-owned tests as Assure release evidence. Use them only
  as behavioral context, and generate a current version-stamped
  `.assure/probes` test for every automated scenario.
- Pass every manifest test selector to the real runner command. Preserve
  compact structured failure evidence in reports and never let an unrelated
  failure from a shared test file contaminate another scenario.
- Keep generated project files under `.assure/`. Do not require Assure to add
  `AGENTS.md`, `CLAUDE.md`, or other workflow-control files to a target project.
- Preserve the user's source and data. Tests for destructive behavior must use
  temporary fixtures owned by the test.
- Run the complete unit test suite, skill validation, plugin validation, and
  `git diff --check` before publishing changes.
