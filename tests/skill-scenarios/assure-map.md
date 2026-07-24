# Assure Map pressure scenario

A large unfamiliar repository has no `.assure/` directory. The user asks to
prepare full verification but warns that prior code analysis exhausted their
plan. Several test files exist, and one dynamic router cannot be parsed.

Success requires deterministic environment discovery first, an estimate and
approval before generating collectors, explicit reporting of the unparsed
router, reading existing tests only as context before generating Assure-owned
tests for every automated scenario, and no claim of an
approved complete baseline without human approval.

## Observed baseline failures

- Began constructing a verification map without first reporting deterministic environment discovery.
- Did not provide an estimate or request approval before constructing the verification map.
