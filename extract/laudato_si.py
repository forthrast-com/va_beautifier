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

from core import (
    HeadingState,
    assign_footnote_context,
    clean_text,
    is_centred,
    is_promulgation,
    normalise_footnote_refs,
    numbered_paragraph,
    only_child_is,
    paragraph_record,
    parse_footnote,
    roman_to_int,
    title_case,
)
from project import SOURCES

from ._modern import chapter_word_marker, encyclical_front_matter, load_main


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


def extract():
    soup, main = load_main(EN_SRC, drop_chrome=True)
    ps = main.find_all('p')

    # Front matter: the first centred <p> containing "ENCYCLICAL LETTER"
    # carries the preamble + title + subtitle as <br/>-separated lines.
    fm_p = next((p for p in ps if 'ENCYCLICAL LETTER' in p.get_text()), None)
    desc_pre, desc_post = encyclical_front_matter(fm_p, TITLE_UPPER)

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
    state = HeadingState()
    pending_chapter_num = None

    for i in range(last_body_idx + 1):
        p = ps[i]
        text = clean_text(p)
        if not text:
            continue

        has_b = bool(p.find('b'))

        # chapter marker: <p align="center">CHAPTER ONE</p> (no <b>)
        if is_centred(p) and not has_b:
            chapter_num = chapter_word_marker(text)
            if chapter_num is not None:
                pending_chapter_num = chapter_num
                continue

        # centred bold: chapter title (after CHAPTER N) or encyclical title (skip)
        if is_centred(p) and has_b:
            if pending_chapter_num is not None:
                state.set_chapter(pending_chapter_num, title_case(text))
                pending_chapter_num = None
            continue

        # section heading: <p>'s only child is a <b> whose text matches "I. TITLE".
        # `align="left"` is set on the first section of chapter 1 and nowhere
        # else; child-shape is the reliable signal. The centred chapter title
        # is caught above so won't reach this branch.
        if only_child_is(p, 'b'):
            ms = RE_SECTION_B.match(text)
            if ms:
                state.set_section(roman_to_int(ms.group(1)),
                                  title_case(ms.group(2)))
                continue

        # sub-heading: <p> whose only non-whitespace child is an <i>.
        # The `align` attribute is unreliable: the first sub-heading in a
        # section gets align="left" but subsequent ones come back blank.
        if only_child_is(p, 'i'):
            state.sub_heading = text
            continue

        numbered = numbered_paragraph(p, RE_PARA)
        if numbered:
            paragraphs.append(paragraph_record(
                *numbered, bracketed_refs=True, **state.kwargs(),
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
            if is_promulgation(text):
                _flush()
                promulgation = clean_text(p, preserve_formatting=True)
                continue
            _flush()
            current = {'title': text, 'kind': 'prayer', 'text': ''}
            continue

        # Centred bold trailer: the papal signature ("Franciscus"). Capture
        # the first one we hit after the promulgation so it can be rendered
        # in the end matter, then keep ignoring any later trailers.
        if is_centred(p) and p.find('b'):
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
        'issued_by': 'Francis',
        'pontificate': 'Francis',
        'date': DATE,
        'identifier': IDENTIFIER,
        # The pope is already named in `desc` ("ENCYCLICAL LETTER OF
        # THE HOLY FATHER FRANCIS"), so the title-page foot stays bare.
        'show_title_author': False,
        'desc': desc_pre,
        'desc_post': desc_post,
        'promulgation': promulgation,
        'signature': signature,
        'paragraphs': paragraphs,
        'footnotes': footnotes,
        'appendices': appendices,
    }
