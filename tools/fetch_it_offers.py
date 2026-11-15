#!/usr/bin/env python3
"""Collect IT job offers from justjoin.it and No Fluff Jobs into one ranked shortlist.

Rules: every IT role at every level, AI roles first; remote, hybrid in a Polish city, or any mode in
the candidate's home city; offers already in a ledger are skipped; pay below the floor is dropped.

Usage:  python3 -I tools/fetch_it_offers.py --profile PROFILE.json [--seen LEDGER ...] [--pages=N] > shortlist.jsonl
        python3 -I tools/fetch_it_offers.py --demo
A --seen file is either a JSON queue with an "applications" list or a JSONL ledger with an "offer" URL per line.
"""
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

JJ = "https://justjoin.it/api/candidate-api/offers"
NFJ = ("https://nofluffjobs.com/api/search/posting"
       "?salaryCurrency=PLN&salaryPeriod=month&region=pl&language=pl-PL&page={page}")
AI = re.compile(r"\b(ai|ml|llm|genai|gen ai|machine learning|nlp|prompt|agent\w*|automation|automatyzac\w*)\b", re.I)
GROSS_TO_NET = 0.72     # ponytail: flat UoP gross-to-net ratio; use a payroll calculator for rows near the floor
# ponytail: hand list of Polish IT cities for hybrid offers; the home city comes from the profile; extend the list when a hybrid offer from another Polish city is missed
PL_CITIES = {"warszawa", "warsaw", "kraków", "krakow", "wrocław", "wroclaw", "gdańsk", "gdansk", "gdynia", "sopot",
             "poznań", "poznan", "łódź", "lodz", "katowice", "gliwice", "lublin", "szczecin", "bydgoszcz", "toruń",
             "torun", "białystok", "bialystok", "rzeszów", "rzeszow", "kielce", "opole", "bielsko-biała",
             "bielsko-biala", "zielona góra", "zielona gora", "częstochowa", "czestochowa", "elbląg", "elblag"}


def get(url, data=None):
    headers = {"User-Agent": "Mozilla/5.0", **({"Content-Type": "application/json"} if data else {})}
    with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers), timeout=30) as r:
        return json.load(r)


def jj_offers(query, pages):
    out, start = [], 0
    for _ in range(pages):
        d = get(f"{JJ}?{query}&from={start}")
        out += d["data"]
        nxt, total = d["meta"]["next"]["cursor"], d["meta"]["totalItems"]
        if not d["data"] or nxt is None or nxt >= total:
            break
        start = nxt
        time.sleep(0.3)
    return out


def nfj_offers(raw, pages):
    out = []
    for page in range(1, pages + 1):
        d = get(NFJ.format(page=page), json.dumps({"rawSearch": raw}).encode())
        out += [p for p in d["postings"] if "it" in (p.get("flavors") or ["it"])]
        if page >= d.get("totalPages", 1):
            break
        time.sleep(0.3)
    return out


def from_jj(o):
    paid = [e for e in o.get("employmentTypes") or [] if e.get("from") or e.get("to")]
    pln = [e for e in paid if e.get("currency") == "PLN"] or paid
    s = pln[0] if pln else None
    url = f"https://justjoin.it/job-offer/{o['slug']}"
    return {"source": "justjoin.it", "url": url, "apply": o.get("applyUrl") or url,
            "apply_method": o.get("applyMethod"), "title": o["title"].strip(), "company": o["companyName"].strip(),
            "level": o.get("experienceLevel"), "workplace": o.get("workplaceType"),
            "cities": sorted({loc["city"] for loc in o.get("locations") or [] if loc.get("city")} | {o.get("city") or ""} - {""}),
            "salary": {k: s.get(k) for k in ("from", "to", "currency", "type", "unit", "gross")} if s else None,
            "ai": o["category"]["key"] == "ai" or bool(AI.search(o["title"])),
            "published": (o.get("publishedAt") or "")[:10], "languages": o.get("languages") or []}


def from_nfj(p):
    s = p.get("salary") or None
    cities = sorted({pl["city"] for pl in p["location"]["places"] if pl.get("city")})
    url = f"https://nofluffjobs.com/pl/job/{p['url']}"
    remote = p["location"].get("fullyRemote") or "Remote" in cities
    return {"source": "nofluffjobs.com", "url": url, "apply": url, "apply_method": "nfj",
            "title": p["title"].strip(), "company": p["name"].strip(),
            "level": ",".join(p.get("seniority") or []).lower(), "workplace": "remote" if remote else "office",
            "cities": [c for c in cities if c != "Remote"],
            "salary": {"from": s.get("from"), "to": s.get("to"), "currency": s.get("currency"), "type": s.get("type"),
                       "unit": (s.get("period") or "month").lower(), "gross": s.get("type") == "permanent"} if s else None,
            "ai": p.get("category") == "artificialIntelligence" or bool(AI.search(p["title"])),
            "published": time.strftime("%Y-%m-%d", time.gmtime((p.get("renewed") or p.get("posted") or 0) / 1000)),
            "languages": []}


