"""Extractor for the ITC document *Quo vadis, humanitas?*."""

import re

from core import paragraph_record, roman_to_int
from curia import anchored_footnotes, heading_title, load_source, prose_text, text
from project import SOURCES


EN_SRC = SOURCES / 'quo_vadis_humanitas_en.html'

NAME = 'Quo vadis, humanitas?'
HUE = 18
SOURCE_URL = (
    'https://www.vatican.va/roman_curia/congregations/cfaith/cti_documents/'
    'rc_cti_doc_20260304_quo-vadis-humanits_en.html'
)
# Sub-commission membership lifted from the preliminary note: a chair
# and eight named members. The full roster sits at the foot of the title
# page so the document's human voices appear under the institutional
# header up top.
AUTHOR = (
    'Rev. Javier Prades López, chair · '
    'Rev. Alberto Cozzi · '
    'Rev. Simon Francis Gaine, O.P. · '
    'Rev. Carlos Maria Galli · '
    'Prof. Reinhard Huetter · '
    'Rev. Victor Ronald La Barrera Villarreal · '
    'Prof. Isabell Naumann, I.S.S.M. · '
    'Rev. Josée Ngalula, R.S.A. · '
    'Rev. Bernard Pottier, S.J.'
)
DATE = '2026-03-04'
IDENTIFIER = 'cti:quo-vadis-humanitas:2026-03-04'

RE_PARA = re.compile(r'^(\d+)\.\s+(.+)$', re.DOTALL)
RE_CHAPTER = re.compile(r'^Chapter\s+([IVX]+)$', re.IGNORECASE)
RE_SECTION = re.compile(r'^(\d+)\.\s+(.+)$', re.DOTALL)


def structural_text(tag):
    """Plain text for heading detection; structural labels are not links."""
    return re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text(tag))


def extract():
    soup = load_source(EN_SRC)
    ps = soup.find_all('p')
    start = next(
        (i for i, p in enumerate(ps)
         if p.find('a', attrs={'name': 'Preliminary_note'})), None
    )
    if start is None:
        raise ValueError(
            f'{EN_SRC.name}: no <a name="Preliminary_note"> anchor found — '
            'source structure has changed or the snapshot is not this dialect'
        )
    end = next(
        (i for i, p in enumerate(ps[start:], start)
         if p.find('a', attrs={'name': re.compile(r'^_ftn\d+$')})), None
    )
    if end is None:
        raise ValueError(
            f'{EN_SRC.name}: no footnote anchor (name="_ftnN") found — '
            'cannot locate the end of the body text'
        )

    paragraphs = []
    part_title = ''
    chapter = 0
    chapter_title = ''
    chapter_subtitle = ''
    section = 0
    section_title = ''
    pending_chapter = False
    hidden_number = -1

    for p in ps[start:end]:
        plain = structural_text(p)
        if not plain:
            continue
        centred = (p.get('align') or '').lower() == 'center'

        if centred and plain == 'Preliminary note':
            part_title = 'Preliminary Note'
            continue
        if centred and plain == 'Introduction':
            part_title = 'Introduction'
            chapter = 0
            section = 0
            section_title = ''
            continue

        marker = RE_CHAPTER.match(plain)
        if centred and marker:
            chapter = roman_to_int(marker.group(1))
            chapter_title = ''
            chapter_subtitle = ''
            section = 0
            section_title = ''
            pending_chapter = True
            continue
        if centred and plain == 'Conclusion':
            chapter = 5
            chapter_title = 'Conclusion'
            chapter_subtitle = ''
            section = 0
            section_title = ''
            pending_chapter = True
            continue
        if centred and pending_chapter:
            if chapter_title == 'Conclusion':
                chapter_subtitle = heading_title(plain)
            else:
                chapter_title = heading_title(plain)
            pending_chapter = False
            continue

        section_match = RE_SECTION.match(plain)
        if p.find('b') and section_match:
            section = int(section_match.group(1))
            section_title = f'{section}. {heading_title(section_match.group(2))}'
            continue

        para = RE_PARA.match(plain)
        if para and not p.find('b'):
            rich = RE_PARA.match(prose_text(p))
            paragraphs.append(paragraph_record(
                int(para.group(1)), rich.group(2),
                part_title=part_title,
                chapter=chapter, chapter_title=chapter_title,
                chapter_subtitle=chapter_subtitle,
                section=section, section_title=section_title,
                bracketed_refs=True,
            ))
            continue

        if part_title == 'Preliminary Note':
            paragraph = paragraph_record(
                hidden_number, prose_text(p), part_title=part_title
            )
            paragraph['hide_number'] = True
            paragraphs.append(paragraph)
            hidden_number -= 1
            continue

        if paragraphs:
            paragraphs[-1]['text'] += '\n\n' + prose_text(p)

    footnotes = anchored_footnotes(soup, paragraphs)
    return {
        'name': NAME,
        'hue': HUE,
        'source_url': SOURCE_URL,
        'author': AUTHOR,
        'issued_by': 'International Theological Commission',
        'pontificate': 'Leo XIV',
        'date': DATE,
        'identifier': IDENTIFIER,
        'desc': 'International Theological Commission',
        'desc_post': 'Thinking through Christian Anthropology in the Face of '
                     'Certain Scenarios for the Future of Humanity',
        'paragraphs': paragraphs,
        'footnotes': footnotes,
    }
