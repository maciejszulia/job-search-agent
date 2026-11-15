#!/usr/bin/env python3
"""Build one CV per plan row from a reviewed baseline CV in Markdown.

Per row: replace the profile's fixed lines (work mode, links), apply correct() (headline, profile,
consent clause, wording rules), write <cv_file_prefix>_<cv_id>.md and build DOCX, PDF and TXT next to it.

    python3 -I tools/build_batch.py --profile PROFILE.json --plan PLAN.json --baselines DIR --out DIR [key ...]
    python3 -I tools/build_batch.py --demo
"""
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
from correct_cv import correct  # noqa: E402


def prepare(source, row, profile):
    """Markdown of one CV: fixed-line replacements, then the per-offer corrections."""
    lang = 'en' if row['base'].endswith('-en.md') else 'pl'
    for old, new in profile['cv_line_replacements'][lang]:
        if old not in source:
            raise ValueError(f'{row["base"]}: expected line missing: {old}')
        source = source.replace(old, new)
    return correct(source, row['cv'], profile.get('contact_links'))


def main(profile, plan, baselines, out, keys):
    from build_cv import build  # needs python-docx, PyMuPDF and LibreOffice
    out.mkdir(parents=True, exist_ok=True)
    failures = 0
    for row in plan:
        if keys and row['key'] not in keys:
            continue
        target = out / f'{profile["cv_file_prefix"]}_{row["cv_id"]}.md'
        try:
            target.write_text(prepare((baselines / row['base']).read_text(encoding='utf-8'), row, profile), encoding='utf-8')
            report = build(target)
            print(json.dumps({'key': row['key'], 'pages': report['pages'], 'fill_pct': report['bounds'][0]['fill_pct']}), flush=True)
        except Exception as error:  # report every CV, stop nothing
            failures += 1
            print(json.dumps({'key': row['key'], 'error': str(error)[:300]}, ensure_ascii=False), flush=True)
    return 1 if failures else 0


def demo():
    profile = json.loads((Path(__file__).resolve().parents[1] / 'examples/profile.example.json').read_text(encoding='utf-8'))
    base = ('# JAN PRZYKŁADOWY\n## Web Developer\n> Lublin · praca stacjonarna\n> code.example.org/jan\n\n'
            '### PROFIL\nStary profil.\n\n### DOŚWIADCZENIE\n**Firma A | 2022**\n- wdrożenia\n')
    row = {'key': 'it-qa-acme', 'base': 'baseline-pl.md', 'cv_id': 'QA_Acme',
           'cv': {'headline': 'Tester QA', 'profile': 'Nowy profil.', 'consent': 'Zgoda dla Acme sp. z o.o.'}}
    md = prepare(base, row, profile)
    assert '> Lublin · praca zdalna, hybrydowa albo stacjonarna · pełny etat' in md, md
    assert '## Tester QA' in md and 'Nowy profil.' in md and 'Stary profil.' not in md, md
    assert '> code.example.org/jan · git.example.com/jan' in md and md.endswith('! Zgoda dla Acme sp. z o.o.\n'), md
    try:
        prepare(base.replace('praca stacjonarna', 'zdalnie'), row, profile)
        raise AssertionError('missing fixed line accepted')
    except ValueError:
        pass
    return 'ok'


if __name__ == '__main__':
    args = sys.argv[1:]
    if '--demo' in args:
        print(demo())
        raise SystemExit(0)
    opts = {a: args[i + 1] for i, a in enumerate(args) if a in ('--profile', '--plan', '--baselines', '--out') and i + 1 < len(args)}
    if len(opts) != 4:
        raise SystemExit(__doc__)
    keys = set(args) - set(opts) - set(opts.values())
    load = lambda p: json.loads(Path(p).read_text(encoding='utf-8'))
    raise SystemExit(main(load(opts['--profile']), load(opts['--plan']), Path(opts['--baselines']), Path(opts['--out']), keys))
