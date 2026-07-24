# Assure Manifest Format

The file is `.assure/verification-manifest.yaml`.

Required root fields:

- `schema_version`: integer `1`
- `baseline.status`: `draft`, `review`, or `approved`
- `baseline.commit`: full Git commit when approved
- `baseline.approved_at`: ISO 8601 timestamp when approved
- `sections`: ordered list

Each section requires `id`, `name`, and `scenarios`.
Each scenario requires `id`, `name`, `risk`, and `verification`.

Risk is `critical`, `high`, or `normal`.
Verification mode is `automated`, `manual`, `uncovered`, or `excluded`.

Automated verification requires:

```yaml
mode: automated
tests:
  - runner: vitest
    args: [run, tests/auth/login.spec.ts]
    selector: valid credentials return access token
```

When an existing project test does not prove the scenario, create an
Assure-owned functional probe:

```yaml
mode: automated
strategy: functional-probe
tests:
  - runner: vitest
    args: [run, .assure/probes/auth/login.assure.test.ts]
    selector: accepts valid credentials and rejects invalid credentials
```

Store functional probes only under `.assure/probes/`. Assure copies that
directory into its temporary execution snapshot; it does not copy other
`.assure` state. A probe must execute product behavior, cover at least a
success or rejection path appropriate to the scenario, and assert observable
output or state. Static source inspection is not an automated verification.

Manual verification requires a non-empty `instructions` list and is reserved
for physical, perceptual, legal, or human-consent outcomes that cannot be
represented by controlled input and observable output. A missing external
service or optional helper does not qualify. Excluded verification requires
`reason`, `approved_by`, and `approved_at`. Uncovered verification has no
additional fields.

## Project adapter contract

An adapter under `.assure/adapters/` must:

- be a Python file or executable and accept `--project <absolute-project-root>`;
- treat the project working directory and product source as read-only;
- exit `0` and write one UTF-8 JSON object to stdout;
- include `items` and `failures` arrays in that object.

Use `items` for discovered structures. Use `failures` for structures the
adapter cannot resolve. On nonzero exit, write a concise reason to stderr.

Complete example:

```yaml
schema_version: 1
baseline:
  status: approved
  commit: 0123456789abcdef0123456789abcdef01234567
  approved_at: 2026-07-23T12:00:00+09:00
sections:
  - id: auth
    name: 인증
    scenarios:
      - id: auth.valid-login
        name: 정상 로그인
        risk: critical
        verification:
          mode: automated
          tests:
            - runner: vitest
              args: [run, tests/auth/login.spec.ts]
              selector: valid credentials return access token
      - id: auth.logout
        name: 로그아웃
        risk: high
        verification:
          mode: manual
          instructions:
            - 로그인한 사용자가 로그아웃 버튼을 누른다.
            - 보호된 화면에 다시 접근할 수 없는지 확인한다.
      - id: auth.expired-session
        name: 만료된 세션 처리
        risk: critical
        verification:
          mode: uncovered
```
