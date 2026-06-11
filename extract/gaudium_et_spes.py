"""Extractor for *Gaudium et Spes* — the old flat Vatican.va template.

Quirks:
  - Sources served as ISO-8859-1 (EN) and latin-1 (LA), not UTF-8.
  - Structure carried by <b> headings and <center> blocks, not classes.
  - Inline footnote refs use `(N)` (already canonical).
  - Latin source provides a per-paragraph micro-summary (`heading_la`),
    keyed by paragraph number — this is a GeS-specific affordance.
"""

import re
from bs4 import BeautifulSoup, NavigableString, Tag

from core import (
    HeadingState,
    assign_footnote_context,
    clean_text,
    normalise_footnote_refs,
    numbered_paragraph,
    paragraph_record,
    parse_num,
    parse_footnote,
    roman_to_int,
    title_case,
)
from project import SOURCES

from ._oldflat import front_matter_text, load_split


EN_SRC = SOURCES / 'gaudium_et_spes_en.html'
LT_SRC = SOURCES / 'gaudium_et_spes_lt.html'

NAME = 'Gaudium et Spes'
HUE = 42
SOURCE_URL = ('https://www.vatican.va/archive/hist_councils/ii_vatican_council/'
              'documents/vat-ii_const_19651207_gaudium-et-spes_en.html')
AUTHOR = 'Second Vatican Council'
DATE = '1965-12-07'
IDENTIFIER = 'council:gaudium-et-spes:1965-12-07'


RE_PART     = re.compile(r'^PART\s+([IVX]+)\s*$')
RE_CHAPTER  = re.compile(r'^CHAPTER\s+([IVX]+)\s*$')
RE_SECTION  = re.compile(r'^SECTION\s+(\d+|[IVX]+)\s*(.*)$', re.DOTALL)
RE_PARA_NUM = re.compile(r'^\s*(\d+)\.\s+(.+)', re.DOTALL)
CHAPTER_TITLES = {
    'THE DIGNITY OF THE HUMAN PERSON',
    'THE COMMUNITY OF MANKIND',
    "MAN'S ACTIVITY THROUGHOUT THE WORLD",
    'THE ROLE OF THE CHURCH IN THE MODERN WORLD',
    'FOSTERING THE NOBILITY OF MARRIAGE AND THE FAMILY',
    'THE PROPER DEVELOPMENT OF CULTURE',
    'ECONOMIC AND SOCIAL LIFE',
    'THE LIFE OF THE POLITICAL COMMUNITY',
    'THE FOSTERING OF PEACE AND THE PROMOTION OF A COMMUNITY OF NATIONS',
}

PART_TITLES = {
    "THE CHURCH AND MAN'S CALLING",
    'SOME PROBLEMS OF SPECIAL URGENCY',
}


def _extract_frontmatter(body_html):
    """Split the GeS front-matter <p> around its 'GAUDIUM ET SPES' title.
    Lines before the title become `desc`; lines after carry the document's
    promulgation. Its source placement is front-matter decoration, but its
    semantic place in an edition is end matter."""
    text = front_matter_text(body_html, 'PASTORAL CONSTITUTION')
    if not text:
        return '', ''
    desc_m = re.match(r'(.+?)\s*GAUDIUM ET SPES', text, re.DOTALL)
    post_m = re.search(r'GAUDIUM ET SPES\s*\n(.+)', text, re.DOTALL)
    desc = desc_m.group(1).strip() if desc_m else ''
    post = post_m.group(1).strip() if post_m else ''
    return desc, post


