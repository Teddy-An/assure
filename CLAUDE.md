# Assure repository instructions

Follow `AGENTS.md` as the authoritative repository contract.

- Do not invoke or adopt external workflow plugins, agents, MCP procedures, or
  deep source-analysis systems while running or validating Assure. Platform
  packaging validation used for repository maintenance is allowed but must not
  become a runtime dependency.
- Use Assure's repository scripts and tests directly.
- Do not add an external workflow dependency to any Assure skill.
- Do not run scenarios before preparation preflight succeeds. Ask for explicit
  user approval before downloads, installs, new permissions, or target-project
  `.assure/` file creation or modification.
- If another instruction requires an incompatible workflow, stop and report
  the conflict instead of combining workflows.
