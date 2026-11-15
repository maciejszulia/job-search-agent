#!/usr/bin/env python3
"""Count applications and employer responses from private ledgers; write stats.json and stats.svg.

The output holds counts only: no employer names, no person names, no addresses.

Usage:
    python3 -I tools/stats.py [--submissions SUBMISSIONS.json --queue APPLICATIONS.json] \
        [--portal PORTAL.jsonl ...] [--outcomes OUTCOMES.jsonl] --out docs
    python3 -I tools/stats.py --demo

Definitions:
    unique application  first confirmed send (e-mail accepted, form or portal confirmation) to one route,
                        where a route is one employer and one position (one ledger key)
    resend              every later confirmed send to a route that already has a unique application
    thread message      reply, reminder or note sent in an existing mail thread (not an application)
    incomplete route    a route with attempts but no confirmed send (CAPTCHA, account wall, unconfirmed form)
    response            one message from a person on the employer side, recorded in the outcomes file
"""
import argparse
import json
import re
import tempfile
from collections import Counter, defaultdict
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Warsaw")
CONFIRMED = {"sent", "form_submitted", "submitted"}
OFFER_TYPE = {"vacancy": "job_ad", "job": "public_employment_service", "spontaneous": "spontaneous"}
EVENTS = ("refusal", "cv_filed", "other_reply", "interview_invitation")
BOARDS = ("pracuj.pl", "justjoin.it", "nofluffjobs.com")


def day(value):
    """ISO timestamp, RFC 2822 date or YYYY-MM-DD -> local calendar date YYYY-MM-DD."""
    if not value:
        return ""
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return value
    try:
        moment = datetime.fromisoformat(value)
    except ValueError:
        moment = parsedate_to_datetime(value)
    return moment.astimezone(TZ).date().isoformat()


def channel(text):
    low = (text or "").lower()
    return next((b for b in BOARDS if b.split(".")[0] in low), "other_form")


def attempts(submissions, queue, portals):
    """Yield (route, attempt, date, state, channel, offer_type) for every ledger record."""
    types = {}
    for a in queue["applications"]:
        types[a["id"]] = types[a["application_key"]] = OFFER_TYPE.get(a["kind"], a["kind"])
    for key, r in submissions.items():
        route, _, tag = key.partition("|")
        when = day(r.get("completed_at") or r.get("started_at"))
        if route.startswith("human-note") or (tag and not tag.startswith("resend")):
            yield route, "thread", when, r.get("state"), None, None
            continue
        ch = channel(r.get("receipt_url")) if r.get("channel") == "web_form" else "email"
        yield route, "resend" if tag else "primary", when, r.get("state"), ch, types.get(route, "unknown")
    for rows in portals:
        for r in rows:
            yield r["key"], "primary", r["date"], r["state"], channel(r["channel"]), "job_ad"


def count(records, outcomes):
    records = sorted(records, key=lambda a: (a[2], a[1] != "primary"))
    unique, resends, routes, threads = {}, [], set(), 0
    for route, attempt, when, state, ch, offer in records:
        if attempt == "thread":
            threads += state in CONFIRMED
            continue
        routes.add(route)
        if state not in CONFIRMED:
            continue
        if route in unique:
            resends.append(when)
        else:
            unique[route] = (when, ch, offer)
    by_month = lambda dates: dict(sorted(Counter(d[:7] for d in dates).items()))
    responses = Counter(o["event"] for o in outcomes)
    unknown = set(responses) - set(EVENTS)
    if unknown:
        raise ValueError(f"unknown outcome events: {sorted(unknown)}")
    monthly = defaultdict(Counter)
    for o in outcomes:
        monthly[o["date"][:7]][o["event"]] += 1
    dates = [u[0] for u in unique.values()]
    return {
        "period": {"first_application": min(dates, default=""), "last_application": max(dates, default="")},
        "totals": {"unique_applications": len(unique), "resends": len(resends), "thread_messages": threads,
                   "incomplete_routes": len(routes - set(unique))},
        "unique_by_month": by_month(dates),
        "resends_by_month": by_month(resends),
        "unique_by_channel": dict(Counter(u[1] for u in unique.values()).most_common()),
        "unique_by_offer_type": dict(Counter(u[2] for u in unique.values()).most_common()),
        "responses": {"total": sum(responses.values()), **{e: responses[e] for e in EVENTS}},
        "responses_by_month": {m: {e: c[e] for e in EVENTS} for m, c in sorted(monthly.items())},
    }


