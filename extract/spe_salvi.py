"""Extractor for *Spe Salvi* — Benedict XVI's 2007 encyclical on Christian
hope.

Modern Bootstrap dialect, standard `_ftn` footnote anchors. The document
carries no ``CHAPTER N`` markers, so the bold topical headers *are* its
primary divisions:

  - ``Introduction`` (an all-bold ``<p>``) opens the part-0 group.
  - Unnumbered all-bold topical headers (``Faith is Hope``, ``Mary, Star of
    Hope`` …) become auto-numbered **chapters** — the navigation backbone —
    rendered as bare titles (the slug joins ``make_html.BARE_CHAPTER_DOCS``,
    so no ``Chapter N`` prefix). The source wraps these as either
    ``<b><i>…</i></b>`` or ``<i><b>…</i></b>`` inconsistently, so an
    *all-bold* test recognises them rather than a single-child shape test.
  - The chapter ``"Settings" for learning and practising hope`` carries three
    centred-bold Roman subsections (``I. Prayer …``); these become its
    **sections**, kept verbatim (numeral and all), rendered bare via
    ``make_html.BARE_SECTION_DOCS``.

Single pass over the body to the first ``_ftn`` definition anchor, then the
footnote tail.
"""

import re

from core import (
    RE_FOOTNOTE,
    HeadingState,
    assign_footnote_context,
    clean_text,
    extract_footnotes,
    flatten_ws,
    heading_title,
    is_centred,
    is_promulgation,
    normalise_footnote_refs,
    numbered_paragraph,
    paragraph_record,
)
from project import SOURCES

from ._modern import (
    encyclical_front_matter,
    is_signature_trailer,
    load_main,
    strip_footnote_anchors,
)


EN_SRC = SOURCES / 'spe_salvi_en.html'

NAME = 'Spe Salvi'
HUE = 150
SOURCE_URL = ('https://www.vatican.va/content/benedict-xvi/en/encyclicals/'
              'documents/hf_ben-xvi_enc_20071130_spe-salvi.html')
AUTHOR = 'Benedict XVI'
DATE = '2007-11-30'
IDENTIFIER = 'papal:spe-salvi:2007-11-30'

TITLE_UPPER = 'SPE SALVI'

RE_PARA = re.compile(r'^(\d+)\s*\.\s+(.+)$', re.DOTALL)
# Centred-bold Roman subsection within the "Settings" section.
RE_SUBSEC = re.compile(r'^[IVX]+\.\s+\S')


def _is_all_bold(p):
    """True when every visible character of `p` sits inside a `<b>`.

    The topical headers are bold throughout (``<b><i>…</i></b>`` or the
    transposed nesting); body paragraphs only carry inline ``<i>`` emphasis,
    so an all-bold test cleanly separates the two.
    """
    bolds = p.find_all('b')
    return bool(bolds) and p.get_text(strip=True) == ''.join(
        b.get_text(strip=True) for b in bolds
    )


def extract():
    soup, main = load_main(EN_SRC, drop_chrome=True)
    ps = main.find_all('p')

    fm_p = next((p for p in ps if 'ENCYCLICAL LETTER' in p.get_text()), None)
    desc_pre, desc_post = encyclical_front_matter(fm_p, TITLE_UPPER)

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

    for p in ps[:first_note_idx]:
        text = clean_text(p)
        if not text or p is fm_p:
            continue

        if is_centred(p):
            if is_signature_trailer(p, promulgation, signature):
                signature = clean_text(p, preserve_formatting=True)
                continue
            # Centred-bold Roman subsection under the current chapter; the
            # source keeps the numeral in the heading, so retain it verbatim.
            if RE_SUBSEC.match(text):
                state.add_section(flatten_ws(text))
            continue

        if _is_all_bold(p):
            if text == 'Introduction':
                state.set_part(0, 'Introduction')
            else:
                # The bold topical headers are the document's primary
                # divisions (it has no "CHAPTER N" markers), so they drive
                # the chapter tier — the navigation backbone — rather than
                # rendering as subordinate sections. The slug joins
                # make_html.BARE_CHAPTER_DOCS so the auto-numbered chapters
                # show their bare title without a "Chapter N" prefix.
                state.set_chapter(state.chapter + 1, heading_title(text))
            continue

        numbered = numbered_paragraph(p, RE_PARA)
        if numbered:
            paragraphs.append(paragraph_record(
                *numbered, bracketed_refs=True, **state.kwargs(),
            ))
            continue

        if is_promulgation(text):
            promulgation = clean_text(p, preserve_formatting=True)
            continue

        # unnumbered continuation prose following a numbered paragraph
        if paragraphs:
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
        'issued_by': 'Benedict XVI',
        'pontificate': 'Benedict XVI',
        'date': DATE,
        'identifier': IDENTIFIER,
        'type': 'encyclical',
        'subtitle': 'on Christian Hope',
        # The pope is already named in `desc` ("ENCYCLICAL LETTER … OF THE
        # SUPREME PONTIFF BENEDICT XVI"), so the title-page foot stays bare.
        'show_title_author': False,
        'desc': desc_pre,
        'desc_post': desc_post,
        'promulgation': promulgation,
        'signature': signature,
        'paragraphs': paragraphs,
        'footnotes': footnotes,
    }
