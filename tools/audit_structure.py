#!/usr/bin/env python3
"""Print a document's structural tree for eyeballing.

Renders each built TOML as an indented part › chapter › section tree with
paragraph ranges, plus footnote/appendix counts — the view you want on the
day you write a new extractor and need to *see* the walker's output before
trusting it. Machine-checkable invariants live in
``tests/test_pipeline_invariants.py``; this is the human-side complement.

Usage: ``python3 tools/audit_structure.py [slug …]`` — defaults to every
implemented document with a built TOML. Run ``make`` (or
``python3 parse.py <slug>``) first; this reads ``build/<slug>.toml``.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import read_toml
from gen_doc_rules import implemented_docs
from project import ROOT

BUILD = ROOT / 'build'


def tree(data):
    """(heading-key, first §, last §) runs in reading order."""
    runs = []
    last_key = run_start = run_end = None
    for p in data['paragraphs']:
        key = (p['part'], p.get('part_title', ''), p['chapter'],
               p.get('chapter_title', ''), p['section'],
               p.get('section_title', ''))
        if key != last_key:
            if last_key is not None:
                runs.append((last_key, run_start, run_end))
            last_key, run_start = key, p['number']
        run_end = p['number']
    if last_key is not None:
        runs.append((last_key, run_start, run_end))
    return runs


def show(slug):
    path = BUILD / f'{slug}.toml'
    if not path.exists():
        print(f'=== {slug} — no {path.relative_to(ROOT)}; '
              f'run `python3 parse.py {slug}` first ===')
        return
    data = read_toml(path)
    print(f'\n=== {slug} — {data["name"]} ===')
    print(f'{len(data["paragraphs"])} paragraphs, '
          f'{len(data.get("footnotes", []))} footnotes, '
          f'{len(data.get("appendices", []))} appendices')

    for (part, pt, ch, cht, sec, sect), a, b in tree(data):
        rng = f'§{a}' if a == b else f'§{a}–{b}'
        indent = ''
        label = []
        if part or pt:
            label.append(f'P{part} {pt}'.strip())
        if ch or cht:
            indent = '  '
            label.append(f'ch{ch} {cht}'.strip())
        if sec or sect:
            indent = '    '
            label.append(f's{sec} {sect}'.strip())
        print(f'{indent}{" › ".join(label) or "(preamble)"}  [{rng}]')

    for i, a in enumerate(data.get('appendices', []), 1):
        kind = f" ({a['kind']})" if a.get('kind') else ''
        print(f'appendix {i}: {a["title"]}{kind}')


def main():
    slugs = sys.argv[1:] or [slug for slug, _ in implemented_docs()]
    for slug in slugs:
        show(slug)


if __name__ == '__main__':
    main()
