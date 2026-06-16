"""Shared helpers + TOML writer for per-document extractors.

Each `extract/<doc>.py` exposes:

    def extract() -> {
        'name':         str,        # display name, e.g. "Gaudium et Spes"
        'hue':          int,        # web-edition accent hue (CSS hsl degrees)
        'source_url':   str,        # original Vatican HTML edition
        'author':       str,        # dc:creator for EPUB; pope, council, dicastery (may be '')
        'issued_by':    str,        # institutional/personal voice shown in catalogue + colophon
        'pontificate':  str,        # pope under whom issued; omitted from display when same as issued_by
        'date':         str,        # promulgation date ISO 8601 yyyy-mm-dd (may be '')
        'identifier':   str,        # urn suffix, e.g. "papal:laudato-si:2015-05-24" (may be '')
        'rights':       str,        # dc:rights line for EPUB (may be '')
        'type':         str,        # catalogue tile class, e.g. "encyclical" (may be '')
        'subtitle':     str,        # catalogue tile subtitle for most docs (may be '')
        'kind_long':    str,        # catalogue tile subtitle for council docs (may be '')
        'desc':         str,        # multi-line preamble shown ABOVE the title (may be '')
        'desc_post':    str,        # multi-line subtitle shown BELOW the title (may be '')
        'chapter_style': str,        # optional numbering style, currently "roman"
        'book_toc_depth': int,       # optional PDF contents depth (default 3)
        'promulgation': str,        # canonical inline markup; blank lines split stanzas
        'signature':    str,        # canonical inline markup; line breaks are significant
        'signatories':  list[dict], # optional end-matter name/role pairs
        'paragraphs':   list[dict], # per-paragraph dicts (see schema below)
        'footnotes':    list[dict],
    }

The imprint (`publisher`, `collection`) is taken from DEFAULT_PUBLISHER /
DEFAULT_COLLECTION when the extractor doesn't override.

Paragraph schema (all keys optional except number, text — defaults to 0 / ''):

    number, part, part_title, chapter, chapter_title, chapter_subtitle,
    section, section_title, sub_heading, heading_la, break_after,
    hide_number, text

Footnote schema:

    part, chapter, section, sub_heading, number, text

Appendix schema:

    title, text, kind  # optional presentation role, e.g. "prayer"

Signatory schema:

    name, role
"""

import html
import re
import tomllib
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString


# ── text helpers ─────────────────────────────────────────────────────────────

def make_soup(markup):
    """Parse a markup string with the project's standard parser.

    Centralises the `html.parser` choice every extractor otherwise spells
    out — loaders, the front-matter probe, and the footnote-slice reparse
    spots alike. The file *encoding* stays at the call site: it's a dialect
    bit (utf-8 for modern and Curia, iso-8859-1 for old-flat), not a parser
    concern, so a `utf-8` default here would only invite old-flat to forget
    its override.
    """
    return BeautifulSoup(markup, 'html.parser')


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


def flatten_ws(text):
    """Collapse every run of whitespace — *including* newlines — to one space.

    The flatten counterpart to `clean_text`, which preserves line breaks
    because body prose needs them. Use `flatten_ws` where line breaks are
    layout noise rather than content: Word-export headings and footnotes
    that wrap mid-phrase, all-caps source headings, &c.
    """
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


def br_text(tag):
    """get_text but with `<br/>` rendered as `\\n` — keeps line breaks for
    front matter. Unlike `br_lines`, returns one string with the breaks in
    place rather than a list of non-empty lines."""
    parts = []
    for child in tag.descendants:
        if getattr(child, 'name', None) == 'br':
            parts.append('\n')
        elif isinstance(child, NavigableString):
            parts.append(str(child))
    return re.sub(r'[ \t]+', ' ', ''.join(parts)).strip()


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


