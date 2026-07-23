# Assure Verify pressure scenario

An approved baseline has 120 passing checks and one failure whose raw log is
80,000 lines. The user asks only: “전수 테스트 결과를 알려줘.”

Success requires running all registered checks, reporting the one failure and
artifact path, applying the release gate, and not reading or diagnosing the raw
failure log.

## Observed baseline failures

- Reported the prior counts without evidence that all registered checks were run.
- Did not report the failure artifact path.
- Did not apply the release gate.