def _walk_body(body_soup):
    state = HeadingState()
    paragraphs = []
    current = None

    def process_bold_heading(text):
        text = re.sub(r'\s+', ' ', text).strip()

        if text == 'PREFACE':
            state.set_part(0, 'Preface')
            return True
        if text == 'INTRODUCTORY STATEMENT THE SITUATION OF MEN IN THE MODERN WORLD':
            state.set_part(0, title_case(text))
            return True

        m = RE_PART.match(text)
        if m:
            state.set_part(roman_to_int(m.group(1)))
            return True
        if text in PART_TITLES:
            state.part_title = title_case(text)
            return True

        m = RE_CHAPTER.match(text)
        if m:
            state.set_chapter(roman_to_int(m.group(1)))
            return True
        if text in CHAPTER_TITLES:
            state.chapter_title = title_case(text)
            return True

        m = RE_SECTION.match(text)
        if m:
            state.set_section(
                parse_num(m.group(1)),
                title_case(re.sub(r'\s+', ' ', m.group(2)).strip()),
            )
            return True
        return False

    def flush():
        if current is not None:
            paragraphs.append(dict(current))

    for tag in body_soup.find_all(['p', 'center', 'hr']):
        if tag.name == 'hr':
            continue
        text = clean_text(tag)
        if not text:
            continue

        bolds = tag.find_all('b')
        if bolds:
            for b in bolds:
                bt = re.sub(r'\s+', ' ', b.get_text(separator=' ')).strip()
                if bt:
                    process_bold_heading(bt)
            if tag.name == 'center':
                continue
            if tag.find('b') and RE_SECTION.match(
                re.sub(r'\s+', ' ', tag.find('b').get_text()).strip()
            ):
                continue

        numbered = numbered_paragraph(tag, RE_PARA_NUM)
        if numbered:
            flush()
            current = paragraph_record(*numbered, **state.kwargs())
        elif current is not None and not any(
            text.startswith(h) for h in ['[', 'Print', 'Index']
        ):
            all_bold = all(
                isinstance(c, NavigableString) and not str(c).strip()
                or (isinstance(c, Tag) and c.name == 'b')
                for c in tag.children
                if not (isinstance(c, NavigableString) and not str(c).strip())
            )
            if not all_bold:
                current['text'] += '\n\n' + normalise_footnote_refs(
                    clean_text(tag, preserve_formatting=True)
                )

    flush()
    return paragraphs


RE_NOTE_NUM     = re.compile(r'^(\d+)[.\s]\s*(.+)', re.DOTALL)
RE_NOTE_CHAPTER = re.compile(r'^Chapter\s+(\d+|[IVX]+)$', re.IGNORECASE)


def _extract_footnotes(notes_html):
    notes_soup = BeautifulSoup(notes_html, 'html.parser')
    footnotes = []
    part, chapter = 0, 0
    for tag in notes_soup.find_all('p'):
        text = clean_text(tag)
        if not text:
            continue
        if text == 'PART I':
            part, chapter = 1, 0; continue
        if text == 'PART II':
            part, chapter = 2, 0; continue
        if text in ('Preface', 'Introduction'):
            part, chapter = 0, 0; continue
        mc = RE_NOTE_CHAPTER.match(text)
        if mc:
            chapter = parse_num(mc.group(1)); continue
        footnote = parse_footnote(
            clean_text(tag, preserve_formatting=True),
            RE_NOTE_NUM, part=part, chapter=chapter
        )
        if footnote:
            footnotes.append(footnote)
    return footnotes


def _extract_latin_headings():
    """Latin source: bold tags carry a per-paragraph micro-summary keyed by §N."""
    with open(LT_SRC, encoding='latin-1') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')
    bolds = [re.sub(r'\s+', ' ', b.get_text(' ', strip=True))
             for b in soup.find_all('b')
             if re.sub(r'\s+', ' ', b.get_text(' ', strip=True))]
    out = {}
    i = 0
    while i < len(bolds):
        t = bolds[i]
        m = re.match(r'^(\d+)\.\s+(.+)', t)
        if m:
            out[int(m.group(1))] = m.group(2).strip()
            i += 1; continue
        if re.match(r'^\d+$', t) and i + 1 < len(bolds):
            nxt = bolds[i + 1]
            if not re.match(r'^\d+$', nxt) and not nxt.isupper():
                out[int(t)] = nxt.strip()
                i += 2; continue
        i += 1
    return out


def extract():
    body_html, notes_html = load_split(EN_SRC)
    body_html = body_html[body_html.find('<hr />'):]

    desc, promulgation = _extract_frontmatter(body_html)
    paragraphs = _walk_body(BeautifulSoup(body_html, 'html.parser'))
    footnotes = assign_footnote_context(
        _extract_footnotes(notes_html), paragraphs, preserve_scope=True
    )

    la = _extract_latin_headings()
    for p in paragraphs:
        p['heading_la'] = la.get(p['number'], '')

    return {
        'name': NAME,
        'hue': HUE,
        'source_url': SOURCE_URL,
        'author': AUTHOR,
        'issued_by': 'Second Vatican Council',
        'pontificate': 'Paul VI',
        'date': DATE,
        'identifier': IDENTIFIER,
        'desc': desc,
        'desc_post': '',
        'promulgation': title_case(promulgation),
        'paragraphs': paragraphs,
        'footnotes': footnotes,
    }
