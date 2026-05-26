"""Extractor for *Antiqua et nova*, a Curia Word-export document."""

import re

from core import paragraph_record, roman_to_int
from curia import anchored_footnotes, heading_title, load_source, prose_text, text
from project import SOURCES


EN_SRC = SOURCES / 'antiqua_et_nova_en.html'

NAME = 'Antiqua et Nova'
HUE = 285
SOURCE_URL = (
    'https://www.vatican.va/roman_curia/congregations/cfaith/documents/'
    'rc_ddf_doc_20250128_antiqua-et-nova_en.html'
)

RE_PARA = re.compile(r'^(\d+)\.\s+(.+)$', re.DOTALL)
RE_MAJOR = re.compile(r'^([IVX]+)\.\s+(.+)$', re.DOTALL)


def extract():
    soup = load_source(EN_SRC)
    ps = soup.find_all('p')
    start = next(i for i, p in enumerate(ps) if text(p) == 'I. Introduction')
    end = next(i for i, p in enumerate(ps[start:], start) if text(p) == 'Contents')

    paragraphs = []
    chapter = 0
    chapter_title = ''
    sub_heading = ''
    promulgation = []
    signature = ''

    for p in ps[start:end]:
        plain = text(p)
        if not plain:
            continue

        major = RE_MAJOR.match(plain)
        if p.find('b') and major:
            chapter = roman_to_int(major.group(1))
            chapter_title = heading_title(major.group(2))
            sub_heading = ''
            continue

        para = RE_PARA.match(plain)
        if para:
            rich = RE_PARA.match(prose_text(p))
            paragraphs.append(paragraph_record(
                int(para.group(1)), rich.group(2),
                chapter=chapter, chapter_title=chapter_title,
                sub_heading=sub_heading, bracketed_refs=True,
            ))
            continue

        if plain.startswith('The Supreme Pontiff'):
            promulgation.append(plain)
            continue
        if plain.startswith('Given in Rome'):
            promulgation.append(plain)
            continue
        if plain.startswith('Ex audientia'):
            signature = plain
            continue

        # Internal topic headings in this source are italic-only paragraphs.
        sub_heading = plain

    footnotes = anchored_footnotes(soup, paragraphs)
    return {
        'name': NAME,
        'hue': HUE,
        'source_url': SOURCE_URL,
        'desc': 'Dicastery for the Doctrine of the Faith\n'
                'Dicastery for Culture and Education',
        'desc_post': 'Note on the Relationship Between Artificial Intelligence '
                     'and Human Intelligence',
        'promulgation': '\n\n'.join(promulgation),
        'signature': signature,
        'paragraphs': paragraphs,
        'footnotes': footnotes,
    }