def plural(n, one, few, many):
    """Polish noun form for the number n."""
    if n == 1:
        return one
    return few if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14) else many


def esc(text):
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def bar(x, y, w, h):
    """Bar path: square at the baseline, 4 px rounded data end; zero width draws nothing."""
    if w <= 0:
        return ""
    r = min(4, w / 2, h / 2)
    return (f"M{x} {y}H{x + w - r:.1f}A{r:.1f} {r:.1f} 0 0 1 {x + w:.1f} {y + r:.1f}V{y + h - r:.1f}"
            f"A{r:.1f} {r:.1f} 0 0 1 {x + w - r:.1f} {y + h}H{x}Z")


def svg(s):
    t, r = s["totals"], s["responses"]
    u, n, i = t["unique_applications"], r["total"], r["interview_invitation"]
    title = (f"{u} {plural(u, 'zgłoszenie', 'zgłoszenia', 'zgłoszeń')} {plural(u, 'dało', 'dały', 'dało')} "
             f"{n} {plural(n, 'odpowiedź', 'odpowiedzi', 'odpowiedzi')} i "
             f"{i} {plural(i, 'zaproszenie', 'zaproszenia', 'zaproszeń')} na rozmowę")
    sub = (f"Zgłoszenia od {s['period']['first_application']} do {s['period']['last_application']}. "
           "Odpowiedź oznacza wiadomość od osoby po stronie pracodawcy.")
    rows = [("Zgłoszenia unikalne", u), ("Wysyłki ponowne", t["resends"]), ("Odmowy", r["refusal"]),
            ("CV zapisane w bazie", r["cv_filed"]), ("Inne odpowiedzi", r["other_reply"]),
            ("Zaproszenia na rozmowę", i)]
    width, x0, span, step, top = 760, 230, 440, 34, 86
    height = top + step * len(rows) + 10
    peak = max(v for _, v in rows) or 1
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
           f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
           '<style>svg{font-family:system-ui,-apple-system,"Segoe UI",sans-serif}'
           '.bg{fill:#fcfcfb}.ink{fill:#0b0b0b}.sub{fill:#52514e}.bar{fill:#2a78d6}.axis{stroke:#c3c2b7}'
           '@media (prefers-color-scheme:dark){.bg{fill:#1a1a19}.ink{fill:#f0efec}.sub{fill:#c3c2b7}'
           '.bar{fill:#3987e5}.axis{stroke:#383835}}</style>',
           f'<title id="title">{esc(title)}</title>',
           f'<desc id="desc">{esc("; ".join(f"{k}: {v}" for k, v in rows))}</desc>',
           f'<rect class="bg" width="{width}" height="{height}" rx="8"/>',
           f'<text class="ink" x="24" y="36" font-size="18" font-weight="600">{esc(title)}</text>',
           f'<text class="sub" x="24" y="60" font-size="13">{esc(sub)}</text>']
    for k, (label, value) in enumerate(rows):
        y, w = top + k * step, span * value / peak
        out.append(f'<g><title>{esc(label)}: {value}</title>'
                   f'<text class="ink" x="{x0 - 12}" y="{y + 15}" font-size="13" text-anchor="end">{esc(label)}</text>'
                   f'<path class="bar" d="{bar(x0, y + 1, w, 20)}"/>'
                   f'<text class="ink" x="{x0 + w + 8:.1f}" y="{y + 15}" font-size="13">{value}</text></g>')
    out.append(f'<line class="axis" x1="{x0}" y1="{top - 4}" x2="{x0}" y2="{top + step * len(rows) - 10}" stroke-width="1"/>')
    return "\n".join(out + ["</svg>"]) + "\n"


