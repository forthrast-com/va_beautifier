"""Extractor for *Antiqua et nova*, a Curia Word-export document."""

import re

from core import clean_text, paragraph_record, roman_to_int
from curia import anchored_footnotes, heading_title, load_source, prose_text, text
from project import SOURCES


EN_SRC = SOURCES / 'antiqua_et_nova_en.html'

NAME = 'Antiqua et Nova'
HUE = 285
SOURCE_URL = (
    'https://www.vatican.va/roman_curia/congregations/cfaith/documents/'
    'rc_ddf_doc_20250128_antiqua-et-nova_en.html'
)
DATE = '2025-01-28'
IDENTIFIER = 'ddf-dce:antiqua-et-nova:2025-01-28'

RE_PARA = re.compile(r'^(\d+)\.\s+(.+)$', re.DOTALL)
RE_MAJOR = re.compile(r'^([IVX]+)\.\s+(.+)$', re.DOTALL)


_ROLE_HINT = re.compile(r'\b(Prefect|Secretary|President)\b', re.IGNORECASE)


def _extract_signatories(soup):
    """The 2×2 signatory table sits between the second promulgation
    stanza and the Latin signature, wrapped in a couple of outer layout
    tables that this source uses for centring. Pick the innermost <table>
    (no nested <table> inside) and filter cells by a Curia role hint so
    the language-switch bar at the top of the page doesn't sneak in."""
    candidates = [t for t in soup.find_all('table') if not t.find('table')]
    for table in candidates:
        signatories = []
        for cell in table.find_all('td'):
            raw = clean_text(cell, preserve_formatting=False)
            lines = [line.strip() for line in raw.splitlines() if line.strip()]
            if not lines or not any(_ROLE_HINT.search(line) for line in lines[1:]):
                continue
            signatories.append({
                'name': lines[0],
                'role': ' '.join(lines[1:]),
            })
        if signatories:
            return signatories
    return []


def extract():
    soup = load_source(EN_SRC)
    ps = soup.find_all('p')
    start = next(i for i, p in enumerate(ps) if text(p) == 'I. Introduction')
    end = next(i for i, p in enumerate(ps[start:], start) if text(p) == 'Contents')

    paragraphs = []
    chapter = 0
    chapter_title = ''
    sub_heading = ''
    promulgation_stanzas = []
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

        if plain.startswith('The Supreme Pontiff') or plain.startswith('Given in Rome'):
            # Preserve the source's italic / roman cadence — the first stanza
            # is fully italic with "Note" set in roman, the second is plain.
            promulgation_stanzas.append(prose_text(p))
            continue
        if plain.startswith('Ex audientia'):
            # The source breaks "Ex audientia die 14 ianuarii 2025" and
            # "Franciscus" onto separate lines via <br>; keep the line break
            # so the rendered signature stacks the date over the name.
            # Collapse `\n\n` runs introduced by leading whitespace around
            # the break — we only want a single line break between the two.
            raw = clean_text(p, preserve_formatting=True)
            signature = re.sub(r'\n+', '\n', raw)
            continue

        # Internal topic headings in this source are italic-only paragraphs.
        sub_heading = plain

    signatories = _extract_signatories(soup)

    footnotes = anchored_footnotes(soup, paragraphs)
    return {
        'name': NAME,
        'hue': HUE,
        'source_url': SOURCE_URL,
        # The Prefects from the signatories table are the document's
        # primary signers; render them as dc:creator rather than the
        # institutional dicasteries that appear above the title.
        'author': ' and '.join(
            s['name'] for s in signatories
            if s.get('role', '').lower() == 'prefect'
        ),
        'date': DATE,
        'identifier': IDENTIFIER,
        'desc': 'Dicastery for the Doctrine of the Faith\n'
                'Dicastery for Culture and Education',
        'desc_post': 'Note on the Relationship Between Artificial Intelligence '
                     'and Human Intelligence',
        'promulgation': '\n\n'.join(promulgation_stanzas),
        'signature': signature,
        'signatories': signatories,
        'paragraphs': paragraphs,
        'footnotes': footnotes,
    }
