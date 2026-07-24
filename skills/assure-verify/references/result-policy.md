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
2. Metadata table: environment, baseline commit, project root, report path
3. Status-count table
4. Complete scenario result table
5. Artifact directory

Show each scenario exactly once. Summarize blocking and unresolved results in
the verdict and status-count table instead of repeating those rows separately.

Keep the scenario columns stable:

| No. | Risk | Section | ID | Scenario | Mode | Result | Detail |
|---:|---|---|---|---|---|---|---|

Translate internal status codes for human-facing tables:

| Internal | English | Korean |
|---|---|---|
| `O` | Passed | 통과 |
| `X` | Failed | 실패 |
| `?` | Unverified | 미검증 |
| `👁` | Confirm | 확인 |
| `—` | Excluded | 제외 |
