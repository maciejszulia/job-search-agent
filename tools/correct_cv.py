#!/usr/bin/env python3
"""Apply per-offer corrections to a reviewed Markdown CV: headline, profile, consent clause, wording rules.

Changes per CV: the tailored headline and profile, the employer-specific consent clause (replacing any
earlier consent line, keeping other notes), no "(self-assessed)"/"approximately" qualifiers before a
language level, no "junior" label, and the second profile link next to the first one in the contact line.

    python3 -I tools/correct_cv.py --selftest
"""
import re
import sys

PROFILE = re.compile(r'(^### (?:PROFIL|PROFILE)\n).*?(?=^### |\Z)', re.M | re.S)
CONSENT = re.compile(r'^! (?:Wyrażam zgodę|I (?:hereby )?consent)[^\n]*\n?', re.M)


def correct(markdown, cv, contact_links=None):
    """contact_links = (anchor, extra): when the contact line lacks extra, add it right after anchor."""
    headline, profile, consent = cv['headline'].strip(), cv['profile'].strip(), cv['consent'].strip()
    if not headline or '\n' in headline or len(headline) > 70:
        raise ValueError('headline must be one line of at most 70 characters')
    if not profile or len(profile.split()) > 60 or re.search(r'^[#>!*-]', profile, re.M) or '\n' in profile:
        raise ValueError('profile must be one paragraph of at most 60 words')
    if not consent or '\n' in consent:
        raise ValueError('consent must be one paragraph')
    if len(re.findall(r'^## ', markdown, re.M)) != 1 or len(PROFILE.findall(markdown)) != 1:
        raise ValueError('unexpected CV sections')
    markdown = re.sub(r'^## [^\n]*', lambda _: '## ' + headline, markdown, count=1, flags=re.M)
    markdown = PROFILE.sub(lambda m: m[1] + profile + '\n\n', markdown, count=1)
    markdown = re.sub(r'\s*\((?:samoocena|self-assessed)\)', '', markdown)
    markdown = re.sub(r'\b(?:ok\.|około|approx\.|approximately)\s+(?=C1\b)', '', markdown)
    markdown = CONSENT.sub('', markdown).rstrip('\n')
    # No "junior" anywhere in a CV, historical job titles included.
    markdown = re.sub(r'\s*[—–-]\s*junior\s*$', '', markdown, flags=re.I | re.M)
    markdown = re.sub(r'\s*\(\s*junior\s*\)|\bjunior\s*/\s*(?:regular|mid)\s+|\s+juniorsk\w*', '', markdown, flags=re.I)
    markdown = re.sub(r'\b(junior|młodsz[ya])\s+(\w)', lambda m: m[2].upper() if m[1][0].isupper() else m[2], markdown, flags=re.I)
    markdown = re.sub(r'^(## )(\w)', lambda m: m[1] + m[2].upper(), markdown, count=1, flags=re.M)
    if re.search(r'junior|młodsz[ya] ', markdown, re.I):
        raise ValueError('CV still contains a junior label')
    if contact_links:
        anchor, extra = (re.escape(link) for link in contact_links)
        if not re.search(r'^>[^\n]*' + extra, markdown, re.M):  # contact line only: bodies may link repositories
            markdown, n = re.subn(r'^(>[^\n]*?)((?:https://)?' + anchor + ')',
                                  lambda m: m[1] + m[2] + (' | ' if '|' in m[1] else ' · ') + contact_links[1],
                                  markdown, count=1, flags=re.M)
            if not n:
                raise ValueError('no contact line with the first profile link to extend')
    return markdown + '\n! ' + consent + '\n'


def selftest():
    md = ('# JAN PRZYKŁADOWY\n## Junior Web Developer — CMS\n> Lublin\n> code.example.org/jan\n\n### PROFIL\nx\n\n'
          '### DOŚWIADCZENIE\n**Firma A — Junior Front-end Dev | 2022**\n- komercyjne doświadczenie juniorskie w frontendzie\n**Młodszy specjalista | 2020**\n'
          '- skill: git.example.com/jan/booking\n')  # a repo link in the body must not suppress the profile link
    links = ('code.example.org/jan', 'git.example.com/jan')
    out = correct(md, {'headline': 'Junior Web Developer — CMS', 'profile': 'Profil.', 'consent': 'Zgoda.'}, links)
    assert '## Web Developer — CMS' in out and 'Firma A — Front-end Dev' in out and 'doświadczenie w frontendzie' in out and '**Specjalista | 2020**' in out, out
    assert '> code.example.org/jan · git.example.com/jan' in out and 'junior' not in out.lower() and out.endswith('! Zgoda.\n'), out
    assert '> Lublin\n' in correct(md, {'headline': 'Web Developer', 'profile': 'Profil.', 'consent': 'Zgoda.'})
    try:
        correct(md, {'headline': 'x' * 71, 'profile': 'Profil.', 'consent': 'Zgoda.'})
        raise AssertionError('long headline accepted')
    except ValueError:
        pass
    return 'selftest ok'


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        print(selftest())
    else:
        raise SystemExit(__doc__)
