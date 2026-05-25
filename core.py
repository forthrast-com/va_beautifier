"""Shared helpers + TOML writer for per-document extractors.

Each `extract/<doc>.py` exposes:

    def extract() -> {
        'name':         str,        # display name, e.g. "Gaudium et Spes"
        'hue':          int,        # web-edition accent hue (CSS hsl degrees)
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

    part, chapter, section, sub_heading, number, text
"""

import re
import tomllib
from pathlib import Path

from bs4 import NavigableString


# ── text helpers ─────────────────────────────────────────────────────────────

def _wrap_inline(text, marker):
    """Wrap visible inline content while keeping source spacing outside marks."""
    match = re.match(r'^(\s*)(.*?)(\s*)$', text, re.DOTALL)
    leading, body, trailing = match.groups()
    return text if not body else f'{leading}{marker}{body}{marker}{trailing}'


def clean_text(element, *, preserve_formatting=False):
    """Extract text and optional inline formatting from source HTML.

    Whitespace within a line is collapsed; line breaks survive. Poetic blocks
    (canticle, prayers) use `<br>` for verse breaks. External hyperlinks in
    the source (vatican.va doc cross-refs in body + footnotes) are kept as
    Markdown-style `[text](href)` markers for the renderer to convert back.
    With `preserve_formatting=True`, authored emphasis and superscript or
    subscript content is retained as Markdown-compatible inline markup.

    Anchors with an `href="#_ftn…"` (the source's footnote backrefs) get their
    wrapper dropped — the bracketed text inside (e.g. `[1]`) is preserved so
    the extractor's `[N]` → `(N)` normalisation still sees it.
    """
    def render(node):
        if isinstance(node, NavigableString):
            return str(node)
        name = getattr(node, 'name', None)
        if name == 'br':
            return '\n'

        content = ''.join(render(child) for child in getattr(node, 'children', ()))
        if name == 'a' and node.get('href'):
            href = node['href']
            if href.startswith('#_ftn'):
                return content
            return f'[{content}]({href})' if content.strip() else ''
        if not preserve_formatting:
            return content
        if name in ('i', 'em'):
            return _wrap_inline(content, '*')
        if name in ('b', 'strong'):
            return _wrap_inline(content, '**')
        if name in ('sup', 'sub'):
            # Source footnote references become renderer-owned linked
            # superscripts, so do not add a second authored wrapper.
            if node.find('a', href=re.compile(r'^#_ftn')):
                return content
            return f'<{name}>{content}</{name}>' if content.strip() else content
        return content

    text = ''.join(render(child) for child in element.children)
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


def br_lines(tag):
    """Return the non-empty text lines of a Vatican `<br>`-separated block."""
    parts = []
    for child in tag.descendants:
        if getattr(child, 'name', None) == 'br':
            parts.append('\n')
        elif isinstance(child, NavigableString):
            parts.append(str(child))
    raw = ''.join(parts)
    return [re.sub(r'\s+', ' ', line).strip()
            for line in raw.splitlines()
            if line.strip()]


def split_around_title(lines, title):
    """Partition front-matter lines around a punctuation-insensitive title."""
    def normalised(text):
        return re.sub(r'[^A-Z ]', '', text.upper()).strip()

    target = normalised(title)
    pre, post, seen = [], [], False
    for line in lines:
        if not seen and normalised(line) == target:
            seen = True
            continue
        (post if seen else pre).append(line)
    return pre, post


def roman_to_int(s):
    vals = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}
    s = s.upper().strip()
    result, prev = 0, 0
    for c in reversed(s):
        curr = vals.get(c, 0)
        result += curr if curr >= prev else -curr
        prev = curr
    return result


def int_to_roman(n):
    pairs = [
        (1000, 'M'), (900, 'CM'), (500, 'D'), (400, 'CD'),
        (100, 'C'), (90, 'XC'), (50, 'L'), (40, 'XL'),
        (10, 'X'), (9, 'IX'), (5, 'V'), (4, 'IV'), (1, 'I'),
    ]
    result = ''
    for value, symbol in pairs:
        while n >= value:
            result += symbol
            n -= value
    return result


def parse_num(s):
    s = s.strip()
    return int(s) if s.isdigit() else roman_to_int(s)


CHAPTER_WORDS = {
    'ONE': 1, 'TWO': 2, 'THREE': 3, 'FOUR': 4, 'FIVE': 5, 'SIX': 6,
    'SEVEN': 7, 'EIGHT': 8, 'NINE': 9, 'TEN': 10,
}


