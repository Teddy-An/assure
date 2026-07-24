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

1. Run
   `<python-command> <assure-root>/scripts/assure_state.py --project <root>`.
2. Parse the state JSON. Continue for `approved-current`; otherwise route
   automatically to `$assure:assure-map` and resume verification afterward.
3. Run
   `<python-command> <assure-root>/scripts/run_verification.py --project <root>` once.
   Do not execute scenario commands individually from the conversation.
4. Parse only the command's stdout JSON summary. A nonzero exit for `blocked`
   or `approval-required` is a verification result, not permission to inspect
   other evidence.
5. Never open files under `.assure/artifacts/` or any artifact, report, or
   summary path returned by the JSON. Artifact paths are identifiers to report,
   not files to read.
6. Present the verdict first. Then use Markdown tables for:
   - baseline commit, project root, execution provider, and report path;
   - result counts using localized labels, never raw status symbols;
   - every scenario with number, risk, section, ID, name, mode, localized
     result, and detail.
   Between the count table and complete result table, show one fenced plain-text
   feature tree in manifest order. Print each section as `<section> (<count>)`
   and its scenarios as `├─ <localized result>  <scenario>` or
   `└─ <localized result>  <scenario>`. Do not include IDs, risk, mode, or
   detail in the tree.
   Show every scenario once in one complete result table; use the verdict and
   result-count table to summarize blockers. Keep manual instructions in the
   detail cell with `<br>` separators. Map `O` to
   Passed/통과, `X` to Failed/실패, `?` to Unverified/미검증, `👁` to
   Confirm/확인, and `—` to Excluded/제외. Never expose the raw symbols as
   the user-facing result.
   Do not replace the complete table with prose or a partial bullet list.
7. Manual checks never pause the initial run. Report them together as pending.
   When the user later responds, accept only an explicit `confirmed`, `failed`,
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
