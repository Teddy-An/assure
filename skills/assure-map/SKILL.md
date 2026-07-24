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
9. Map existing tests before creating Assure-owned functional probes. Record
   the test command and selector that prove each mapping.
10. For every scenario not proven by an existing test, analyze its real entry
    point, accepted input, rejection conditions, observable output, state
    transition, authorization boundary, and outbound side effects. Do not
    classify a software behavior as manual merely because it uses a database,
    authentication provider, cloud SDK, API, queue, payment service, or other
    external dependency.
11. Create the smallest project-specific functional probe under
    `.assure/probes/` that executes the real product code with controlled
    success, failure, and boundary inputs. Replace only unsafe outbound
    boundaries with deterministic in-memory fakes, record attempted effects,
    and assert both required effects and forbidden effects. Never change
    production code.
12. Prefer the project's existing test runner for probes. A missing Docker
    daemon, emulator, browser driver, test account, or optional helper is not
    enough to leave a scenario manual or uncovered. Use helpers when available;
    otherwise exercise the nearest real code boundary through the Assure-owned
    probe.
13. Mark a probe automated only when it executes behavior and asserts an
    observable result. Static source inspection alone is supporting evidence,
    never a passing functional result. Reserve manual verification for
    irreducibly physical, perceptual, legal, or human-consent outcomes that
    cannot be represented by controlled inputs and observable outputs.
14. Follow `references/functional-probes.md` for probe design and safety. For
    generated probes, follow the project's existing test conventions. Prove
    sensitivity with a controlled mutation in an isolated workspace and
    restore it.
15. If a test reveals an existing defect, report it. Do not fix production code
    without a separate user request.
16. Record added, changed, deleted, uncovered, manual, and excluded scenarios
    with risk levels for the final report.
17. Write baseline status `approved`, record the current Git commit as
    provenance, record the deterministic `source_snapshot`, and set
    `baseline.verification_policy` to `functional-probes-v1`. Continue directly
    to verification. A matching snapshot is current even when files are
    uncommitted.

Read `references/manifest-format.md` before creating or editing the manifest.
Read `references/functional-probes.md` before creating a probe or classifying
an executable software behavior as manual or uncovered.

## Red flags

- Reading the whole repository before deterministic discovery
- Treating an adapter failure as a harmless warning
- Modifying production code to make a generated test pass
- Treating an external dependency or missing helper as proof that a software
  behavior requires a person
- Passing a scenario from static inspection without executing the behavior
- Calling a draft or partial list complete
- Pausing for routine approval instead of returning a result

Any red flag means stop and return to the relevant workflow step.
