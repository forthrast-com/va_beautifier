"""Extractor for *Magnifica Humanitas* -- Leo XIV's 2026 AI encyclical.

The source uses the modern Vatican rich-text template, but unlike *Laudato
Si'* its primary section headings are unnumbered.  Synthetic section numbers
give the renderer stable IDs; the renderer suppresses their visible prefixes.
Bold-italic headings nested below primary headings become `sub_heading`.
"""

import re

from bs4 import BeautifulSoup

from core import (
    assign_footnote_context,
    br_lines,
    chapter_word_to_int,
    clean_text,
    extract_footnotes,
    paragraph_record,
    split_around_title,
    title_case,
)
from project import SOURCES


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
RE_FOOTNOTE = re.compile(r'^\[\s*(\d+)\s*\]\s*(.+)$', re.DOTALL)
RE_CHAPTER = re.compile(r'^CHAPTER\s+([A-Z]+)$')

def _heading_text(p):
    text = re.sub(r'\s+', ' ', p.get_text(separator=' ', strip=True)).strip()
    return text.replace('R esponsibility', 'Responsibility')


def _title(text):
    return title_case(text).replace(' Ai', ' AI')


def extract():
    with open(EN_SRC, encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')

    main = soup.find('main') or soup.body
    ps = main.find_all('p')
    first_body_idx = next(
        i for i, p in enumerate(ps) if RE_PARA.match(clean_text(p))
    )
    first_note_idx = next(
        i for i, p in enumerate(ps)
        if p.find('a', attrs={'name': re.compile(r'^_ftn\d+$')})
    )

    # Front matter: the abstract block holds the encyclical-letter preamble
    # with the title (MAGNIFICA HUMANITAS) split across its lines. Pull the
    # text apart so the renderer can sit the title between the two halves.
    abstract = soup.find('div', class_='abstract')
    desc_pre, desc_post = '', ''
    if abstract:
        pre, post = split_around_title(br_lines(abstract.find('p')), TITLE_UPPER)
        desc_pre = '\n'.join(pre)
        desc_post = '\n'.join(post)

    paragraphs = []
    promulgation = ''
    signature = ''

    chapter = 0
    chapter_title = ''
    chapter_subtitle = ''
    # The source has opening prose before its first primary heading. The
    # renderer supplies the top-level Introduction label for that scope;
    # do not manufacture a duplicate nested section here.
    section = 0
    section_title = ''
    sub_heading = ''
    pending_chapter_title = False

    for p in ps[first_body_idx:first_note_idx]:
        text = clean_text(p)
        if not text:
            continue

        m = RE_PARA.match(text)
        if m:
            pending_chapter_title = False
            rich_match = RE_PARA.match(clean_text(p, preserve_formatting=True))
            paragraphs.append(paragraph_record(
                int(m.group(1)), rich_match.group(2),
                chapter=chapter, chapter_title=chapter_title,
                chapter_subtitle=chapter_subtitle,
                section=section, section_title=section_title,
                sub_heading=sub_heading, bracketed_refs=True,
            ))
            continue

        heading = _heading_text(p)
        mc = RE_CHAPTER.match(heading)
        if mc and (chapter_num := chapter_word_to_int(mc.group(1))) is not None:
            chapter = chapter_num
            chapter_title = ''
            chapter_subtitle = ''
            section = 0
            section_title = ''
            sub_heading = ''
            pending_chapter_title = True
            continue

        if p.find('b'):
            if pending_chapter_title and heading.isupper():
                if not chapter_title:
                    chapter_title = _title(heading)
                else:
                    separator = ' ' if chapter_subtitle else ''
                    chapter_subtitle += separator + _title(heading)
                continue

            subordinate = (p.find('i') is not None
                           and chapter != 0
                           and section)
            if subordinate:
                sub_heading = heading
            else:
                section += 1
                section_title = heading
                sub_heading = ''
            continue

        if text.startswith('Given in ') or text.startswith('Given at '):
            promulgation = clean_text(p, preserve_formatting=True)
            continue

        # Papal signature: a short centred trailer after the dedication line,
        # e.g. "LEO PP. XIV". Match by position (post-promulgation) plus the
        # MS-Word centred-paragraph style so we don't catch stray prose.
        style = (p.get('style') or '').lower().replace(' ', '')
        if promulgation and 'text-align:center' in style and text:
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
        'date': DATE,
        'identifier': IDENTIFIER,
        'desc': desc_pre,
        'desc_post': desc_post,
        'promulgation': promulgation,
        'signature': signature,
        'paragraphs': paragraphs,
        'footnotes': footnotes,
    }
