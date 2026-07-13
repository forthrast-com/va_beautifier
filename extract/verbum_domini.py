"""Extractor for *Verbum Domini* — Benedict XVI's 2010 post-synodal
apostolic exhortation on the Word of God.

Modern Bootstrap page with the deepest hierarchy met so far — three tiers
below the document:

  - **Part** — a centred ``PART ONE`` marker, then a centred all-caps part
    title (``VERBUM DEI``) and a centred scriptural epigraph.
  - **Chapter** — a centred mixed-case heading within a part
    (``The God Who Speaks``).
  - **Section** — an unnumbered bold topical header
    (``God in dialogue`` / ``The Church receives the word``),
    auto-numbered within its chapter.

``INTRODUCTION`` opens the part-0 group; ``CONCLUSION`` is an unnumbered
trailing chapter. The source brackets the body with a table of contents at
each end (both titled ``INDEX``); the walk starts at the centred
``INTRODUCTION`` and stops at the first footnote definition, so neither
index is seen. Footnote cites use the fragment ``#_ftn`` form; the anchors
are unwrapped to ``[N]`` for the canonical normalisation regardless.
"""

import re

from core import (
    RE_FOOTNOTE,
    HeadingState,
    assign_footnote_context,
    canonical_blockquote,
    chapter_word_to_int,
    clean_text,
    extract_footnotes,
    heading_title,
    is_centred,
    is_promulgation,
    make_soup,
    normalise_footnote_refs,
    numbered_paragraph,
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
RE_PART = re.compile(r'^PART\s+([A-Z]+)$')

_QUOTE_CHARS = '“"‘’”\''
RE_PART_EPIGRAPH = re.compile(
    r'^[“"](?P<body>.+)[”"]\n\((?P<citation>[^)]+)\)$',
    re.DOTALL,
)
RE_COUPLET_CLOSE = re.compile(
    r'^(?P<body>.+)”(?P<punct>[.!?])(?P<ref>\(\d+\))$',
    re.DOTALL,
)


def _canonicalise_part_epigraph(text):
    text = text.strip()
    if text.startswith('*') and text.endswith('*'):
        text = text[1:-1]
    match = RE_PART_EPIGRAPH.fullmatch(text)
    if not match:
        return text
    citation = re.sub(
        r'^((?:[1-3]\s+)?[A-Za-z]+)(\s+)', r'*\1*\2',
        match.group('citation'),
    )
    citation = re.sub(r'(?<=\d)-(?=\d)', '–', citation)
    return canonical_blockquote(match.group('body'), citation)


def _canonicalise_hermeneutic_couplet(paragraphs):
    """Lift §37's Latin couplet + translation into one quiet quotation."""
    paragraph = next((p for p in paragraphs if p['number'] == 37), None)
    if paragraph is None:
        return
    chunks = paragraph['text'].split('\n\n')
    quote_index = next(
        (i for i, chunk in enumerate(chunks[:-1])
         if chunk.startswith('“*Littera gesta docet')),
        None,
    )
    if quote_index is None:
        return
    opening = chunks[quote_index]
    closing = RE_COUPLET_CLOSE.fullmatch(chunks[quote_index + 1])
    if not closing:
        return
    quote = (
        opening.removeprefix('“') + '\n\n'
        + closing.group('body') + closing.group('punct') + closing.group('ref')
    )
    paragraph['text'] = '\n\n'.join(
        chunks[:quote_index]
        + [canonical_blockquote(quote)]
        + chunks[quote_index + 2:]
    )


def _is_all_bold(p):
    """True when every visible character of `p` sits inside a `<b>`.

    VD's topical headers are wrapped inconsistently (plain ``<b>`` in Part I,
    ``<i><b>…</b></i>`` in Part II), so a single-child shape test misses the
    latter and folds it into the previous paragraph as continuation prose.
    """
    bolds = p.find_all('b')
    return bool(bolds) and p.get_text(strip=True) == ''.join(
        b.get_text(strip=True) for b in bolds
    )


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
    return make_soup(f'<p>{fragment}</p>').p if fragment else None


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
    expect = None  # 'part_title' or 'part_subtitle' after a PART marker

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
                expect = 'part_subtitle'
                continue
            if expect == 'part_subtitle' and text[:1] in _QUOTE_CHARS:
                state.part_subtitle = _canonicalise_part_epigraph(
                    clean_text(p, preserve_formatting=True)
                )
                expect = None
                continue
            expect = None
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
        if _is_all_bold(p):
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

    _canonicalise_hermeneutic_couplet(paragraphs)

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
        'type': 'apostolic_exhortation',
        'subtitle': (
            'on the Word of God in the Life and Mission of the Church'
        ),
        # The pope is already named in `desc` ("POST-SYNODAL APOSTOLIC
        # EXHORTATION … OF THE HOLY FATHER BENEDICT XVI"), so the title-page
        # foot stays bare.
        'show_title_author': False,
        'desc': desc_pre,
        'desc_post': desc_post,
        'promulgation': promulgation,
        'signature': signature,
        'layout': {'long': True, 'bare_sections': True, 'capped_indicator': True},
        'paragraphs': paragraphs,
        'footnotes': footnotes,
    }
