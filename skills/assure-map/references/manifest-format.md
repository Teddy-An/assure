# Assure Manifest Format

The file is `.assure/verification-manifest.yaml`.

Required root fields:

- `schema_version`: integer `1`
- `baseline.status`: `draft`, `review`, or `approved`
- `baseline.commit`: full Git commit when approved
- `baseline.approved_at`: ISO 8601 timestamp when approved
- `baseline.verification_policy`: `assure-generated-probes-v2` when approved
- `sections`: ordered list

Each section requires `id`, `name`, and `scenarios`.
Each scenario requires `id`, `name`, `risk`, and `verification`.

Risk is `critical`, `high`, or `normal`.
Verification mode is `automated`, `manual`, `uncovered`, or `excluded`.

Every automated verification requires an Assure-owned functional probe.
Project-owned tests may inform the LLM but are never registered or executed as
release evidence:

```yaml
mode: automated
strategy: functional-probe
probe:
  entry_points: [src/auth/login.ts#login]
  cases: [success, failure, boundary]
  assertions: [result, side-effects]
tests:
  - runner: vitest
    args: [run, .assure/probes/auth/login.assure.test.ts]
    selector: accepts valid credentials and rejects invalid credentials
    sha256: <sha256-of-probe-file>
```

Firestore Rules probes use the isolated Rules runner:

```yaml
mode: automated
strategy: functional-probe
probe:
  entry_points: [firestore.rules#rules]
  cases: [success, failure, boundary]
  assertions: [result, side-effects]
tests:
  - runner: vitest
    args: [run, .assure/probes/platform/firestore-rules.assure.test.ts]
    selector: enforces role based Firestore access
    sha256: <sha256-of-probe-file>
```

This probe replaces the external store boundary with an Assure-owned Mock and
effect ledger, uses only controlled test values, and
keeps external network access blocked.

Store functional probes only under `.assure/probes/`. Assure copies that
directory into its temporary execution snapshot; it does not copy other
`.assure` state. Every entry point uses `<project-relative-file>#<symbol>`.
A probe must execute product behavior, cover success, failure, and boundary
cases, and assert both the observable result and outbound side effects.
Placeholder files and static source inspection are not automated verification.
Record the SHA-256 of every functional probe test file. Approval and execution
must fail if a probe changes without remapping.

Manual verification requires a non-empty `instructions` list and is reserved
for physical, perceptual, legal, or human-consent outcomes that cannot be
represented by controlled input and observable output. A missing external
service or optional helper does not qualify. Excluded verification requires
`reason`, `approved_by`, and `approved_at`.

An uncovered scenario requires evidence that Assure attempted its own probe:

```yaml
mode: uncovered
probe_attempt:
  entry_points: [native/sensor.ts#readSensor]
  strategies: [direct-call, boundary-spy]
  blocker: cannot-observe-outcome
  reason: The outcome requires physical sensor behavior.
  resolution:
    capability: physical-sensor
    status: not-applicable
    reason: Physical sensor behavior cannot be represented in the Sandbox.
```

Allowed blocker codes are `cannot-observe-outcome`, `no-executable-boundary`,
`unsafe-boundary`, and `unsupported-runner`. Missing Docker, an emulator, a
browser driver, a test account, or an external service is not by itself a
valid blocker.

## Discovery extensions

Project-provided discovery adapters are not executed. Assure uses only its
built-in deterministic collectors so repository code cannot extend or replace
the verification workflow. Record unsupported dynamic structures as unresolved
scope; unresolved scope keeps the baseline unapproved.

Complete example:

```yaml
schema_version: 1
baseline:
  status: approved
  commit: 0123456789abcdef0123456789abcdef01234567
  approved_at: 2026-07-23T12:00:00+09:00
  verification_policy: assure-generated-probes-v2
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
          probe_attempt:
            entry_points: [native/secure-session.ts#readExpiredSession]
            strategies: [direct-call, boundary-spy]
            blocker: cannot-observe-outcome
            reason: The outcome depends on device-controlled secure storage.
            resolution:
              capability: device-secure-storage
              status: not-applicable
              reason: The result cannot be represented safely in the Sandbox.
```
