"""Extractor for *Deus Caritas Est* — Benedict XVI's 2005 encyclical on
Christian love, the first of his pontificate.

Modern Bootstrap dialect with the standard `_ftn` footnote anchors, but the
simplest structure met in that dialect so far: a single tier below the
document.

  - ``INTRODUCTION`` opens the part-0 group (kept as an authored title).
  - Two centred ``PART I`` / ``PART II`` markers each carry a centred-bold
    title. Part II spreads its lead word ``CARITAS`` onto its own centred
    line ahead of the descriptive title, so consecutive centred-bold title
    fragments are joined with a colon
    (``Caritas: The Practice of Love …``).
  - Within each part, italic-only topical headers ("A problem of language",
    "Charity as a responsibility of the Church") are the document's main
    divisions; they map to **bare chapters** (auto-numbered, the "Chapter N"
    prefix dropped via ``BARE_CHAPTER_DOCS``) so they surface as H2-level
    entries in the book tables of contents.
  - ``CONCLUSION`` is the trailing bare chapter.

Single pass over the body up to the first ``_ftn`` definition anchor, then
the footnote tail — the shape MH/VD/LF share. The closing Marian prayer
trails §42 as a source ``<blockquote>`` and folds onto it as italic verse,
the same handling as Lumen Fidei.
"""

import re

from core import (
    RE_FOOTNOTE,
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
    roman_to_int,
    title_case,
)
from project import SOURCES

from ._modern import (
    encyclical_front_matter,
    is_signature_trailer,
    load_main,
    strip_footnote_anchors,
)


EN_SRC = SOURCES / 'deus_caritas_est_en.html'

NAME = 'Deus Caritas Est'
HUE = 354
SOURCE_URL = ('https://www.vatican.va/content/benedict-xvi/en/encyclicals/'
              'documents/hf_ben-xvi_enc_20051225_deus-caritas-est.html')
AUTHOR = 'Benedict XVI'
DATE = '2005-12-25'
IDENTIFIER = 'papal:deus-caritas-est:2005-12-25'

TITLE_UPPER = 'DEUS CARITAS EST'

RE_PARA = re.compile(r'^(\d+)\s*\.\s+(.+)$', re.DOTALL)
RE_PART = re.compile(r'^PART\s+([IVX]+)$')

# Part II's title quotes "COMMUNITY OF LOVE"; `title_case` lower-cases the
# word straight after an opening quote (correct for mid-sentence quoted
# phrases elsewhere, wrong for this title noun), so re-capitalise it here.
_QUOTED_LC = re.compile(r'(["“‘\'])([a-z])')


def _restore_quoted_caps(title):
    return _QUOTED_LC.sub(lambda m: m.group(1) + m.group(2).upper(), title)


def _continuation_text(p):
    text = normalise_footnote_refs(
        clean_text(p, preserve_formatting=True), bracketed=True
    )
    if p.find_parent('blockquote'):
        # The closing Marian prayer trails §42 as a source <blockquote> (the
        # same shape as Lumen Fidei's). The TOML contract has no blockquote
        # role for paragraph continuations, so keep the source's visual
        # signal as canonical emphasis while preserving the verse breaks.
        return f'*{text}*'
    return text


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
    part_title_parts = []

    for p in ps[:first_note_idx]:
        text = clean_text(p)
        if not text or p is fm_p:
            continue

        if is_centred(p):
            if is_signature_trailer(p, promulgation, signature):
                signature = clean_text(p, preserve_formatting=True)
                continue

            part = RE_PART.match(text)
            if part:
                state.set_part(roman_to_int(part.group(1)))
                part_title_parts = []
                continue
            if text == 'INTRODUCTION':
                state.set_part(0, 'Introduction')
                part_title_parts = []
                continue
            if text.upper().startswith('CONCLUSION'):
                state.set_chapter(state.chapter + 1, 'Conclusion')
                continue
            # A centred-bold line inside a part is a title fragment; Part II
            # arrives as two (``CARITAS`` then the descriptive line), joined
            # with a colon into the canonical heading.
            if state.part:
                part_title_parts.append(title_case(text))
                state.part_title = _restore_quoted_caps(
                    ': '.join(part_title_parts)
                )
            continue

        # Italic-only topical header → bare chapter under the current part.
        # These are the document's H2-level divisions ("Charity as a
        # responsibility of the Church"); the source gives them no number, so
        # the slug joins make_html/make_book.BARE_CHAPTER_DOCS to drop the
        # "Chapter N" prefix. The promulgation dateline is a lone italic <p>
        # too, so let it fall through to its own branch.
        if only_child_is(p, 'i') and not is_promulgation(text):
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
            paragraphs[-1]['text'] += '\n\n' + _continuation_text(p)

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
        'subtitle': 'on Christian Love',
        # The pope is already named in `desc` ("ENCYCLICAL LETTER … OF THE
        # SUPREME PONTIFF BENEDICT XVI"), so the title-page foot stays bare.
        'show_title_author': False,
        'desc': desc_pre,
        'desc_post': desc_post,
        'promulgation': promulgation,
        'signature': signature,
        'layout': {'long': True, 'bare_chapters': True},
        'paragraphs': paragraphs,
        'footnotes': footnotes,
    }