def load_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def demo():
    queue = {"applications": [{"id": "a", "application_key": "a", "kind": "vacancy"},
                              {"id": "b", "application_key": "b", "kind": "spontaneous"},
                              {"id": "c", "application_key": "c", "kind": "job"}]}
    subs = {"a": {"state": "sent", "completed_at": "2026-09-30T23:30:00+00:00"},          # 1 Oct in Warsaw
            "b": {"state": "unconfirmed", "channel": "web_form", "started_at": "2026-10-02T10:00:00+00:00"},
            "b|resend-2026-11": {"state": "sent", "completed_at": "2026-11-03T10:00:00+00:00"},
            "a|resend-2026-11": {"state": "sent", "completed_at": "2026-11-03T10:05:00+00:00"},
            "c": {"state": "form_submitted", "channel": "web_form", "receipt_url": "https://x.pracuj.pl/ok",
                  "completed_at": "2026-11-09T10:00:00+00:00"},
            "a|reply-2026-11-04": {"state": "sent", "completed_at": "Wed, 04 Nov 2026 10:00:00 +0000"},
            "human-note-2026-11-09|x.example": {"state": "sent", "completed_at": "2026-11-09T12:00:00+00:00"}}
    portal = [{"key": "p1", "date": "2026-11-04", "state": "submitted", "channel": "justjoin.it form"},
              {"key": "p2", "date": "2026-11-05", "state": "blocked-captcha", "channel": "justjoin.it form"}]
    outcomes = [{"date": "2026-10-05", "event": "refusal"}, {"date": "2026-11-04", "event": "interview_invitation"}]
    s = count(attempts(subs, queue, [portal]), outcomes)
    assert s["totals"] == {"unique_applications": 4, "resends": 1, "thread_messages": 2, "incomplete_routes": 1}, s
    assert s["unique_by_month"] == {"2026-10": 1, "2026-11": 3}, s          # b counts once, on its first confirmed send
    assert s["unique_by_channel"] == {"email": 2, "pracuj.pl": 1, "justjoin.it": 1}, s
    assert s["unique_by_offer_type"] == {"job_ad": 2, "spontaneous": 1, "public_employment_service": 1}, s
    assert s["responses"]["total"] == 2 and s["responses_by_month"]["2026-11"]["interview_invitation"] == 1, s
    picture = svg(s)
    assert "4 zgłoszenia dały 2 odpowiedzi i 1 zaproszenie na rozmowę" in picture, picture
    assert picture.count("font-family") == 1
    assert plural(22, "a", "b", "c") == "b" and plural(12, "a", "b", "c") == "c" and plural(161, "a", "b", "c") == "c"
    try:
        count([], [{"date": "2026-11-01", "event": "offer"}])
        raise AssertionError("unknown event accepted")
    except ValueError:
        pass
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "o.jsonl"
        path.write_text('{"date": "2026-11-01", "event": "refusal"}\n\n', encoding="utf-8")
        assert load_jsonl(path) == [{"date": "2026-11-01", "event": "refusal"}]
    return "ok"


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--demo", action="store_true", help="run the self-check and exit")
    p.add_argument("--submissions", help="JSON ledger of e-mail and form sends, keyed by route")
    p.add_argument("--queue", help="JSON application queue with the offer type of each route")
    p.add_argument("--portal", action="append", default=[], help="JSONL ledger of portal forms (repeatable)")
    p.add_argument("--outcomes", help="JSONL file of employer responses: date, event")
    p.add_argument("--out", default="docs", help="output directory for stats.json and stats.svg")
    a = p.parse_args()
    if a.demo:
        print(demo())
        return
    if not (a.submissions or a.portal):
        p.error("give --submissions with --queue, or at least one --portal ledger")
    load = lambda path, empty: json.loads(Path(path).read_text(encoding="utf-8")) if path else empty
    stats = count(attempts(load(a.submissions, {}), load(a.queue, {"applications": []}), [load_jsonl(f) for f in a.portal]),
                  load_jsonl(a.outcomes) if a.outcomes else [])
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (out / "stats.svg").write_text(svg(stats), encoding="utf-8")
    print(json.dumps(stats["totals"]), json.dumps(stats["responses"]))


if __name__ == "__main__":
    main()