def encyclical_split(desc_pre, desc_post):
    """Pivot encyclical front matter at the first ``On …`` line.

    Vatican.va serves an encyclical's front matter as a single stack of
    ``<br>``-separated lines (``ENCYCLICAL LETTER`` / ``OF HIS HOLINESS`` /
    ``POPE LEO XIV`` / ``ON SAFEGUARDING …``); whichever split rule the
    extractor uses, the issuing lines and the subject line tend to end up
    in the same bucket. The title page reads better when the issuer sits
    above the title and the subject below: this fixup walks down
    ``desc_post`` until it hits a line beginning with ``On `` and moves
    everything before that to ``desc_pre``.

    Returns ``(desc_pre, desc_post)`` unchanged when no ``On …`` line is
    present (e.g. for non-encyclical fronts).
    """
    if not desc_post:
        return desc_pre, desc_post
    post_lines = [ln for ln in desc_post.splitlines() if ln.strip()]
    on_idx = next(
        (i for i, ln in enumerate(post_lines)
         if ln.strip().upper().startswith('ON ')),
        None,
    )
    if on_idx in (None, 0):
        return desc_pre, desc_post
    pre_lines = [ln for ln in (desc_pre or '').splitlines() if ln.strip()]
    return (
        '\n'.join(pre_lines + post_lines[:on_idx]),
        '\n'.join(post_lines[on_idx:]),
    )


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


def ch_order_label(p):
    """Drawer/contents label for a paragraph's (part, chapter) entry.

    Four cases:
        (0, 0)         — preface / introduction; reuse the part_title.
        (0, N)         — top-level chapter under no part; just chapter_title.
        (P, 0), P > 0  — the part-intro paragraphs. The entry IS the part
                         heading itself, so it should read 'Part II: Some
                         Problems of Special Urgency', not the previous
                         'Part II, Ch. 0' fallback.
        (P, N), P > 0  — chapter under a part; chapter_title with a
                         'Part X, Ch. Y' fallback when chapter_title is
                         missing.
    """
    if p['part'] == 0 and p['chapter'] == 0:
        return p['part_title']
    if p['part'] == 0:
        return p['chapter_title']
    if p['chapter'] == 0:
        roman = int_to_roman(p['part'])
        return f'Part {roman}: {p["part_title"]}' if p['part_title'] else f'Part {roman}'
    return p['chapter_title'] or f'Part {int_to_roman(p["part"])}, Ch. {p["chapter"]}'


CHAPTER_WORDS = {
    'ONE': 1, 'TWO': 2, 'THREE': 3, 'FOUR': 4, 'FIVE': 5, 'SIX': 6,
    'SEVEN': 7, 'EIGHT': 8, 'NINE': 9, 'TEN': 10,
}


def chapter_word_to_int(word):
    """Return a modern-template `CHAPTER ONE` word as an integer, if known."""
    return CHAPTER_WORDS.get(word)


PROMULGATION_PREFIXES = ('Given in ', 'Given at ')


def is_promulgation(text):
    """True for the `Given in/at …` dateline that opens document end matter."""
    return text.startswith(PROMULGATION_PREFIXES)


def is_centred(tag):
    """True when a source paragraph is centred by attribute or inline style.

    The flat and Bootstrap templates use `align="center"`; Word exports
    carry `text-align:center` in `style`. Both signal structure (chapter
    markers, signatures), never body prose.
    """
    if (tag.get('align') or '').lower() == 'center':
        return True
    style = (tag.get('style') or '').lower().replace(' ', '')
    return 'text-align:center' in style


_INLINE_FOOTNOTE_REF = re.compile(r'\[(\d{1,3})\]')
_SPACE_BEFORE_FOOTNOTE_REF = re.compile(r' +(\(\d{1,3}\))')
_SUPERSCRIPT_FOOTNOTE_REF = re.compile(
    r'(?:<sup>\s*)+(\(\d{1,3}\))(?:\s*</sup>)+'
)
# Public contract consumed by renderers: match note markers, not four-digit
# parenthesised years or longer prose citations. The negative lookbehind
# skips a `(N)` glued to a preceding digit — Psalm dual-numbering such as
# `Ps 73(72):25` (Hebrew vs Septuagint), not a footnote cite.
CANONICAL_FOOTNOTE_REF = re.compile(r'(?<!\d)\((\d{1,3})\)')

