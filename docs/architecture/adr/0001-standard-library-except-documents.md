# ADR 0001: Standard library only, except the DOCX and PDF step

## Status

Accepted. Visible since the first tool commits `fb696e5` and `8b9fb0d`.

## Context

The tools run on the candidate's machine and in CI. Every dependency is something to install and to keep working.
Building a DOCX and a PDF needs a document library and a renderer.

## Decision

The offer collectors, the plan builder, the ledger recorder, the CV corrections and the statistics use only the
Python standard library (`urllib.request`, `json`, `re`, `hashlib`, `zoneinfo`). Only `tools/build_cv.py` imports
`python-docx` and `pymupdf` and calls LibreOffice (`soffice`). `tools/build_batch.py` imports `build_cv` inside
`main()`, so its `--demo` runs without those packages.

## Consequences

- 7 of the 8 self-checks in CI run without installing a package.
- HTTP code is hand-written on `urllib.request`, with its own timeouts and pauses.
- The CV build needs LibreOffice and fonts on the machine; CI installs `libreoffice-writer` and `fonts-liberation`.

## Evidence

- imports in `tools/fetch_it_offers.py`, `tools/cbop_scan.py`, `tools/make_plan.py`, `tools/record.py`,
  `tools/stats.py`, `tools/correct_cv.py`
- `main()` in `tools/build_batch.py`
- `tools/build_cv.py`
- `.github/workflows/ci.yml`
- `README.md`, sections "Quick start" and "How it works"
