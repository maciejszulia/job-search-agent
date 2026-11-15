#!/usr/bin/env python3
"""Turn a day's offer specs into a build_batch.py plan: one CV variant and one written message per offer.

Usage:  python3 -I tools/make_plan.py PROFILE.json SPECS.json DETAILS.json MESSAGES.json > batch-plan.json
        python3 -I tools/make_plan.py              (self-check)

A spec row is [offer key prefix, workplace or null, "pl"|"en", cv_id, data controller with seat, verbatim consent or null].
Every message is written for its offer, so MESSAGES maps each plan key to its own text; a missing message,
a message without the profile links or without one repository link is an error.
"""
import json
import sys

CONSENT = {
    "pl": ("Wyrażam zgodę na przetwarzanie moich danych osobowych przez {adm} dla potrzeb niezbędnych do realizacji procesu tej oraz przyszłych "
           "rekrutacji, zgodnie z Rozporządzeniem Parlamentu Europejskiego i Rady (UE) 2016/679 z dnia 27 kwietnia 2016 r. (RODO)."),
    "en": ("I consent to the processing of my personal data by {adm} for the purposes of this and future recruitment processes, in accordance "
           "with Regulation (EU) 2016/679 of the European Parliament and of the Council of 27 April 2016 (GDPR).")}


def rows(profile, specs, details, messages):
    out = []
    for prefix, workplace, lang, cv_id, adm, verbatim in specs:
        hits = [o for o in details if o["key"].startswith(prefix) and workplace in (None, o["workplace"])]
        if len(hits) != 1:
            raise ValueError(f"{prefix}: {len(hits)} offers match, expected 1")
        o = hits[0]
        if not (adm or verbatim):
            raise ValueError(f"{prefix}: no data controller and no verbatim consent")
        cv = {"headline": profile["headline"][lang], "profile": profile["profile"][lang],
              "consent": verbatim or CONSENT[lang].format(adm=adm)}
        assert len(cv["headline"]) <= 70 and len(cv["profile"].split()) <= 60, cv_id   # limits of correct()
        key = "it-" + cv_id.lower().replace("_", "-")
        message = messages.get(key, "")
        if not all(link in message for link in profile["links"]) or profile["repo_prefix"] not in message:
            raise ValueError(f"{key}: message missing, without the profile links or without a repository chosen for the offer")
        out.append({"key": key, "url": o["url"], "base": profile["baseline_cv"][lang], "cv_id": cv_id, "cv": cv,
                    "message": message, "company": o["company"], "title": o["title"],
                    "level": o["level"], "workplace": o["workplace"], "salary": o["salary"], "channel": "justjoin.it form (no account)"})
    return out


def demo():
    profile = {"headline": {"pl": "Specjalista automatyzacji"}, "profile": {"pl": "Absolwent informatyki."},
               "baseline_cv": {"pl": "baseline-pl.md"}, "links": ["git.example.com/jan", "www.example.com"],
               "repo_prefix": "git.example.com/jan/"}
    det = [{"key": "acme-ai-engineer-x", "url": "u", "title": "AI Engineer", "company": "Acme", "level": "mid", "workplace": "remote", "salary": None}]
    spec = [["acme-ai", None, "pl", "AI_Engineer_Acme", "Acme sp. z o.o. z siedzibą w Lublinie", None]]
    good = {"it-ai-engineer-acme": "Dzień dobry, ... git.example.com/jan/booking ... " + ", ".join(profile["links"])}
    r = rows(profile, spec, det, good)[0]
    assert r["cv"]["profile"] == "Absolwent informatyki." and "Acme sp. z o.o." in r["cv"]["consent"] and r["base"] == "baseline-pl.md"
    for bad_spec, bad_messages in ((spec, {}), (spec, {"it-ai-engineer-acme": "Dzień dobry, " + ", ".join(profile["links"])}),
                                   ([["acme-ai", None, "pl", "AI_Engineer_Acme", None, None]], good)):
        try:
            rows(profile, bad_spec, det, bad_messages)
            raise AssertionError("bad row accepted")
        except ValueError:
            pass
    return "ok"


if __name__ == "__main__":
    if len(sys.argv) < 5:
        print(demo())
    else:
        load = lambda p: json.load(open(p, encoding="utf-8"))
        print(json.dumps(rows(*(load(p) for p in sys.argv[1:5])), ensure_ascii=False, indent=1))
