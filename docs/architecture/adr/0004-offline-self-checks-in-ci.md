# ADR 0004: Offline self-checks in every tool, run by CI

## Status

Accepted. Introduced in commit `ef6ba1e`.

## Context

The tools depend on live portal APIs and on private data. Neither is available in CI or to a reader who clones
the repository.

## Decision

Each tool carries an offline self-check on synthetic data: `--demo`, `--selftest`, or a run without arguments for
`tools/make_plan.py`. The GitHub Actions workflow runs these checks on Python 3.13 and then builds and verifies a
demo CV.

## Consequences

- A reader can check every tool without network and without private data.
- The checks do not prove that a live portal API still answers in the same format.
- `tools/test_fetch_it_offers.py`, added later in commit `4206f25`, is not part of the workflow.

## Evidence

- `.github/workflows/ci.yml`
- `demo()` functions in `tools/*.py`
- commits `ef6ba1e`, `4206f25`
- `README.md`, section "Quick start"
