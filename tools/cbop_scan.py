#!/usr/bin/env python3
"""Scan CBOP (oferty.praca.gov.pl, all public employment office offers) for office and computer jobs
near the home location or remote, applyable by e-mail and open to non-registered candidates.

    python3 -I tools/cbop_scan.py --profile PROFILE.json [--out cbop-candidates.json]
    python3 -I tools/cbop_scan.py --demo
"""
import json
import math
import re
import sys
import time
import urllib.request
from pathlib import Path

API = 'https://oferty.praca.gov.pl/portal-api/v3/oferta/wyszukiwanie?page={}&size=200'
OFFICE = re.compile(r'biur|administr|referent|sekretar|informaty|asystent|specjalist|analityk|kadr|recepcj|'
                    r'wprowadzan|dokument|archiw|obsług[ai] klient|koordynator|helpdesk|wsparci|it\b|'
                    r'\bweb|program|tester|grafik|redaktor|tłumacz', re.I)
# hard exclusions: physical or manual work, target-driven sales, telemarketing
EXCLUDE = re.compile(r'sprzedaw|handlow|przedstawiciel|telemarket|kierowc|magazyn|fizyczn|sprząt|kuchar|'
                     r'monter|operator (wózk|maszyn|koparki)|produkcj|pomocnik|ochron|opiekun|pielęgn|'
                     r'kasjer|piekarz|mechanik|elektryk|spawacz|stolarz|kelner|ślusarz|dozorc|konserwator', re.I)


def km(home, lat, lon):
    p1, p2 = math.radians(home[0]), math.radians(lat)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon - home[1]) / 2) ** 2)
    return 12742 * math.asin(math.sqrt(a))


def fetch(page):
    req = urllib.request.Request(API.format(page), data=b'{}', method='POST',
                                 headers={'Content-Type': 'application/json', 'User-Agent': 'job-search-agent/1'})
    for attempt in range(4):  # the API sometimes answers 200 with payload null on big pages
        with urllib.request.urlopen(req, timeout=90) as r:
            body = json.load(r)
        if body.get('payload'):
            return body['payload']['ofertyPracyPage']
        time.sleep(5 * (attempt + 1))
    print(f'page {page}: skipped, API error {body.get("status")} {body.get("msg")}')  # ponytail: a bad record 500s its whole page; bisect with smaller pages if skips grow
    return None


def pick(offers, home, max_km):
    hits = []
    for o in offers:
        text = ' '.join(str(o.get(k) or '') for k in ('stanowisko', 'zakresObowiazkow', 'wymagania'))
        remote = bool(re.search(r'zdaln', text, re.I))
        lat, lon = o.get('miejscePracyLatitude'), o.get('miejscePracyLongitude')
        near = lat is not None and lon is not None and km(home, lat, lon) <= max_km
        if not (o.get('email') and not o.get('dlaOsobZarej') and (near or remote)):
            continue
        if EXCLUDE.search(o['stanowisko']) or not OFFICE.search(o['stanowisko'] + ' ' + (o.get('wymagania') or '')):
            continue
        hits.append({'id': o['id'], 'stanowisko': o['stanowisko'], 'pracodawca': o['pracodawca'],
                     'miejsce': o['miejscePracy'], 'km': round(km(home, lat, lon)) if lat is not None and lon is not None else None,
                     'zdalnie': remote, 'email': o['email'], 'umowa': o.get('rodzajUmowy'),
                     'wynagrodzenie': o.get('wynagrodzenie'), 'wazne_do': o.get('dataWaznDo'),
                     'url': f"https://oferty.praca.gov.pl/portal/lista-ofert/szczegoly-oferty/{o['id']}",
                     'zakres': (o.get('zakresObowiazkow') or '')[:600], 'wymagania': (o.get('wymagania') or '')[:600]})
    return hits


def demo():
    home = (51.2465, 22.5684)
    base = {'pracodawca': 'Firma', 'miejscePracy': 'X', 'email': 'mail-1', 'dlaOsobZarej': False,
            'zakresObowiazkow': '', 'wymagania': ''}
    offers = [dict(base, id='1', stanowisko='Referent', miejscePracyLatitude=51.30, miejscePracyLongitude=22.60),
              dict(base, id='2', stanowisko='Referent', miejscePracyLatitude=52.23, miejscePracyLongitude=21.01),
              dict(base, id='3', stanowisko='Specjalista IT', zakresObowiazkow='praca zdalna',
                   miejscePracyLatitude=None, miejscePracyLongitude=None),
              dict(base, id='4', stanowisko='Sprzedawca', miejscePracyLatitude=51.30, miejscePracyLongitude=22.60),
              dict(base, id='5', stanowisko='Sekretarka', email=None, miejscePracyLatitude=51.30, miejscePracyLongitude=22.60),
              dict(base, id='6', stanowisko='Referent', dlaOsobZarej=True, miejscePracyLatitude=51.30, miejscePracyLongitude=22.60)]
    got = [h['id'] for h in pick(offers, home, 50)]
    assert got == ['1', '3'], got     # far, sales, no e-mail and registered-only offers dropped
    assert 140 < km(home, 52.23, 21.01) < 160
    return 'ok'


def main(profile, out):
    home = (profile['home']['lat'], profile['home']['lon'])
    offers, page, total = [], 0, 1
    while True:
        p = fetch(page)
        print(f'page {page}/{total}', flush=True)
        if p:
            offers += p['content']
            total = p['totalPages']
        if page + 1 >= total:
            break
        page += 1
        time.sleep(1)
    hits = pick(offers, home, profile['home']['max_km'])
    out.write_text(json.dumps(hits, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'{len(offers)} offers scanned, {len(hits)} candidates -> {out}')


if __name__ == '__main__':
    args = sys.argv[1:]
    if '--demo' in args:
        print(demo())
        raise SystemExit(0)
    value = lambda flag, default=None: next((args[i + 1] for i, a in enumerate(args) if a == flag and i + 1 < len(args)), default)
    if not value('--profile'):
        raise SystemExit(__doc__)
    main(json.loads(Path(value('--profile')).read_text(encoding='utf-8')), Path(value('--out', 'cbop-candidates.json')))
