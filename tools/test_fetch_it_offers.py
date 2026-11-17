"""Regression test for jj_offers: a 40-page cap once read 400 of 942 offers in one category and found 11 of the
25 junior offers, with no warning. jj_offers must read every page unless the caller sets a cap, and a cap that
cuts the list must say so on stderr. The justjoin.it API is stubbed with 942 synthetic offers, 25 of them junior.
Usage:  python3 -I tools/test_fetch_it_offers.py      (prints ok)"""
import contextlib
import io
import sys
import types
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_it_offers as f  # noqa: E402

TOTAL = 942
JUNIOR = set(range(5, 400, 37)) | set(range(431, TOTAL, 37))       # 11 junior offers before offer 400, 14 after it


def fake_get(url, data=None):
    start = int(urllib.parse.parse_qs(urllib.parse.urlparse(url).query)['from'][0])
    page = [{'slug': f'o{i}', 'experienceLevel': 'junior' if i in JUNIOR else 'mid'} for i in range(start, min(start + 10, TOTAL))]
    nxt = start + 10
    return {'data': page, 'meta': {'next': {'cursor': nxt if nxt < TOTAL else None, 'itemsCount': len(page)}, 'totalItems': TOTAL}}


f.get, f.time = fake_get, types.SimpleNamespace(sleep=lambda s: None)
juniors = lambda rows: sum(o['experienceLevel'] == 'junior' for o in rows)
assert len(JUNIOR) == 25 and len([i for i in JUNIOR if i < 400]) == 11

rows = f.jj_offers('categories=pm')
assert len(rows) == TOTAL and juniors(rows) == 25, (len(rows), juniors(rows))

err = io.StringIO()
with contextlib.redirect_stderr(err):
    capped = f.jj_offers('categories=pm', 40)
assert len(capped) == 400 and juniors(capped) == 11, (len(capped), juniors(capped))
assert '400 of 942' in err.getvalue(), repr(err.getvalue())
print('ok')
