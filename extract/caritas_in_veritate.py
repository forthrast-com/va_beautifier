"""Extractor for *Caritas in Veritate* — Benedict XVI's 2009 social
encyclical on integral human development.

Modern Bootstrap dialect with two wrinkles versus the Francis-era pages:

  - **Footnotes are a Word *endnote* export.** Body cites and tail
    definitions use ``_ednref{N}`` / ``_edn{N}`` anchors rather than
    ``_ftnref`` / ``_ftn``; ``_modern.RE_FOOTNOTE_ANCHOR`` matches both, so
    ``strip_footnote_anchors`` unwraps the ``[N]`` markers for the canonical
    ``[N]`` → ``(N)`` pass exactly as it does for the ``_ftn`` pages. The
    boundary probe therefore looks for ``name="_ednN"``.
  - **Chapter markers are bold.** Unlike LF (where ``CHAPTER ONE`` is a
    plain centred line), here the marker is itself centred-bold, so the
    ``has_b`` discriminator LF uses doesn't apply — the word marker is
    matched directly and the following centred-bold line is the title.

``INTRODUCTION`` opens the part-0 group; ``CONCLUSION`` is an unnumbered
trailing chapter. No bold topical sections. Single pass to the first
endnote definition, then the footnote tail.
"""

import re

from core import (
    RE_FOOTNOTE,
    HeadingState,
    assign_footnote_context,
    clean_text,
    extract_footnotes,
    is_centred,
    is_promulgation,
    normalise_footnote_refs,
    numbered_paragraph,
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


EN_SRC = SOURCES / 'caritas_in_veritate_en.html'

NAME = 'Caritas in Veritate'
HUE = 28
SOURCE_URL = ('https://www.vatican.va/content/benedict-xvi/en/encyclicals/'
              'documents/hf_ben-xvi_enc_20090629_caritas-in-veritate.html')
AUTHOR = 'Benedict XVI'
DATE = '2009-06-29'
IDENTIFIER = 'papal:caritas-in-veritate:2009-06-29'

TITLE_UPPER = 'CARITAS IN VERITATE'

RE_PARA = re.compile(r'^(\d+)\s*\.\s+(.+)$', re.DOTALL)

# Chapter 4's centred heading stacks a three-item list on <br/> lines with no
# punctuation ("THE DEVELOPMENT OF PEOPLE / RIGHTS AND DUTIES / THE
# ENVIRONMENT"); the space-join loses the list commas the encyclical's own
# index carries. A generic comma-join would wreck ordinary wrapped titles
# (chapter 6 breaks mid-phrase), so repair the one known title, keyed on the
# joined form so a source change surfaces as a miss.
CHAPTER_TITLE_REPAIRS = {
    'The Development of People Rights and Duties the Environment':
        'The Development of People, Rights and Duties, the Environment',
}


def extract():
    soup, main = load_main(EN_SRC, drop_chrome=True)
    ps = main.find_all('p')

    fm_p = next((p for p in ps if 'ENCYCLICAL LETTER' in p.get_text()), None)
    desc_pre, desc_post = encyclical_front_matter(fm_p, TITLE_UPPER)

    # Word endnote export: the tail definitions open with `name="_ednN"`
    # (the body cites carry `_ednrefN`). Locate the boundary before stripping
    # the anchors, which would erase the marker.
    first_note_idx = next(
        (i for i, p in enumerate(ps)
         if p.find('a', attrs={'name': re.compile(r'^_edn\d+$')})), None
    )
    if first_note_idx is None:
        raise ValueError(
            f'{EN_SRC.name}: no endnote definition (name="_ednN") found — '
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

        if is_centred(p):
            if is_signature_trailer(p, promulgation, signature):
                signature = clean_text(p, preserve_formatting=True)
                continue
            chapter_num = chapter_word_marker(text)
            if chapter_num is not None:
                pending_chapter_num = chapter_num
                continue
            if text == 'INTRODUCTION':
                state.set_part(0, 'Introduction')
                continue
            if text.upper().startswith('CONCLUSION'):
                state.part_title = ''
                state.set_chapter(state.chapter + 1, 'Conclusion')
                continue
            if pending_chapter_num is not None:
                # Leave the part-0 "Introduction" label behind once chapters
                # begin, so it doesn't bleed onto every chapter paragraph.
                state.part_title = ''
                title = title_case(text)
                state.set_chapter(
                    pending_chapter_num,
                    CHAPTER_TITLE_REPAIRS.get(title, title),
                )
                pending_chapter_num = None
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
        'subtitle': 'on Integral Human Development in Charity and in Truth',
        # The pope is already named in `desc` ("ENCYCLICAL LETTER … OF THE
        # SUPREME PONTIFF BENEDICT XVI"), so the title-page foot stays bare.
        'show_title_author': False,
        'desc': desc_pre,
        'desc_post': desc_post,
        'promulgation': promulgation,
        'signature': signature,
        'layout': {'long': True},
        'paragraphs': paragraphs,
        'footnotes': footnotes,
    }
