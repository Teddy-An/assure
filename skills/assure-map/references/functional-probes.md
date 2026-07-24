# Assure Functional Probes

Use a functional probe when existing tests do not prove a software scenario.
The probe belongs to Assure, not to production source, and runs only from the
isolated project copy.

## Derive the contract

Trace the scenario to the nearest executable product entry point and record:

- accepted inputs and how a valid value is derived;
- rejection, authorization, and boundary conditions;
- observable return value, rendered state, persisted state, or emitted event;
- outbound writes, messages, payments, uploads, redirects, and network calls;
- effects that must occur and effects that must never occur.

Do not require a real Firebase project, database, identity provider, API, or
other external system merely because product code imports its SDK. Exercise
the product-owned behavior and replace only the unsafe boundary.

## Build the probe

1. Store it under `.assure/probes/` using the project's supported test runner.
2. Import and execute real product code. Do not copy its logic into the probe.
3. Supply deterministic valid, invalid, unauthorized, duplicate, and boundary
   inputs that are relevant to the scenario.
4. Replace outbound boundaries with in-memory fakes or spies. Make unexpected
   network or credential access fail closed.
5. Assert the visible result and the side-effect ledger. Check both required
   calls and forbidden calls, including call count and payload where relevant.
6. Keep the probe independent of personal credentials, current production
   data, wall-clock timing, and external availability.
7. Prove sensitivity with a controlled mutation in an isolated workspace, then
   restore the mutation.
8. Record `probe.entry_points`, all three `probe.cases`, and both
   `probe.assertions` in the manifest. Use `<project-relative-file>#<symbol>`
   for every entry point.

An in-memory fake may model a boundary's documented contract, but it must not
reimplement the product decision being tested. For example, fake user lookup
may return a controlled user; the real login code must still decide whether
the supplied credential is accepted and whether a session is created.

## Isolate and record outbound effects

Represent outbound observations consistently across runners:

```text
effect:
  kind: database-write
  target: users/session
  operation: create
  payload: controlled value
  count: 1
  blocked: true
```

Use the active runner's native mechanism: Vitest `vi.mock`, Jest `jest.mock`,
pytest fixtures or `monkeypatch`, or a compatible project mock. Preserve a
project mock when it already owns the boundary. Create an Assure adapter only
under `.assure/`, keep it as small as possible, and make unexpected access fail
closed. The adapter may supply a controlled boundary response and record
effects; it must not reproduce product decisions.

Treat execution providers and boundary adapters as separate layers:

- Docker or Podman with `network none` provides `os-blocked` assurance.
- `local-isolated` provides `runtime-guarded` assurance through stripped
  credentials, a separate HOME, blocking proxies, and supported runtime mocks.
- Never label runtime guards as OS-level isolation.
- If no safe runner adapter or project mock covers a detected outbound
  boundary, do not execute the scenario. Record the attempted adapter and
  blocker as uncovered evidence.

## Classify the result

- Use `automated` only when the probe executes product behavior and asserts an
  observable outcome.
- Use `uncovered` when no safe executable boundary can be reached or the probe
  cannot distinguish correct from incorrect behavior. Record every attempted
  entry point and strategy, a supported blocker code, and a concrete reason.
- Use `manual` only for outcomes that fundamentally require physical hardware,
  human perception or consent, or a legally controlled real-world action.
- Never use missing Docker, an emulator, a browser driver, a test account, or
  an external service as the sole reason for `manual`.

Static analysis, configuration inspection, and type checking can support probe
construction, but cannot alone produce a passing functional result.

Before approval, run `scripts/assure_probe_policy.py --project <root>`. Treat
every validator error as required mapping work. Policy metadata without a
successful validator result is not an approved functional-probe baseline.
