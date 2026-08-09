#!/usr/bin/env python3
"""Run the structural probe over every built reader, in three conditions.

Desktop light is the default view; desktop dark and mobile light exercise
the two variant paths (`data-theme`, `mobile_inline` + narrow layout) that
nothing else in the suite touches.

Run inside the dev shell (needs node for agent-browser):
    nix develop --command python3 tools/qa_readers.py [slug …]
"""

import json
import subprocess
import sys
from pathlib import Path

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))

from project import ROOT, SITE

AB = str(ROOT / 'tools' / 'agent-browser')
PROBE = (ROOT / 'tools' / 'reader_probe.js').read_text()

CONDITIONS = [
    ('desktop-light', (1280, 900), ''),
    ('desktop-dark', (1280, 900), "document.documentElement.dataset.theme='dark';"),
    ('mobile-light', (390, 844), ''),
]


def ab(*args, stdin=None):
    return subprocess.run([AB, *args], capture_output=True, text=True,
                          input=stdin, timeout=180).stdout.strip()


def probe(slug, setup):
    ab('open', f'file://{SITE / (slug + ".html")}')
    if setup:
        ab('eval', setup + "'ok'")
    raw = ab('eval', '--stdin', stdin=PROBE)
    try:
        # agent-browser prints the JS return value JSON-encoded; the probe
        # itself returns a JSON string, hence the double decode.
        return json.loads(json.loads(raw))
    except (json.JSONDecodeError, TypeError):
        return {'flags': [{'kind': 'probe-failed', 'detail': raw[:300]}]}


def main():
    slugs = sys.argv[1:] or sorted(
        p.stem for p in SITE.glob('*.html') if p.stem != 'index')
    findings = {}
    for name, (w, h), setup in CONDITIONS:
        ab('set', 'viewport', str(w), str(h))
        print(f'\n══ {name} ({w}×{h}) ' + '═' * 30, flush=True)
        for slug in slugs:
            result = probe(slug, setup)
            flags = result.get('flags', [])
            if flags:
                findings.setdefault(name, {})[slug] = flags
                print(f'  {slug:24} {len(flags)} FLAG(S)', flush=True)
                for f in flags[:6]:
                    print(f'      {f["kind"]}: {f["detail"]}', flush=True)
            else:
                extra = (f"{result.get('paragraphs', '?')}p "
                         f"{result.get('bars', '?')}bar "
                         f"{result.get('internalLinks', '?')}links")
                print(f'  {slug:24} ok   {extra}', flush=True)
    ab('close')

    print('\n' + '═' * 50)
    total = sum(len(v) for cond in findings.values() for v in cond.values())
    print(f'{total} flag(s) across {sum(len(c) for c in findings.values())} '
          f'doc/condition pairs')
    return 1 if findings else 0


if __name__ == '__main__':
    sys.exit(main())
