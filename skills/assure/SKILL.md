---
name: assure
description: Use when the user wants Assure to prepare, update, and run trustworthy full-project release verification without choosing a sub-workflow
---

# Assure

Select the required Assure workflow; do not perform mapping or verification
inside this dispatcher.

## Workflow isolation

Treat Assure as an exclusive workflow while this skill or a routed Assure
skill is active. Do not invoke or apply other workflow skills, including
startup, planning, debugging, development, or completion workflows. Use only
the Assure skills explicitly routed below. System, developer, and user
instructions still take precedence.

1. Resolve `<plugin-root>` as `../..` from the directory containing this
   `SKILL.md`. Run:

   ```bash
   PYTHONPATH=<plugin-root>/scripts python3 \
     <plugin-root>/scripts/assure_state.py --project <project-root>
   ```

2. Route by returned `kind`:

   - `approved-current`: use `$assure:assure-verify`.
   - `absent`, `incomplete`, `draft`, `review`, `damaged`, or
     `approved-stale`: use `$assure:assure-map`.

3. After mapping, wait for explicit human approval. Re-run the state command.
   Invoke `$assure:assure-verify` only when it returns `approved-current`.

Never bypass approval because the user is in a hurry. Never copy the map or
verify workflow into this skill.
