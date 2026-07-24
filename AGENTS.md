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
  Require explicit user approval before dependency downloads or installs,
  creation or modification of target-project `.assure/` files, or any new
  permission. Never infer preparation approval from a general Assure request.
- Keep generated project files under `.assure/`. Do not require Assure to add
  `AGENTS.md`, `CLAUDE.md`, or other workflow-control files to a target project.
- Preserve the user's source and data. Tests for destructive behavior must use
  temporary fixtures owned by the test.
- Run the complete unit test suite, skill validation, plugin validation, and
  `git diff --check` before publishing changes.