def eligible(r, home):
    """Remote anywhere, hybrid in a Polish city, or any mode in the home city."""
    cities = {c.lower() for c in r["cities"]}
    if r["workplace"] == "remote" or home in cities:
        return True
    return r["workplace"] == "hybrid" and bool(cities & PL_CITIES)


def pays_enough(s, min_net):
    """False only when the advertised maximum is clearly below the take-home floor."""
    if not s or not s.get("to") or s.get("currency") != "PLN":
        return True
    per_month = s["to"] * (168 if s.get("unit") == "hour" else 1)
    return per_month * (GROSS_TO_NET if s.get("gross") or s.get("type") == "permanent" else 1) >= min_net


def norm_url(u):
    return u.split("?")[0].split("#")[0].rstrip("/").lower()


def pair(company, title):
    words = lambda s: re.sub(r"\W+", " ", (s or "").lower()).strip()
    return f"{words(company)}|{words(title)}"


def ledger_keys(paths):
    """Offer URLs and company|title pairs already present in the given queue or ledger files."""
    keys = set()
    for path in paths:
        text = Path(path).read_text(encoding="utf-8")
        if path.endswith(".jsonl"):
            keys |= {norm_url(json.loads(line).get("offer", "")) for line in text.splitlines() if line.strip()}
            continue
        for a in json.loads(text)["applications"]:
            keys |= {norm_url(a[k]) for k in ("source_url", "apply_url") if a.get(k)}
            keys.add(pair(a.get("employer"), a.get("title")))
    return keys


def shortlist(rows, seen, home, min_net):
    out, taken = [], set(seen)
    for r in sorted(rows, key=lambda r: (r["ai"], r["published"]), reverse=True):   # AI first, newest first
        k1, k2 = norm_url(r["url"]), pair(r["company"], r["title"])
        if k1 in taken or k2 in taken or not eligible(r, home) or not pays_enough(r["salary"], min_net):
            continue
        taken |= {k1, k2}
        out.append(r)
    return out


def demo():
    base = {"source": "t", "apply": "", "apply_method": "form", "level": "senior", "salary": None, "languages": []}
    rows = [dict(base, url="https://x/1", title="Java Dev", company="A", workplace="remote", cities=["Oslo"], ai=False, published="2026-11-15"),
            dict(base, url="https://x/2", title="AI Engineer", company="B", workplace="hybrid", cities=["Warszawa"], ai=True, published="2026-11-10"),
            dict(base, url="https://x/3", title="QA", company="C", workplace="office", cities=["Kraków"], ai=False, published="2026-11-15"),
            dict(base, url="https://x/4?utm=1", title="Admin", company="D", workplace="office", cities=["Lublin"], ai=False, published="2026-11-14"),
            dict(base, url="https://x/5", title="Intern", company="E", workplace="remote", cities=[], ai=False, published="2026-11-15",
                 salary={"from": 3000, "to": 4000, "currency": "PLN", "type": "permanent", "unit": "month", "gross": True}),
            dict(base, url="https://x/6", title="AI Engineer", company="B", workplace="remote", cities=[], ai=True, published="2026-11-09"),
            dict(base, url="https://x/7", title="Support", company="F", workplace="office", cities=["Lublin"], ai=False, published="2026-11-13")]
    got = [r["url"] for r in shortlist(rows, {norm_url("https://x/4")}, "lublin", 4000)]
    assert got == ["https://x/2", "https://x/1", "https://x/7"], got   # AI first; office outside home, low pay, ledger and duplicate pair dropped
    assert pays_enough({"to": 40, "currency": "PLN", "type": "b2b", "unit": "hour"}, 4000)
    assert not pays_enough({"to": 5000, "currency": "PLN", "type": "permanent", "unit": "month", "gross": True}, 4000)
    assert AI.search("Senior LLM Platform Engineer") and not AI.search("Email marketing specialist")
    return "ok"


def main(profile, seen, pages):
    home, min_net = profile["home"]["city"].lower(), profile["min_net_pln"]
    rows = [from_jj(o) for o in jj_offers("categories=ai", 70)]
    rows += [from_jj(o) for o in jj_offers(f"city={home}", 20)]
    rows += [from_jj(o) for o in jj_offers("", pages)]
    rows += [from_nfj(p) for p in nfj_offers("category=artificial-intelligence", 10)]
    rows += [from_nfj(p) for p in nfj_offers("remote", pages)]
    rows += [from_nfj(p) for p in nfj_offers(f"city={home}", 5)]
    out = shortlist(rows, ledger_keys(seen), home, min_net)
    for r in out:
        print(json.dumps(r, ensure_ascii=False))
    print(f"fetched {len(rows)}, shortlisted {len(out)}, AI {sum(r['ai'] for r in out)}", file=sys.stderr)


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--demo" in args:
        print(demo())
        raise SystemExit(0)
    value = lambda flag: [args[i + 1] for i, a in enumerate(args) if a == flag and i + 1 < len(args)]
    if not value("--profile"):
        raise SystemExit(__doc__)
    main(json.loads(Path(value("--profile")[0]).read_text(encoding="utf-8")), value("--seen"),
         int(next((a.split("=", 1)[1] for a in args if a.startswith("--pages=")), "20")))
