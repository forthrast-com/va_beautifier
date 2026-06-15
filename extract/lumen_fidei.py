"""Extractor for *Lumen Fidei* — Francis's 2013 encyclical on faith.

Modern Bootstrap dialect, close kin to *Laudato Si'*: word-based
`CHAPTER ONE` markers followed by a centred-bold scriptural chapter title,
and unnumbered bold topical headers within each chapter (mapped to
auto-numbered sections, like *Magnifica Humanitas*). There is no Roman
section tier and no appendix.

The one wrinkle versus LS: every footnote anchor carries an *absolute*
cross-document href, so the anchors are unwrapped to their `[N]` text
(`_modern.strip_footnote_anchors`) before the canonical `[N]` → `(N)`
normalisation runs.

Structure (per <p> in <main>):
  - <p align="center">CHAPTER ONE</p>           — chapter delimiter (word)
  - <p align="center"><b>TITLE (cf. …)</b></p>  — chapter title
  - <p><b>Topical header</b></p>                — section (auto-numbered)
  - <p>N. Body…</p>                             — numbered paragraph
  - <p>[N] Footnote…</p>                        — footnote definition (tail)
"""

import re

from core import (
    HeadingState,
    assign_footnote_context,
    clean_text,
    heading_title,
    is_centred,
    is_promulgation,
    normalise_footnote_refs,
    numbered_paragraph,
    only_child_is,
    paragraph_record,
    parse_footnote,
    title_case,
)
from project import SOURCES

from ._modern import (
    chapter_word_marker,
    encyclical_front_matter,
    load_main,
    strip_footnote_anchors,
)


EN_SRC = SOURCES / 'lumen_fidei_en.html'

NAME = 'Lumen Fidei'
HUE = 48
SOURCE_URL = ('https://www.vatican.va/content/francesco/en/encyclicals/documents/'
              'papa-francesco_20130629_enciclica-lumen-fidei.html')
AUTHOR = 'Francis'
DATE = '2013-06-29'
IDENTIFIER = 'papal:lumen-fidei:2013-06-29'

TITLE_UPPER = 'LUMEN FIDEI'

RE_PARA = re.compile(r'^(\d+)\s*\.\s+(.+)$', re.DOTALL)
RE_FOOTNOTE = re.compile(r'^\[\s*(\d+)\s*\]\s*(.+)$', re.DOTALL)

# title_case capitalises the `cf` of a parenthetical scripture citation
# ("(cf. 1 Jn 4:16)"); restore the lower-case scholarly abbreviation.
_CF_FIX = re.compile(r'\(Cf\.')


def _chapter_title(text):
    return _CF_FIX.sub('(cf.', title_case(text))


def extract():
    soup, main = load_main(EN_SRC, drop_chrome=True)
    strip_footnote_anchors(soup)
    ps = main.find_all('p')

    fm_p = next((p for p in ps if 'ENCYCLICAL LETTER' in p.get_text()), None)
    desc_pre, desc_post = encyclical_front_matter(fm_p, TITLE_UPPER)

    # The body ends at the last numbered paragraph; the promulgation,
    # signature, and footnote definitions all trail it unnumbered.
    last_body_idx = max(
        (i for i, p in enumerate(ps) if RE_PARA.match(clean_text(p))),
        default=-1,
    )

    paragraphs = []
    footnotes = []
    promulgation = ''
    signature = ''

    # ─── Phase 1: body walk ──────────────────────────────────────────────
    state = HeadingState()
    pending_chapter_num = None

    for i in range(last_body_idx + 1):
        p = ps[i]
        text = clean_text(p)
        if not text or p is fm_p:
            continue

        has_b = bool(p.find('b'))

        # chapter marker: <p align="center">CHAPTER ONE</p> (no <b>)
        if is_centred(p) and not has_b:
            chapter_num = chapter_word_marker(text)
            if chapter_num is not None:
                pending_chapter_num = chapter_num
            continue

        # centred bold following a CHAPTER N marker: the chapter title
        if is_centred(p) and has_b:
            if pending_chapter_num is not None:
                state.set_chapter(pending_chapter_num, _chapter_title(text))
                pending_chapter_num = None
            continue

        # unnumbered bold topical header → auto-numbered section
        if only_child_is(p, 'b'):
            state.set_section(state.section + 1, heading_title(text))
            continue

        numbered = numbered_paragraph(p, RE_PARA)
        if numbered:
            paragraphs.append(paragraph_record(
                *numbered, bracketed_refs=True, **state.kwargs(),
            ))
            continue

        # unnumbered continuation prose following a numbered paragraph
        if paragraphs and not has_b:
            paragraphs[-1]['text'] += '\n\n' + normalise_footnote_refs(
                clean_text(p, preserve_formatting=True), bracketed=True
            )

    # ─── Phase 2: end matter (promulgation, signature, footnotes) ─────────
    for i in range(last_body_idx + 1, len(ps)):
        p = ps[i]
        text = clean_text(p)
        if not text:
            continue

        footnote = parse_footnote(
            clean_text(p, preserve_formatting=True),
            RE_FOOTNOTE, bracketed_refs=True,
        )
        if footnote:
            footnotes.append(footnote)
            continue

        if is_promulgation(text):
            promulgation = clean_text(p, preserve_formatting=True)
            continue

        # The papal signature ("FRANCISCUS") is the centred trailer after
        # the promulgation; capture the first one and ignore later ones.
        if is_centred(p) and promulgation and not signature:
            signature = clean_text(p, preserve_formatting=True)

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
        # The pope is already named in `desc` ("ENCYCLICAL LETTER OF THE
        # SUPREME PONTIFF FRANCIS"), so the title-page foot stays bare.
        'show_title_author': False,
        'desc': desc_pre,
        'desc_post': desc_post,
        'promulgation': promulgation,
        'signature': signature,
        'paragraphs': paragraphs,
        'footnotes': footnotes,
    }
