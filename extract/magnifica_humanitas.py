"""Extractor for *Magnifica Humanitas* -- Leo XIV's 2026 AI encyclical.

The source uses the modern Vatican rich-text template, but unlike *Laudato
Si'* its primary section headings are unnumbered.  Synthetic section numbers
give the renderer stable IDs; the renderer suppresses their visible prefixes.
Bold-italic headings nested below primary headings become `sub_heading`.
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
    numbered_paragraph,
    paragraph_record,
)
from project import SOURCES

from ._modern import chapter_word_marker, encyclical_front_matter, load_main


EN_SRC = SOURCES / 'magnifica_humanitas_en.html'

NAME = 'Magnifica Humanitas'
HUE = 230
SOURCE_URL = ('https://www.vatican.va/content/leo-xiv/en/encyclicals/documents/'
              '20260515-magnifica-humanitas.html')
AUTHOR = 'Leo XIV'
DATE = '2026-05-15'
IDENTIFIER = 'papal:magnifica-humanitas:2026-05-15'

# Front-matter signal: the abstract block sits in a div whose class list
# includes "abstract"; its first <p> carries the encyclical-letter preamble
# with the title sandwiched in the middle (separated by <br/> tags).
TITLE_UPPER = 'MAGNIFICA HUMANITAS'

RE_PARA = re.compile(r'^(\d+)\.\s+(.+)$', re.DOTALL)

def _heading_text(p):
    text = flatten_ws(p.get_text(separator=' ', strip=True))
    return text.replace('R esponsibility', 'Responsibility')


def extract():
    soup, main = load_main(EN_SRC)
    ps = main.find_all('p')
    first_body_idx = next(
        (i for i, p in enumerate(ps) if RE_PARA.match(clean_text(p))), None
    )
    if first_body_idx is None:
        raise ValueError(
            f'{EN_SRC.name}: no numbered body paragraph ("N. …") found — '
            'source structure has changed or the snapshot is not this dialect'
        )
    first_note_idx = next(
        (i for i, p in enumerate(ps)
         if p.find('a', attrs={'name': re.compile(r'^_ftn\d+$')})), None
    )
    if first_note_idx is None:
        raise ValueError(
            f'{EN_SRC.name}: no footnote anchor (name="_ftnN") found — '
            'cannot locate the end of the body text'
        )

    # Front matter: the abstract block holds the encyclical-letter preamble
    # with the title (MAGNIFICA HUMANITAS) split across its lines. Pull the
    # text apart so the renderer can sit the title between the two halves,
    # pivoted at the "On …" line so the issuer sits above the title and
    # the subject below it.
    abstract = soup.find('div', class_='abstract')
    desc_pre, desc_post = encyclical_front_matter(
        abstract.find('p') if abstract else None, TITLE_UPPER
    )

    paragraphs = []
    promulgation = ''
    signature = ''

    # The source has opening prose before its first primary heading. The
    # renderer supplies the top-level Introduction label for that scope;
    # do not manufacture a duplicate nested section here.
    state = HeadingState()
    pending_chapter_title = False

    for p in ps[first_body_idx:first_note_idx]:
        text = clean_text(p)
        if not text:
            continue

        numbered = numbered_paragraph(p, RE_PARA)
        if numbered:
            pending_chapter_title = False
            paragraphs.append(paragraph_record(
                *numbered, bracketed_refs=True, **state.kwargs(),
            ))
            continue

        heading = _heading_text(p)
        chapter_num = chapter_word_marker(heading)
        if chapter_num is not None:
            state.set_chapter(chapter_num)
            pending_chapter_title = True
            continue

        if p.find('b'):
            # `pending_chapter_title` stays raised until the first numbered
            # body paragraph: the source may split a chapter's subtitle
            # across several consecutive bold-caps <p>s, and every fragment
            # accumulates here.
            if pending_chapter_title and heading.isupper():
                if not state.chapter_title:
                    state.chapter_title = heading_title(heading)
                else:
                    separator = ' ' if state.chapter_subtitle else ''
                    state.chapter_subtitle += separator + heading_title(heading)
                continue

            subordinate = (p.find('i') is not None
                           and state.chapter != 0
                           and state.section)
            if subordinate:
                state.sub_heading = heading
            else:
                # Primary headings are mixed case except the closing
                # CONCLUSION; heading_title normalises all-caps ones the
                # way chapter titles are and passes the rest through.
                state.add_section(heading_title(heading))
            continue

        if is_promulgation(text):
            promulgation = clean_text(p, preserve_formatting=True)
            continue

        # Papal signature: a short centred trailer after the dedication line,
        # e.g. "LEO PP. XIV". Match by position (post-promulgation) plus the
        # centred-paragraph shape so we don't catch stray prose.
        if promulgation and is_centred(p) and text:
            signature = clean_text(p, preserve_formatting=True)

    footnotes = extract_footnotes(
        ps[first_note_idx:], RE_FOOTNOTE, bracketed_refs=True
    )
    footnotes = assign_footnote_context(footnotes, paragraphs)

    return {
        'name': NAME,
        'hue': HUE,
        'source_url': SOURCE_URL,
        'author': AUTHOR,
        'issued_by': 'Leo XIV',
        'pontificate': 'Leo XIV',
        'date': DATE,
        'identifier': IDENTIFIER,
        'type': 'encyclical',
        'subtitle': (
            'on Safeguarding the Human Person '
            'in the Time of Artificial Intelligence'
        ),
        # The pope is already named in `desc` ("ENCYCLICAL LETTER OF
        # HIS HOLINESS POPE LEO XIV"), so the title-page foot stays bare.
        'show_title_author': False,
        'desc': desc_pre,
        'desc_post': desc_post,
        'promulgation': promulgation,
        'signature': signature,
        'layout': {'long': True, 'bare_sections': True, 'mobile_inline': True, 'section_indicator': True},
        'paragraphs': paragraphs,
        'footnotes': footnotes,
    }
