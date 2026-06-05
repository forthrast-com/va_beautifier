"""Extractor for *Laudato Si'* — the modern Bootstrap Vatican.va template.

Structure (per <p> tag in <main>):
  - <p align="center">CHAPTER ONE</p>      — chapter delimiter (text → number)
  - <p align="center"><b>TITLE</b></p>     — chapter title (when preceded by CHAPTER N)
  - <p align="left"><b>I. TITLE</b></p>    — section heading (Roman prefix)
  - <p align="left"><i>Sub-heading</i></p> — sub-section heading
  - <p>N. Body text…</p>                   — numbered paragraph
  - <p>[N] Footnote text…</p>              — footnote (at tail of doc)

Inline refs use `[N]`; normalised to canonical `(N)` for the TOML.
No PART tier; no per-paragraph Latin micro-summary.
"""

import re
from bs4 import BeautifulSoup

from core import (
    assign_footnote_context,
    br_lines,
    chapter_word_to_int,
    clean_text,
    normalise_footnote_refs,
    only_child_is,
    paragraph_record,
    parse_footnote,
    roman_to_int,
    split_around_title,
    title_case,
)
from project import SOURCES


EN_SRC = SOURCES / 'laudato_si_en.html'
LT_SRC = SOURCES / 'laudato_si_lt.html'

NAME = "Laudato Si'"
HUE = 140
SOURCE_URL = ('https://www.vatican.va/content/francesco/en/encyclicals/documents/'
              'papa-francesco_20150524_enciclica-laudato-si.html')
AUTHOR = 'Francis'
DATE = '2015-05-24'
IDENTIFIER = 'papal:laudato-si:2015-05-24'

# Front matter is the first centred <p> whose text contains "ENCYCLICAL
# LETTER" — its lines (separated by <br/>) carry the title in the middle.
# Strip the apostrophe variants before matching since the source uses ’
# (RIGHT SINGLE QUOTATION MARK).
TITLE_UPPER = "LAUDATO SI"


# The `\s*` slack absorbs whitespace inserted by BeautifulSoup's text-node
# separator when an inline element falls between the number and its period
# (LS wraps the leading `1.` inside an <a> at every chapter break).
RE_PARA       = re.compile(r'^(\d+)\s*\.\s+(.+)$', re.DOTALL)
RE_FOOTNOTE   = re.compile(r'^\[\s*(\d+)\s*\]\s+(.+)$', re.DOTALL)
RE_SECTION_B  = re.compile(r'^([IVX]+)\s*\.\s+(.+)$')
RE_CHAPTER_C  = re.compile(r'^CHAPTER\s+([A-Z]+)$')

CHROME = ['script', 'style', 'meta', 'link', 'img', 'header',
          'footer', 'nav', 'svg', 'input', 'button', 'figure']


