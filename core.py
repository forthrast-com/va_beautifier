"""Shared helpers + TOML writer for per-document extractors.

Each `extract/<doc>.py` exposes:

    def extract() -> {
        'name':         str,        # display name, e.g. "Gaudium et Spes"
        'desc':         str,        # multi-line description (may be '')
        'promulgation': str,        # multi-line promulgation (may be '')
        'paragraphs':   list[dict], # per-paragraph dicts (see schema below)
        'footnotes':    list[dict],
    }

Paragraph schema (all keys optional except number, text — defaults to 0 / ''):

    number, part, part_title, chapter, chapter_title,
    section, section_title, sub_heading, heading_la, text

Footnote schema:

    part, chapter, number, text
"""

import re

from bs4 import NavigableString


# ── text helpers ─────────────────────────────────────────────────────────────

def clean_text(element):
    text = element.get_text(separator=' ')
    return re.sub(r'\s+', ' ', text).strip()


def only_child_is(tag, name):
    """True if `tag`'s only non-whitespace direct child is a <name>.

    The modern Vatican.va template (LS) uses 'a <p> whose sole content is an
    <i>' as the sub-heading signal, and 'sole content is a <b>' for section
    headings. Generalised here so future modern-template extractors don't
    re-roll it.
    """
    kids = [c for c in tag.children
            if not (isinstance(c, NavigableString) and not c.strip())]
    return len(kids) == 1 and getattr(kids[0], 'name', None) == name


def roman_to_int(s):
    vals = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}
    s = s.upper().strip()
    result, prev = 0, 0
    for c in reversed(s):
        curr = vals.get(c, 0)
        result += curr if curr >= prev else -curr
        prev = curr
    return result


def parse_num(s):
    s = s.strip()
    return int(s) if s.isdigit() else roman_to_int(s)


_SMALL = {'a', 'an', 'the', 'and', 'but', 'or', 'nor', 'for', 'yet', 'so',
          'at', 'by', 'in', 'of', 'on', 'to', 'up', 'as', 'from', 'with'}

def title_case(s):
    words = s.lower().split()
    result = []
    for i, word in enumerate(words):
        if "'" in word or '’' in word:
            sep = "'" if "'" in word else '’'
            parts = word.split(sep)
            parts[0] = parts[0].capitalize()
            result.append(sep.join(parts))
        elif i == 0 or i == len(words) - 1 or word not in _SMALL:
            result.append(word.capitalize())
        else:
            result.append(word)
    return ' '.join(result)


# ── TOML serialisation ───────────────────────────────────────────────────────

def _toml_str(s):
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'


def _toml_multiline(s):
    escaped = s.replace('\\', '\\\\').replace('"""', '\\"\\"\\"')
    return '"""\n' + escaped + '"""'


_PARA_FIELDS = [
    ('number',        'int'),
    ('part',          'int'),
    ('part_title',    'str'),
    ('chapter',       'int'),
    ('chapter_title', 'str'),
    ('section',       'int'),
    ('section_title', 'str'),
    ('sub_heading',   'str'),
    ('heading_la',    'str'),
    ('text',          'mlstr'),
]


def write_toml(path, *, name, desc='', promulgation='', paragraphs, footnotes, appendices=()):
    out = [f'name = {_toml_str(name)}']
    if desc:
        out.append(f'desc = {_toml_multiline(desc)}')
    if promulgation:
        out.append(f'promulgation = {_toml_multiline(promulgation)}')
    out.append('')

    for p in paragraphs:
        out.append('[[paragraphs]]')
        for key, kind in _PARA_FIELDS:
            if kind == 'int':
                out.append(f'{key} = {p.get(key, 0)}')
            elif kind == 'str':
                out.append(f'{key} = {_toml_str(p.get(key, ""))}')
            else:  # mlstr
                out.append(f'{key} = {_toml_multiline(p.get(key, ""))}')
        out.append('')

    for fn in footnotes:
        out.append('[[footnotes]]')
        out.append(f'part = {fn.get("part", 0)}')
        out.append(f'chapter = {fn.get("chapter", 0)}')
        out.append(f'number = {fn["number"]}')
        out.append(f'text = {_toml_multiline(fn["text"])}')
        out.append('')

    for app in appendices:
        out.append('[[appendices]]')
        out.append(f'title = {_toml_str(app["title"])}')
        out.append(f'text = {_toml_multiline(app["text"])}')
        out.append('')

    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(out))
