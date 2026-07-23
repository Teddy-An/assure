---
name: assure-verify
description: Use when a project has an approved Assure baseline and needs full regression verification, release-readiness evidence, or a deployment gate decision
---

# Assure Verify

Run the approved population completely while keeping model context small.

## Workflow isolation

Treat Assure Verify as an exclusive workflow while this skill is active. Do not
invoke or apply other workflow skills, including startup, planning, debugging,
development, or completion workflows. Use only this Assure workflow. System,
developer, and user instructions still take precedence.

## Workflow

Resolve `<assure-root>` as `../..` from the directory containing this
`SKILL.md`. Use these plugin-root paths even when `<root>` is an external
project.

1. Run
   `python3 <assure-root>/scripts/assure_state.py --project <root>`.
2. Parse the state command's stdout JSON. Continue only for
   `approved-current`. For every other state, stop and direct the user to
   `$assure:assure-map`.
3. Run
   `python3 <assure-root>/scripts/run_verification.py --project <root>` once.
   Do not execute scenario commands individually from the conversation.
4. Parse only the command's stdout JSON summary. A nonzero exit for `blocked`
   or `approval-required` is a verification result, not permission to inspect
   other evidence.
5. Never open files under `.assure/artifacts/` or any artifact, report, or
   summary path returned by the JSON. Artifact paths are identifiers to report,
   not files to read.
6. Present the verdict first, then baseline commit and project root, status
   counts, blocking or unresolved scenario IDs, manual checks, and the Markdown
   report path.
7. For each manual check, accept only an explicit `confirmed`, `failed`,
   `indeterminate`, or `excluded` response. Require an actor for every response,
   and require a reason for `excluded`; for that response, `--actor` identifies
   the approver. Do not infer confirmation.
8. Record an explicit manual response with the same plugin-root runner using
   `--summary <summary_path> --manual-result <scenario-id> --response <response>
   --actor <actor>` and `--reason <reason>` when required. For `excluded`, pass
   the approver as `<actor>`. Parse only its stdout JSON. This updates the
   manual result; it does not authorize a verification rerun or a file read.
9. Do not diagnose failures, rerun commands, edit tests, or edit production
   code.
10. If the user explicitly requests diagnosis, end this workflow and report
    that diagnosis is a separate task. Do not start it inside Assure.

Read `references/result-policy.md` when explaining a status or verdict.

## Red flags

- “The log already exists, so reading it is efficient.”
- “A quick rerun may make the failure disappear.”
- “The likely fix is obvious.”
- “Only the changed feature needs to run.”

Any red flag means stop. Report evidence only.
