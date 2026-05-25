"""Shared helpers + TOML writer for per-document extractors.

Each `extract/<doc>.py` exposes:

    def extract() -> {
        'name':         str,        # display name, e.g. "Gaudium et Spes"
        'source_url':   str,        # original Vatican HTML edition
        'desc':         str,        # multi-line preamble shown ABOVE the title (may be '')
        'desc_post':    str,        # multi-line subtitle shown BELOW the title (may be '')
        'promulgation': str,        # multi-line promulgation (may be '')
        'signature':    str,        # papal signature line, e.g. "Franciscus" (may be '')
        'hero_image':   str,        # path to title-page image, repo-relative (may be '')
        'hero_credit':  str,        # one-line credit/caption shown beneath the image (may be '')
        'paragraphs':   list[dict], # per-paragraph dicts (see schema below)
        'footnotes':    list[dict],
    }

Paragraph schema (all keys optional except number, text — defaults to 0 / ''):

    number, part, part_title, chapter, chapter_title, chapter_subtitle,
    section, section_title, sub_heading, heading_la, break_after, text

Footnote schema:

    part, chapter, number, text
"""

import re

from bs4 import NavigableString


# ── text helpers ─────────────────────────────────────────────────────────────

def clean_text(element):
    """Extract text, preserving `<br>` as `\\n` and `<a href>` as `[text](href)`.

    Whitespace within a line is collapsed; line breaks survive. Poetic blocks
    (canticle, prayers) use `<br>` for verse breaks. External hyperlinks in
    the source (vatican.va doc cross-refs in body + footnotes) are kept as
    markdown-style `[text](href)` markers for the renderer to convert back.

    Anchors with an `href="#_ftn…"` (the source's footnote backrefs) get their
    wrapper dropped — the bracketed text inside (e.g. `[1]`) is preserved so
    the extractor's `[N]` → `(N)` normalisation still sees it.
    """
    chunks = []
    for desc in element.descendants:
        name = getattr(desc, 'name', None)
        if name == 'br':
            chunks.append('\n')
        elif name == 'a' and desc.get('href'):
            href = desc['href']
            text = re.sub(r'\s+', ' ', desc.get_text(separator=' ')).strip()
            if href.startswith('#_ftn'):
                # Internal source-footnote anchor — keep just the text content.
                if text:
                    chunks.append(text)
            elif text:
                chunks.append(f'[{text}]({href})')
        elif isinstance(desc, NavigableString):
            # Children of an anchor we already captured — skip to avoid dupes.
            parent_a = desc.find_parent('a')
            if parent_a is not None and parent_a.get('href'):
                continue
            chunks.append(str(desc))
    text = ''.join(chunks)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r' *\n *', '\n', text)
    return text.strip()


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

# Roman numerals (papal regnal numbers, council numerals like Vatican II,
# etc.) should survive an uppercase → title-case round-trip unchanged.
# Match the letter cluster ignoring trailing punctuation; reject the
# degenerate single-character cases I/L/D/M that almost always mean an
# initial or word in normal prose.
_ROMAN = re.compile(r'^[IVXLCDM]{2,}$')


def title_case(s, *, cap_last=True, small_words=False):
    """Dumb title case: capitalise every word, force small words ("of",
    "the", "in"…) to lowercase, and preserve Roman numerals.

    With `small_words=False` (default), the *first* word is always
    capitalised — even if it's a small word — so chapter and section
    titles like "A Dynamic Approach Faithful to the Gospel" keep their
    leading article. With `small_words=True`, small words stay lowercase
    everywhere, suitable for fragments like "of the Holy Father" sitting
    inside a centred multi-line subtitle.

    `cap_last` is accepted for back-compat but is a no-op — trailing
    small words always stay lowercase."""
    del cap_last  # always treated as dumb-title-case
    words = s.split()
    result = []
    for i, word in enumerate(words):
        # Strip surrounding punctuation for the Roman test so "VI," still
        # registers as a numeral.
        core = word.strip('.,;:!?"\'’“”()[]')
        if _ROMAN.match(core):
            result.append(word)
            continue
        lo = word.lower()
        if "'" in lo or '’' in lo:
            sep = "'" if "'" in lo else '’'
            parts = lo.split(sep)
            parts[0] = parts[0].capitalize()
            result.append(sep.join(parts))
        elif lo in _SMALL and (small_words or i > 0):
            result.append(lo)
        else:
            result.append(lo.capitalize())
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
    ('chapter_subtitle', 'str'),
    ('section',       'int'),
    ('section_title', 'str'),
    ('sub_heading',   'str'),
    ('heading_la',    'str'),
    ('break_after',   'bool'),
    ('text',          'mlstr'),
]


def write_toml(path, *, name, source_url='', desc='', desc_post='',
               promulgation='', signature='', hero_image='', hero_credit='',
               paragraphs, footnotes, appendices=()):
    out = [f'name = {_toml_str(name)}']
    if source_url:
        out.append(f'source_url = {_toml_str(source_url)}')
    if desc:
        out.append(f'desc = {_toml_multiline(desc)}')
    if desc_post:
        out.append(f'desc_post = {_toml_multiline(desc_post)}')
    if promulgation:
        out.append(f'promulgation = {_toml_multiline(promulgation)}')
    if signature:
        out.append(f'signature = {_toml_str(signature)}')
    if hero_image:
        out.append(f'hero_image = {_toml_str(hero_image)}')
    if hero_credit:
        out.append(f'hero_credit = {_toml_str(hero_credit)}')
    out.append('')

    for p in paragraphs:
        out.append('[[paragraphs]]')
        for key, kind in _PARA_FIELDS:
            if kind == 'int':
                out.append(f'{key} = {p.get(key, 0)}')
            elif kind == 'str':
                out.append(f'{key} = {_toml_str(p.get(key, ""))}')
            elif kind == 'bool':
                out.append(f'{key} = {str(p.get(key, False)).lower()}')
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
