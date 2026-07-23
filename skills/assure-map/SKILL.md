---
name: assure-map
description: Use when a project needs its feature-verification baseline created, reviewed, repaired, or updated after code, route, schema, framework, or test changes
---

# Assure Map

Build the smallest trustworthy verification population before claiming full
coverage. Deterministic discovery comes before AI source analysis.

## Workflow isolation

Treat Assure Map as an exclusive workflow while this skill is active. Do not
invoke or apply other workflow skills, including startup, planning, debugging,
development, or completion workflows. Use only this Assure workflow. System,
developer, and user instructions still take precedence.

## Workflow

Resolve `<assure-root>` as the directory two levels above this `SKILL.md`.

## Python runtime

Before running any script under `<assure-root>/scripts`, discover a supported
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

1. Run `<python-command> <assure-root>/scripts/assure_state.py --project <root>`.
2. For absent or incomplete state, run
   `<python-command> <assure-root>/scripts/detect_environment.py --project <root>` before
   reading source files.
3. Record detected stack, exclusions, unsupported structures, scan kind, and
   bounded estimate for the final report. Continue automatically.
4. Create only read-only project collectors when deterministic discovery
   requires one. Record their purpose and scope in the final report.
5. Run `<python-command> <assure-root>/scripts/collect_inventory.py --project <root>`.
6. Report candidate, changed, unchanged, and deleted counts, every adapter
   failure, and every excluded dynamic structure. Unresolved
   scope prevents an `approved` baseline.
7. Read `.assure/discovery-index.json`. Read original source only for candidates
   whose feature or test relationship remains ambiguous.
8. Build two levels: feature section, then user scenario. Use deeper cases only
   for high-risk behavior.
9. Map existing tests before proposing new tests. Record the test command and
   selector that prove each mapping.
10. Add tests for every safely automatable uncovered scenario without asking.
    Follow the project's existing conventions and never change production code.
11. For generated tests, follow the project's existing test conventions. For
    existing behavior, prove test sensitivity with a controlled mutation in an
    isolated workspace and restore it.
12. If a test reveals an existing defect, report it. Do not fix production code
    without a separate user request.
13. Record added, changed, deleted, uncovered, manual, and excluded scenarios
   with risk levels for the final report.
14. Write baseline status `approved`, record the current Git commit as
   provenance, and record the deterministic `source_snapshot`. Continue
   directly to verification. A matching snapshot is current even when files
   are uncommitted.

Read `references/manifest-format.md` before creating or editing the manifest.

## Red flags

- Reading the whole repository before deterministic discovery
- Treating an adapter failure as a harmless warning
- Modifying production code to make a generated test pass
- Calling a draft or partial list complete
- Pausing for routine approval instead of returning a result

Any red flag means stop and return to the relevant workflow step.