def chapter_word_to_int(word):
    """Return a modern-template `CHAPTER ONE` word as an integer, if known."""
    return CHAPTER_WORDS.get(word)


_INLINE_FOOTNOTE_REF = re.compile(r'\[(\d{1,3})\]')
_SPACE_BEFORE_FOOTNOTE_REF = re.compile(r' +(\(\d{1,3}\))')
# Public contract consumed by renderers: match note markers, not four-digit
# parenthesised years or longer prose citations.
CANONICAL_FOOTNOTE_REF = re.compile(r'\((\d{1,3})\)')


def normalise_footnote_refs(text, *, bracketed=False):
    """Return body or note text with canonical compact `(N)` references.

    Modern source pages use square-bracket references; old-flat documents
    already use parentheses but may contain a stray space before the marker.
    """
    if bracketed:
        text = _INLINE_FOOTNOTE_REF.sub(r'(\1)', text)
    return _SPACE_BEFORE_FOOTNOTE_REF.sub(r'\1', text)


def paragraph_record(number, text, *, part=0, part_title='', chapter=0,
                     chapter_title='', chapter_subtitle='', section=0,
                     section_title='', sub_heading='', heading_la='',
                     bracketed_refs=False):
    """Construct a canonical paragraph record from source text and context."""
    return {
        'number': number,
        'part': part,
        'part_title': part_title,
        'chapter': chapter,
        'chapter_title': chapter_title,
        'chapter_subtitle': chapter_subtitle,
        'section': section,
        'section_title': section_title,
        'sub_heading': sub_heading,
        'heading_la': heading_la,
        'text': normalise_footnote_refs(text.strip(), bracketed=bracketed_refs),
    }


def parse_footnote(text, pattern, *, part=0, chapter=0, bracketed_refs=False):
    """Parse a numbered footnote string using a document-specific regex.

    `pattern` must capture the note number and note body as groups 1 and 2.
    Source-template rules decide which strings are notes; this helper owns
    the canonical footnote record produced once a note has been recognised.
    """
    match = pattern.match(text)
    if not match:
        return None
    return {
        'part': part,
        'chapter': chapter,
        'number': int(match.group(1)),
        'text': normalise_footnote_refs(
            match.group(2).strip(), bracketed=bracketed_refs
        ),
    }


def extract_footnotes(elements, pattern, *, part=0, chapter=0,
                      bracketed_refs=False, preserve_formatting=True):
    """Extract numbered footnotes from an iterable of source elements."""
    footnotes = []
    for element in elements:
        note = parse_footnote(
            clean_text(element, preserve_formatting=preserve_formatting),
            pattern, part=part, chapter=chapter,
            bracketed_refs=bracketed_refs
        )
        if note:
            footnotes.append(note)
    return footnotes


def assign_footnote_context(footnotes, paragraphs, *, preserve_scope=False):
    """Return notes owned by the lowest heading containing their first cite.

    Most documents number notes globally, so the note number alone identifies
    the first citing paragraph. Old-flat documents may already assign a note
    to a part/chapter scope; `preserve_scope=True` keeps that disambiguation
    while filling in its section and sub-heading.
    """
    citations = {}
    for paragraph in paragraphs:
        for ref in CANONICAL_FOOTNOTE_REF.findall(paragraph['text']):
            number = int(ref)
            key = (paragraph['part'], paragraph['chapter'], number)
            citations.setdefault(key, paragraph)
            citations.setdefault(number, paragraph)

    assigned = []
    for note in footnotes:
        scoped_key = (note['part'], note['chapter'], note['number'])
        paragraph = (
            citations.get(scoped_key) if preserve_scope
            else citations.get(note['number'])
        )
        if paragraph is None:
            assigned.append({
                **note,
                'section': note.get('section', 0),
                'sub_heading': note.get('sub_heading', ''),
            })
            continue
        assigned.append({
            **note,
            'part': paragraph['part'],
            'chapter': paragraph['chapter'],
            'section': paragraph['section'],
            'sub_heading': paragraph.get('sub_heading', ''),
        })
    return assigned


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


def read_toml(path):
    with Path(path).open('rb') as source:
        return tomllib.load(source)


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


def write_toml(path, *, name, hue=None, source_url='', desc='', desc_post='',
               promulgation='', signature='', hero_image='', hero_credit='',
               paragraphs, footnotes, appendices=()):
    out = [f'name = {_toml_str(name)}']
    if hue is not None:
        out.append(f'hue = {hue}')
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
        out.append(f'section = {fn.get("section", 0)}')
        out.append(f'sub_heading = {_toml_str(fn.get("sub_heading", ""))}')
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
