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
    extract_footnotes,
    heading_title,
    is_centred,
    is_promulgation,
    normalise_footnote_refs,
    numbered_paragraph,
    only_child_is,
    paragraph_record,
    title_case,
)
from project import SOURCES

from ._modern import (
    chapter_word_marker,
    encyclical_front_matter,
    is_signature_trailer,
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
    ps = main.find_all('p')

    fm_p = next((p for p in ps if 'ENCYCLICAL LETTER' in p.get_text()), None)
    desc_pre, desc_post = encyclical_front_matter(fm_p, TITLE_UPPER)

    # The footnote definitions are a contiguous tail block, each opening with
    # an `<a name="_ftnN">` anchor (the body cites carry `_ftnrefN`). Single
    # pass over the body up to that boundary, then slice the notes off the
    # tail — the same shape MH and VD use. Locate the boundary *before*
    # unwrapping the anchors, which would erase the marker.
    first_note_idx = next(
        (i for i, p in enumerate(ps)
         if p.find('a', attrs={'name': re.compile(r'^_ftn\d+$')})), None
    )
    if first_note_idx is None:
        raise ValueError(
            f'{EN_SRC.name}: no footnote definition (name="_ftnN") found — '
            'cannot locate the end of the body text'
        )
    strip_footnote_anchors(soup)

    paragraphs = []
    promulgation = ''
    signature = ''

    state = HeadingState()
    pending_chapter_num = None

    for p in ps[:first_note_idx]:
        text = clean_text(p)
        if not text or p is fm_p:
            continue

        has_b = bool(p.find('b'))

        if is_centred(p):
            # Once the promulgation is seen, the only centred line left is the
            # papal signature ("FRANCISCUS"); take it before the chapter
            # branches below would treat it as a (title-less) chapter line.
            if is_signature_trailer(p, promulgation, signature):
                signature = clean_text(p, preserve_formatting=True)
                continue
            # chapter marker: <p align="center">CHAPTER ONE</p> (no <b>),
            # then its centred-bold scriptural title
            if not has_b:
                chapter_num = chapter_word_marker(text)
                if chapter_num is not None:
                    pending_chapter_num = chapter_num
                continue
            if pending_chapter_num is not None:
                state.set_chapter(pending_chapter_num, _chapter_title(text))
                pending_chapter_num = None
            continue

        # unnumbered bold topical header → auto-numbered section
        if only_child_is(p, 'b'):
            state.add_section(heading_title(text))
            continue

        numbered = numbered_paragraph(p, RE_PARA)
        if numbered:
            paragraphs.append(paragraph_record(
                *numbered, bracketed_refs=True, **state.kwargs(),
            ))
            continue

        # The promulgation dateline trails the last numbered paragraph; catch
        # it before the continuation fallback would fold it into §60.
        if is_promulgation(text):
            promulgation = clean_text(p, preserve_formatting=True)
            continue

        # unnumbered continuation prose following a numbered paragraph
        if paragraphs and not has_b:
            paragraphs[-1]['text'] += '\n\n' + normalise_footnote_refs(
                clean_text(p, preserve_formatting=True), bracketed=True
            )

    footnotes = extract_footnotes(
        ps[first_note_idx:], RE_FOOTNOTE, bracketed_refs=True
    )
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