def extract():
    with open(EN_SRC, encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')
    for t in soup(CHROME):
        t.decompose()

    main = soup.find('main') or soup.body
    ps = main.find_all('p')

    # Front matter: the first centred <p> containing "ENCYCLICAL LETTER"
    # carries the preamble + title + subtitle as <br/>-separated lines.
    desc_pre, desc_post = '', ''
    fm_p = next((p for p in ps if 'ENCYCLICAL LETTER' in p.get_text()), None)
    if fm_p:
        pre, post = split_around_title(br_lines(fm_p), TITLE_UPPER)
        desc_pre = '\n'.join(pre)
        desc_post = '\n'.join(post)

    # LS ends with two appended prayers and a "Given in Rome…" promulgation
    # block. None of them are numbered, so without an end-of-body marker
    # they'd be vacuumed up as continuations of §246. Pre-compute the
    # last numbered-paragraph position to cap body accumulation.
    last_body_idx = max(
        (i for i, p in enumerate(ps) if RE_PARA.match(clean_text(p))),
        default=-1,
    )

    paragraphs = []
    footnotes = []
    appendices = []
    promulgation = ''
    signature = ''

    # ─── Phase 1: body walk (idx 0 .. last_body_idx) ─────────────────────
    chapter = 0
    chapter_title = ''
    section = 0
    section_title = ''
    sub_heading = ''
    pending_chapter_num = None

    for i in range(last_body_idx + 1):
        p = ps[i]
        text = clean_text(p)
        if not text:
            continue

        align = (p.get('align') or '').lower()
        has_b = bool(p.find('b'))

        # chapter marker: <p align="center">CHAPTER ONE</p> (no <b>)
        if align == 'center' and not has_b:
            mc = RE_CHAPTER_C.match(text)
            if mc and (chapter_num := chapter_word_to_int(mc.group(1))) is not None:
                pending_chapter_num = chapter_num
                continue

        # centred bold: chapter title (after CHAPTER N) or encyclical title (skip)
        if align == 'center' and has_b:
            if pending_chapter_num is not None:
                chapter = pending_chapter_num
                chapter_title = title_case(text)
                pending_chapter_num = None
                section = 0; section_title = ''
                sub_heading = ''
            continue

        # section heading: <p>'s only child is a <b> whose text matches "I. TITLE".
        # `align="left"` is set on the first section of chapter 1 and nowhere
        # else; child-shape is the reliable signal. The centred chapter title
        # is caught above so won't reach this branch.
        if only_child_is(p, 'b'):
            ms = RE_SECTION_B.match(text)
            if ms:
                section = roman_to_int(ms.group(1))
                section_title = title_case(ms.group(2))
                sub_heading = ''
                continue

        # sub-heading: <p> whose only non-whitespace child is an <i>.
        # The `align` attribute is unreliable: the first sub-heading in a
        # section gets align="left" but subsequent ones come back blank.
        if only_child_is(p, 'i'):
            sub_heading = text
            continue

        # numbered paragraph
        m = RE_PARA.match(text)
        if m:
            rich_match = RE_PARA.match(clean_text(p, preserve_formatting=True))
            paragraphs.append(paragraph_record(
                int(m.group(1)), rich_match.group(2),
                chapter=chapter, chapter_title=chapter_title,
                section=section, section_title=section_title,
                sub_heading=sub_heading, bracketed_refs=True,
            ))
            continue

        # The conclusion is divided from its invitation to prayer by a
        # centred source ornament. Preserve its function, not its glyphs.
        if text == '* * * * *' and paragraphs:
            paragraphs[-1]['break_after'] = True
            continue

        # continuation: unnumbered body para following a numbered one (rare in LS)
        if paragraphs and not has_b:
            paragraphs[-1]['text'] += '\n\n' + normalise_footnote_refs(
                clean_text(p, preserve_formatting=True), bracketed=True
            )

    # ─── Phase 2: appendix walk (last_body_idx+1 .. end) ─────────────────
    # The tail of LS holds: two prayers (each `<i>Title</i>` followed by
    # several body paragraphs), an italic "Given in Rome…" promulgation,
    # a "Franciscus" signature, then the footnotes.
    current = None
    def _flush():
        nonlocal current
        if current and current['text']:
            appendices.append(current)
        current = None

    for i in range(last_body_idx + 1, len(ps)):
        p = ps[i]
        text = clean_text(p)
        if not text:
            continue

        # footnote definitions stream in at the very end
        footnote = parse_footnote(
            clean_text(p, preserve_formatting=True),
            RE_FOOTNOTE, bracketed_refs=True
        )
        if footnote:
            _flush()
            footnotes.append(footnote)
            continue

        # italic-only block: prayer title, the promulgation, or signature
        if only_child_is(p, 'i'):
            if text.startswith('Given in') or text.startswith('Given at'):
                _flush()
                promulgation = clean_text(p, preserve_formatting=True)
                continue
            _flush()
            current = {'title': text, 'kind': 'prayer', 'text': ''}
            continue

        # Centred bold trailer: the papal signature ("Franciscus"). Capture
        # the first one we hit after the promulgation so it can be rendered
        # in the end matter, then keep ignoring any later trailers.
        align = (p.get('align') or '').lower()
        if align == 'center' and p.find('b'):
            if promulgation and not signature:
                signature = clean_text(p, preserve_formatting=True)
            continue

        # body of current prayer
        if current is not None:
            if current['text']:
                current['text'] += '\n\n'
            current['text'] += normalise_footnote_refs(
                clean_text(p, preserve_formatting=True), bracketed=True
            )

    _flush()

    # Store the smallest structural context available for each note. The
    # reader drawer can then render the canonical TOML hierarchy directly.
    footnotes = assign_footnote_context(footnotes, paragraphs)

    return {
        'name': NAME,
        'hue': HUE,
        'source_url': SOURCE_URL,
        'author': AUTHOR,
        'date': DATE,
        'identifier': IDENTIFIER,
        'desc': desc_pre,
        'desc_post': desc_post,
        'promulgation': promulgation,
        'signature': signature,
        'paragraphs': paragraphs,
        'footnotes': footnotes,
        'appendices': appendices,
    }
