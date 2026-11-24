# ADR 0002: Personal data stays in an ignored `private/` folder

## Status

Accepted. Introduced in commit `c53f579`.

## Context

A job search produces personal data: the profile, ledgers, CVs, correspondence and employer names. The tools and
the method are public.

## Decision

`.gitignore` excludes `/private/`. Every run on real data reads and writes files in `private/`. The repository
holds only synthetic examples (`examples/`) and counts without names (`docs/stats.json`). Tools whose code holds
private data, such as the e-mail sending panel, stay in a private repository.

## Consequences

- The Git history holds no personal data from the job search.
- The public repository cannot send applications; the private panel or the candidate sends them.
- A private tool moves here only after its data moves to the profile and it gets a self-check.

## Evidence

- `.gitignore`
- commit `c53f579`
- `examples/profile.example.json`, `examples/outcomes.example.jsonl`
- docstring of `tools/stats.py`
- `README.md`, sections "Run on your own data", "Rules the candidate set for the agent" and "Limits"
