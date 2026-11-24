# ADR 0003: An append-only JSONL ledger with the SHA-256 of the uploaded CV

## Status

Accepted. Introduced in commit `b176288`.

## Context

The agent sends many applications. The candidate needs to know what was sent, where, when and with which CV, and
the agent must not apply twice for the same offer.

## Decision

`tools/record.py` appends 1 JSON line per attempt to a ledger: offer URL, key, company, title, level, CV file name,
SHA-256 of the CV, upload name, channel, state, evidence seen on the screen, date and time. Failed attempts are
recorded too, for example the state `filled-awaiting-owner`. `tools/fetch_it_offers.py --seen` reads the ledger and
drops offers already in it; `tools/stats.py` counts from it.

## Consequences

- The ledger is the single record for deduplication and statistics.
- The hash ties each entry to the exact CV file.
- The file only grows; a correction is a new line.

## Evidence

- `tools/record.py`
- `ledger_keys()` in `tools/fetch_it_offers.py`
- `attempts()` and `count()` in `tools/stats.py`
- commit `b176288`
