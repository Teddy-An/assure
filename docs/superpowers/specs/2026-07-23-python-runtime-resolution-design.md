# Python runtime resolution

## Goal

Make Assure select an available, supported Python 3 runtime before it runs any
Assure helper script. Python 2 is unsupported. When no supported runtime is
available, Assure must ask the user whether to install Python before taking any
installation action.

## Runtime selection

At the start of each Assure workflow, probe runtime candidates in this order:

1. `python3`
2. `python`
3. `py -3`

Use the first candidate whose reported version is Python 3.9 or newer. Store
the selected command for the rest of the workflow and use it consistently for
every command under `scripts/`.

Python 2 and Python 3 versions below 3.9 are rejected with an actionable
explanation. The version floor is 3.9 because the plugin uses modern built-in
generic annotations such as `list[str]`.

## Missing runtime

If no candidate is available, report that Python 3.9 or newer is required and
ask the user whether Assure should install it. Do not install software before
an explicit affirmative response. After an approved installation, rerun
runtime selection and continue only if a supported runtime is found.

## Skill changes

Update the dispatcher, map, and verify skill instructions to use the selected
runtime rather than hard-coded `python3` calls. The instructions must preserve
the existing workflow isolation and approval gates.

## Testing

Extend the repository's contract tests to verify that skills no longer contain
hard-coded `python3` execution commands, require runtime selection before
scripts run, reject Python 2, and require explicit approval before installation.

## Non-goals

This change does not silently install Python, add a package manager dependency,
or change the verification-map and verification-result semantics.