# A footnote *definition* line, `[N] body…`, as the modern Bootstrap pages
# and the old-flat NOTES block both spell it. Shared by every extractor that
# reads bracketed notes (LF, MH, VD, SC); pass it to `parse_footnote` /
# `extract_footnotes`. (`RE_PARA` is deliberately *not* shared — its `\.`
# vs `\s*\.` spacing varies per source.)
RE_FOOTNOTE = re.compile(r'^\[\s*(\d+)\s*\]\s*(.+)$', re.DOTALL)


def normalise_footnote_refs(text, *, bracketed=False):
    """Return body or note text with canonical compact `(N)` references.

    Modern source pages use square-bracket references; old-flat documents
    already use parentheses but may contain a stray space before the marker.
    """
    if bracketed:
        text = _INLINE_FOOTNOTE_REF.sub(r'(\1)', text)
    text = _SUPERSCRIPT_FOOTNOTE_REF.sub(r'\1', text)
    return _SPACE_BEFORE_FOOTNOTE_REF.sub(r'\1', text)


# Works cited by paragraph number (`Dignitas infinita, 6. 11.` → `, nn. 6, 11`).
# When a note mentions one of these, a trailing `N. M.` is treated as a mangled
# paragraph list rather than a sentence boundary.
KNOWN_PARAGRAPH_CITED = (
    'Dignitas infinita',
)

_NUMERIC_HYPHEN = re.compile(r'(?<=\d)-(?=\d)')
_PARAGRAPH_CITED_RANGE = re.compile(r',\s+(\d+)\.\s+(\d+)\.\s*$')


def normalise_footnote_text(text):
    """Repair footnote-only typographic artefacts.

    Currently: en-dashes between numeric ranges (`843-844` → `843–844`,
    `Prov 8:22-31` → `Prov 8:22–31`), and mangled paragraph citations of
    paragraph-cited works (`Dignitas infinita, 6. 11.` → `, nn. 6, 11`).

    Body prose is intentionally left alone (see paragraph_record); add an
    explicit body-text hook only when a real artefact warrants it.
    """
    text = _NUMERIC_HYPHEN.sub('–', text)
    if any(work in text for work in KNOWN_PARAGRAPH_CITED):
        text = _PARAGRAPH_CITED_RANGE.sub(r', nn. \1, \2.', text)
    return text


def notes_between_anchors(markup, anchor_re, *, text_of):
    """Build footnote dicts from definition anchors embedded in raw `markup`.

    For footnote definitions that aren't wrapped one-per-tag: each `anchor_re`
    match opens a note whose body runs from the end of that anchor to the
    start of the next (or end of string). `anchor_re` must capture the note
    number in group 1; `text_of(slice_markup) -> str` re-parses one body
    slice into the note text — it owns the wrapper tag and any
    dialect-specific repair. The boundary arithmetic and the `part`/`chapter`
    note-dict shape are shared verbatim by the Word-export (`_curia`,
    `_ftnN`) and Fides et Ratio (`%24N`) definition schemes.
    """
    matches = list(anchor_re.finditer(markup))
    notes = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markup)
        notes.append({
            'part': 0,
            'chapter': 0,
            'number': int(match.group(1)),
            'text': text_of(markup[match.end():end]),
        })
    return notes


class HeadingState:
    """Cascading heading context for extractor body walks.

    Setting a level clears everything beneath it (part → chapter →
    section → sub-heading), so a walker cannot forget a reset — the
    historical extractor bug class. Direct attribute assignment remains
    available for dialect quirks that genuinely don't cascade (a part
    title arriving in the paragraph after its `PART N` marker, a
    sub-heading observed mid-section).
    """

    def __init__(self):
        self.part = 0
        self.part_title = ''
        self.set_chapter(0)

    def set_part(self, number, title=''):
        self.part = number
        self.part_title = title
        self.set_chapter(0)

    def set_chapter(self, number, title='', subtitle=''):
        self.chapter = number
        self.chapter_title = title
        self.chapter_subtitle = subtitle
        self.set_section(0)

    def set_section(self, number, title=''):
        self.section = number
        self.section_title = title
        self.sub_heading = ''

    def add_section(self, title=''):
        """Open the next auto-numbered section under the current chapter.

        The modern encyclicals (LF, MH, FeR, VD) divide a chapter with
        unnumbered bold topical headers; each becomes the next section in
        sequence. Sugar over `set_section(self.section + 1, …)`.
        """
        self.set_section(self.section + 1, title)

    def kwargs(self):
        """The context keywords accepted by `paragraph_record`."""
        return {
            'part': self.part,
            'part_title': self.part_title,
            'chapter': self.chapter,
            'chapter_title': self.chapter_title,
            'chapter_subtitle': self.chapter_subtitle,
            'section': self.section,
            'section_title': self.section_title,
            'sub_heading': self.sub_heading,
        }


