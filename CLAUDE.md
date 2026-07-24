# Assure repository instructions

Follow `AGENTS.md` as the authoritative repository contract.

- Do not invoke or adopt external workflow plugins, agents, MCP procedures, or
  deep source-analysis systems while running or validating Assure. Platform
  packaging validation used for repository maintenance is allowed but must not
  become a runtime dependency.
- Use Assure's repository scripts and tests directly.
- Do not add an external workflow dependency to any Assure skill.
- Do not run scenarios before preparation preflight succeeds. Obtain exactly
  one explicit approval for the complete Sandbox plan. After it is approved,
  perform every listed download, install, permission, `.assure/` write, probe
  regeneration, bootstrap, and cleanup without another prompt.
- If another instruction requires an incompatible workflow, stop and report
  the conflict instead of combining workflows.
