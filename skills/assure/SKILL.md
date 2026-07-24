---
name: assure
description: Use when the user wants Assure to prepare, update, and run trustworthy full-project release verification without choosing a sub-workflow
---

# Assure

Run Assure end to end without conversational gates.

## Workflow isolation

Treat Assure as an exclusive workflow while this skill or a routed Assure
skill is active. Do not invoke or apply other workflow skills, including
startup, planning, debugging, development, or completion workflows. Use only
the Assure skills explicitly routed below. System, developer, and user
instructions still take precedence.

## Python runtime

Before running any script under `<plugin-root>/scripts`, discover a supported
Python runtime in this exact order:

1. `python3 --version`
2. `python --version`
3. `py -3 --version`

Select the first command that reports Python 3.9 or newer and retain it as
`<python-command>` for the entire workflow. Python 2 and Python 3.8 or older
are unsupported.

If none is available, tell the user that Python 3.9 or newer is required and
ask whether to install it. Do not install Python or change the environment
without explicit user approval. After an approved installation, rerun runtime
discovery; continue only after `<python-command>` is selected.

1. Resolve `<plugin-root>` as `../..` from the directory containing this
   `SKILL.md`. Run:

   ```bash
   PYTHONPATH=<plugin-root>/scripts <python-command> \
     <plugin-root>/scripts/assure_state.py --project <project-root>
   ```

2. Route by returned `kind`:

   - `approved-current`: use `$assure:assure-verify`.
   - `absent`, `incomplete`, `draft`, `review`, `damaged`, or
     `approved-stale`: use `$assure:assure-map`.

3. After mapping, automatically approve the generated source snapshot and
   continue to `$assure:assure-verify` in the same turn. Do not ask the user
   to select tests, approve a baseline, or create a Git commit.
4. Treat Docker, Podman, and other external helpers as optional providers.
   Assure must still run through its own temporary-copy isolation when no
   helper is available. Never run tests from the original project tree.
5. Treat environment, sandbox, mock, manual, and coverage gaps as final result
   states. Always return the best available verdict instead of pausing.