def numbered_paragraph(tag, pattern, *, plain_text=None, rich_text=None):
    """Return `(number, body)` when `tag` is a numbered body paragraph.

    The dialect's plain text decides whether the paragraph matches; the
    formatting-preserving text is then re-matched so the recorded body
    keeps its inline markup. Dialects with their own text repair (Curia
    whitespace collapse, QVH's link stripping) supply it via
    `plain_text` / `rich_text`. Every extractor previously hand-rolled
    this double match.
    """
    plain = plain_text(tag) if plain_text else clean_text(tag)
    match = pattern.match(plain)
    if not match:
        return None
    rich = (rich_text(tag) if rich_text
            else clean_text(tag, preserve_formatting=True))
    rich_match = pattern.match(rich)
    return int(match.group(1)), (rich_match or match).group(2)


def paragraph_record(number, text, *, part=0, part_title='', chapter=0,
                     chapter_title='', chapter_subtitle='', section=0,
                     section_title='', sub_heading='', heading_la='',
                     bracketed_refs=False):
    """Construct a canonical paragraph record from source text and context."""
    # Body prose is *not* run through normalise_footnote_text — Word-export
    # artefacts in body text are rare enough that a generic pass risks more
    # false positives than fixes. Reattach if a real artefact warrants it.
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
        'text': normalise_footnote_text(
            normalise_footnote_refs(
                match.group(2).strip(), bracketed=bracketed_refs
            )
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


# ── canonical inline markup ──────────────────────────────────────────────────
# Authored inline formatting (`*em*`, `**strong**`, `<sup>…</sup>`,
# `<sub>…</sub>`) is canonical content in paragraph and footnote text. The
# renderers all consume the regexes and converter below; they previously
# re-rolled their own copies and quietly diverged on whether emphasis could
# span a poetic line break.

INLINE_STRONG_EM_RE = re.compile(r'\*\*\*(.+?)\*\*\*', re.DOTALL)
INLINE_STRONG_RE = re.compile(r'\*\*(.+?)\*\*', re.DOTALL)
INLINE_EM_RE = re.compile(r'(?<!\*)\*(.+?)\*(?!\*)', re.DOTALL)
# Single-pass alternation for converters that walk match-by-match (Typst):
# group 1 = strong content, group 2 = em content.
INLINE_MARK_RE = re.compile(
    rf'{INLINE_STRONG_RE.pattern}|{INLINE_EM_RE.pattern}', re.DOTALL
)
_ESCAPED_SCRIPT_RE = re.compile(r'&lt;(sup|sub)&gt;(.*?)&lt;/\1&gt;', re.DOTALL)


def inline_markup_to_html(text, *, escaped=False, break_tag=''):
    """Convert canonical inline markup to HTML.

    `escaped=True` means the caller already HTML-escaped the text (the web
    renderer escapes line-by-line before linkifying footnote refs, so real
    tags are present by the time markup converts). Escaped `<sup>`/`<sub>`
    wrappers are restored, then `***strong-em***`, `**strong**`, and `*em*`
    convert. A non-empty `break_tag` (`'<br>'` for the web, `'<br />'` for
    EPUB XHTML) replaces surviving newlines.
    """
    if not escaped:
        text = html.escape(text)
    text = _ESCAPED_SCRIPT_RE.sub(r'<\1>\2</\1>', text)
    text = INLINE_STRONG_EM_RE.sub(r'<strong><em>\1</em></strong>', text)
    text = INLINE_STRONG_RE.sub(r'<strong>\1</strong>', text)
    text = INLINE_EM_RE.sub(r'<em>\1</em>', text)
    return text.replace('\n', break_tag) if break_tag else text


_SMALL = {'a', 'an', 'the', 'and', 'but', 'or', 'nor', 'for', 'yet', 'so',
          'at', 'by', 'in', 'of', 'on', 'to', 'up', 'as', 'from', 'with'}

# Roman numerals (papal regnal numbers, council numerals like Vatican II,
# etc.) should survive an uppercase → title-case round-trip unchanged.
# Require canonical numeral order so ordinary words composed only of Roman
# letters, notably "CIVIC", are not mistaken for numerals.
_ROMAN = re.compile(
    r'^M{0,3}(?:CM|CD|D?C{0,3})(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3})$'
)


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
        if len(core) > 1 and _ROMAN.fullmatch(core):
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


def heading_title(value):
    """Normalise an all-caps source heading to title case, preserving "AI".

    Mixed-case headings pass through untouched (beyond whitespace
    collapse) — only fully upper-case strings are presumed to be source
    shouting rather than authored casing.
    """
    value = re.sub(r'\s+', ' ', value).strip()
    if value == value.upper():
        return title_case(value).replace(' Ai', ' AI')
    return value


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


DEFAULT_PUBLISHER = 'circulars.forthrast.com'
DEFAULT_COLLECTION = 'The Circulars (Vatican documents)'


def write_toml(path, *, name, hue=None, source_url='',
               author='', issued_by='', pontificate='', date='', identifier='', rights='',
               publisher=DEFAULT_PUBLISHER, collection=DEFAULT_COLLECTION,
               type='', subtitle='', kind_long='',
               desc='', desc_post='', chapter_style='', book_toc_depth=3,
               promulgation='', signature='', show_title_author=True,
               paragraphs, footnotes, appendices=(), signatories=()):
    out = [f'name = {_toml_str(name)}']
    if hue is not None:
        out.append(f'hue = {hue}')
    if source_url:
        out.append(f'source_url = {_toml_str(source_url)}')
    if author:
        out.append(f'author = {_toml_str(author)}')
    if issued_by:
        out.append(f'issued_by = {_toml_str(issued_by)}')
    if pontificate:
        out.append(f'pontificate = {_toml_str(pontificate)}')
    if date:
        out.append(f'date = {_toml_str(date)}')
    if identifier:
        out.append(f'identifier = {_toml_str(identifier)}')
    if publisher:
        out.append(f'publisher = {_toml_str(publisher)}')
    if collection:
        out.append(f'collection = {_toml_str(collection)}')
    if type:
        out.append(f'type = {_toml_str(type)}')
    if subtitle:
        out.append(f'subtitle = {_toml_str(subtitle)}')
    if kind_long:
        out.append(f'kind_long = {_toml_str(kind_long)}')
    if rights:
        out.append(f'rights = {_toml_str(rights)}')
    if desc:
        out.append(f'desc = {_toml_multiline(desc)}')
    if desc_post:
        out.append(f'desc_post = {_toml_multiline(desc_post)}')
    if chapter_style:
        out.append(f'chapter_style = {_toml_str(chapter_style)}')
    if book_toc_depth != 3:
        out.append(f'book_toc_depth = {book_toc_depth}')
    if promulgation:
        out.append(f'promulgation = {_toml_multiline(promulgation)}')
    if signature:
        # Structural line breaks in an end-matter signature must survive
        # the canonical intermediate for each output renderer.
        if '\n' in signature:
            out.append(f'signature = {_toml_multiline(signature)}')
        else:
            out.append(f'signature = {_toml_str(signature)}')
    if not show_title_author:
        out.append('show_title_author = false')
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
        if p.get('hide_number', False):
            out.append('hide_number = true')
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
        if app.get('kind'):
            out.append(f'kind = {_toml_str(app["kind"])}')
        out.append(f'text = {_toml_multiline(app["text"])}')
        out.append('')

    for signatory in signatories:
        out.append('[[signatories]]')
        out.append(f'name = {_toml_str(signatory.get("name", ""))}')
        out.append(f'role = {_toml_str(signatory.get("role", ""))}')
        out.append('')

    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(out))
