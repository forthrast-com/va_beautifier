"""Extractor for *Verbum Domini* — Benedict XVI's 2010 post-synodal
apostolic exhortation on the Word of God.

Modern Bootstrap page with the deepest hierarchy met so far — three tiers
below the document:

  - **Part** — a centred ``PART ONE`` marker, then a centred all-caps part
    title (``VERBUM DEI``) and a centred scriptural epigraph (dropped).
  - **Chapter** — a centred mixed-case heading within a part
    (``The God Who Speaks``).
  - **Section** — an unnumbered bold topical header (``God in dialogue``),
    auto-numbered within its chapter.

``INTRODUCTION`` opens the part-0 group; ``CONCLUSION`` is an unnumbered
trailing chapter. The source brackets the body with a table of contents at
each end (both titled ``INDEX``); the walk starts at the centred
``INTRODUCTION`` and stops at the first footnote definition, so neither
index is seen. Footnote cites use the fragment ``#_ftn`` form; the anchors
are unwrapped to ``[N]`` for the canonical normalisation regardless.
"""

import re

from bs4 import BeautifulSoup

from core import (
    HeadingState,
    assign_footnote_context,
    chapter_word_to_int,
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

from ._modern import encyclical_front_matter, load_main, strip_footnote_anchors


EN_SRC = SOURCES / 'verbum_domini_en.html'

NAME = 'Verbum Domini'
HUE = 200
SOURCE_URL = ('https://www.vatican.va/content/benedict-xvi/en/apost_exhortations/'
              'documents/hf_ben-xvi_exh_20100930_verbum-domini.html')
AUTHOR = 'Benedict XVI'
DATE = '2010-09-30'
IDENTIFIER = 'papal:verbum-domini:2010-09-30'

TITLE_UPPER = 'VERBUM DOMINI'

RE_PARA = re.compile(r'^(\d+)\s*\.\s+(.+)$', re.DOTALL)
RE_FOOTNOTE = re.compile(r'^\[\s*(\d+)\s*\]\s*(.+)$', re.DOTALL)
RE_PART = re.compile(r'^PART\s+([A-Z]+)$')

_QUOTE_CHARS = '“"‘’”\''


def _trailing_prose(tag):
    """Inline text that trails `tag` outside any block element, as a <p>.

    Verbum Domini's §1 is loose content between the ``INTRODUCTION`` heading
    and the next ``<p>`` (a Word-export artefact), so ``find_all('p')`` skips
    it. Gather the heading's inline next-siblings up to the following block.
    """
    parts = []
    for sibling in tag.next_siblings:
        if getattr(sibling, 'name', None) in ('p', 'div', 'table'):
            break
        parts.append(str(sibling))
    fragment = ''.join(parts).strip()
    return BeautifulSoup(f'<p>{fragment}</p>', 'html.parser').p if fragment else None


def extract():
    soup, main = load_main(EN_SRC, drop_chrome=True)
    ps = main.find_all('p')

    desc_pre, desc_post = encyclical_front_matter(ps[0] if ps else None,
                                                  TITLE_UPPER)

    body_start = next(
        (i for i, p in enumerate(ps)
         if is_centred(p) and clean_text(p) == 'INTRODUCTION'), None
    )
    if body_start is None:
        raise ValueError(
            f'{EN_SRC.name}: no centred "INTRODUCTION" heading found — '
            'source structure has changed or the snapshot is not this dialect'
        )
    first_note_idx = next(
        (i for i, p in enumerate(ps)
         if p.find('a', attrs={'name': re.compile(r'^_ftn\d+$')})), None
    )
    if first_note_idx is None:
        raise ValueError(
            f'{EN_SRC.name}: no footnote definition (name="_ftnN") found — '
            'cannot locate the end of the body text'
        )

    # The note anchors have now served their purpose as the body/notes
    # boundary marker, so unwrap them to bare `[N]` for normalisation.
    strip_footnote_anchors(soup)

    paragraphs = []
    promulgation = ''
    signature = ''

    state = HeadingState()
    expect = None  # 'part_title' or 'epigraph' after a PART marker

    for p in ps[body_start:first_note_idx]:
        text = clean_text(p)
        if not text:
            continue

        if is_centred(p):
            # Past the promulgation, the only centred line left is the papal
            # signature; capture it and stop before the trailing index.
            if promulgation:
                if not signature:
                    signature = clean_text(p, preserve_formatting=True)
                break

            part = RE_PART.match(text)
            if part:
                state.set_part(chapter_word_to_int(part.group(1)) or 0)
                expect = 'part_title'
                continue
            if expect == 'part_title' and text == text.upper():
                state.part_title = title_case(text)
                expect = 'epigraph'
                continue
            drop_epigraph = expect == 'epigraph' and text[:1] in _QUOTE_CHARS
            expect = None
            if drop_epigraph:
                continue
            if text == 'INTRODUCTION':
                # Keep the source's "Introduction" heading as an authored
                # part-0 title (a real heading on every surface), not the
                # generated Preamble used for untitled openings.
                state.set_part(0)
                state.part_title = 'Introduction'
                # §1 trails the heading as loose inline text, not a <p>.
                loose = _trailing_prose(p)
                numbered = loose and numbered_paragraph(loose, RE_PARA)
                if numbered:
                    paragraphs.append(paragraph_record(
                        *numbered, bracketed_refs=True, **state.kwargs(),
                    ))
                continue
            if text.upper().startswith('CONCLUSION'):
                state.set_chapter(state.chapter + 1, 'Conclusion')
                continue
            # any other centred line within a part is a chapter heading
            state.set_chapter(state.chapter + 1, title_case(text))
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
        # The pope is already named in `desc` ("POST-SYNODAL APOSTOLIC
        # EXHORTATION … OF THE HOLY FATHER BENEDICT XVI"), so the title-page
        # foot stays bare.
        'show_title_author': False,
        'desc': desc_pre,
        'desc_post': desc_post,
        'promulgation': promulgation,
        'signature': signature,
        'paragraphs': paragraphs,
        'footnotes': footnotes,
    }
