# Assure Result Policy

## Scenario status

| Status | Meaning |
|---|---|
| `O` | Automated verification passed or a person explicitly confirmed the manual check |
| `X` | Verification failed |
| `👁` | Manual confirmation remains unanswered |
| `?` | Environment, permission, data, or missing coverage prevented a conclusion |
| `—` | Explicitly excluded with reason, approver, and timestamp |

## Release verdict

| Risk | `X` | `👁` or `?` |
|---|---|---|
| `critical` | blocked | blocked |
| `high` | blocked | approval-required |
| `normal` | warning | warning |

All `O` results and properly approved exclusions produce `releasable`.

## Manual response mapping

| User response | Stored status |
|---|---|
| `confirmed` | `O` |
| `failed` | `X` |
| `indeterminate` | `?` |
| `excluded` with reason and `--actor` naming the approver | `—` |
| no explicit response | `👁` |

## Report order

1. Verdict
2. Execution environment and baseline commit
3. Counts
4. Blocking and indeterminate scenarios
5. Manual checks
6. All section results
7. Exclusions and reasons
8. Artifact directory
