#!/usr/bin/env python3
"""Append one application attempt to a portal ledger (JSONL), with the SHA-256 of the CV that was uploaded.

Usage:  python3 -I tools/record.py --plan PLAN.json --cv-dir DIR --ledger LEDGER.jsonl --profile PROFILE.json \
            KEY "evidence seen on the page" [STATE]
        python3 -I tools/record.py --demo
STATE defaults to "submitted"; use "filled-awaiting-owner" when a CAPTCHA leaves the click to the person.
"""
import argparse
import hashlib
import json
import tempfile
import time
from pathlib import Path


def record(plan, cv_dir, ledger, prefix, key, evidence, state="submitted", now=None):
    row = next(r for r in json.loads(Path(plan).read_text(encoding="utf-8")) if r["key"] == key)
    cv = Path(cv_dir) / f"{prefix}_{row['cv_id']}.pdf"
    now = now or time.localtime()
    entry = {"offer": row["url"], "key": key, "company": row["company"], "title": row["title"], "level": row["level"],
             "cv": cv.name, "cv_sha256": hashlib.sha256(cv.read_bytes()).hexdigest(), "uploaded_as": f"{prefix}.pdf",
             "channel": row["channel"], "state": state, "evidence": evidence,
             "date": time.strftime("%Y-%m-%d", now), "time": time.strftime("%H:%M", now)}
    with open(ledger, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def demo():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        plan = tmp / "plan.json"
        plan.write_text(json.dumps([{"key": "it-qa-acme", "url": "https://example.com/job/1", "company": "Acme", "title": "QA",
                                     "level": "mid", "cv_id": "QA_Acme", "channel": "portal form"}]), encoding="utf-8")
        (tmp / "CV_Jan_QA_Acme.pdf").write_bytes(b"%PDF-1.4 demo")
        ledger = tmp / "ledger.jsonl"
        now = time.strptime("2026-11-15 13:56", "%Y-%m-%d %H:%M")
        record(plan, tmp, ledger, "CV_Jan", "it-qa-acme", "Done!", now=now)
        record(plan, tmp, ledger, "CV_Jan", "it-qa-acme", "CAPTCHA", "filled-awaiting-owner", now=now)
        rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
        assert [r["state"] for r in rows] == ["submitted", "filled-awaiting-owner"], rows
        assert rows[0]["cv_sha256"] == hashlib.sha256(b"%PDF-1.4 demo").hexdigest() and rows[0]["uploaded_as"] == "CV_Jan.pdf"
        assert (rows[0]["date"], rows[0]["time"]) == ("2026-11-15", "13:56"), rows[0]
    return "ok"


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--demo", action="store_true", help="run the self-check and exit")
    for flag in ("--plan", "--cv-dir", "--ledger", "--profile"):
        p.add_argument(flag)
    p.add_argument("key", nargs="?")
    p.add_argument("evidence", nargs="?")
    p.add_argument("state", nargs="?", default="submitted")
    a = p.parse_args()
    if a.demo:
        print(demo())
    elif not all((a.plan, a.cv_dir, a.ledger, a.profile, a.key, a.evidence)):
        p.error("--plan, --cv-dir, --ledger, --profile, KEY and EVIDENCE are required")
    else:
        prefix = json.loads(Path(a.profile).read_text(encoding="utf-8"))["cv_file_prefix"]
        e = record(a.plan, a.cv_dir, a.ledger, prefix, a.key, a.evidence, a.state)
        print(e["date"], e["time"], a.key, "recorded")
