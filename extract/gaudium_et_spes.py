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

from core import clean_text, roman_to_int, parse_num, title_case


EN_SRC = 'sources/gaudium_et_spes_en.html'
LT_SRC = 'sources/gaudium_et_spes_lt.html'

NAME = 'Gaudium et Spes'
SOURCE_URL = ('https://www.vatican.va/archive/hist_councils/ii_vatican_council/'
              'documents/vat-ii_const_19651207_gaudium-et-spes_en.html')


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


def _br_text(tag):
    """get_text but with <br/> rendered as \\n — keeps line breaks for front matter."""
    parts = []
    for child in tag.descendants:
        if hasattr(child, 'name') and child.name == 'br':
            parts.append('\n')
        elif isinstance(child, str):
            parts.append(child)
    return re.sub(r'[ \t]+', ' ', ''.join(parts)).strip()


def _extract_frontmatter(body_html):
    """Split the GeS front-matter <p> around its 'GAUDIUM ET SPES' title.
    Lines before the title become `desc` (preamble); lines after become
    `desc_post` (the 'PROMULGATED BY... DECEMBER 7, 1965' block). GeS keeps
    that date line in the front matter rather than as an end-of-doc
    dedication, so it lives in `desc_post`, not `promulgation`."""
    soup = BeautifulSoup(body_html, 'html.parser')
    fm = next((p for p in soup.find_all('p')
               if 'PASTORAL CONSTITUTION' in p.get_text()), None)
    if not fm:
        return '', ''
    text = _br_text(fm)
    desc_m = re.match(r'(.+?)\s*GAUDIUM ET SPES', text, re.DOTALL)
    post_m = re.search(r'GAUDIUM ET SPES\s*\n(.+)', text, re.DOTALL)
    desc = desc_m.group(1).strip() if desc_m else ''
    post = post_m.group(1).strip() if post_m else ''
    return desc, post


def _walk_body(body_soup):
    state = {
        'part': 0, 'part_title': '',
        'chapter': 0, 'chapter_title': '',
        'section': 0, 'section_title': '',
    }
    paragraphs = []
    current = None

    def process_bold_heading(text):
        text = re.sub(r'\s+', ' ', text).strip()

        if text == 'PREFACE':
            state.update(part=0, part_title='Preface',
                         chapter=0, chapter_title='',
                         section=0, section_title='')
            return True
        if text == 'INTRODUCTORY STATEMENT THE SITUATION OF MEN IN THE MODERN WORLD':
            state.update(part=0, part_title=title_case(text),
                         chapter=0, chapter_title='',
                         section=0, section_title='')
            return True

        m = RE_PART.match(text)
        if m:
            state.update(part=roman_to_int(m.group(1)), part_title='',
                         chapter=0, chapter_title='',
                         section=0, section_title='')
            return True
        if text in PART_TITLES:
            state['part_title'] = title_case(text)
            return True

        m = RE_CHAPTER.match(text)
        if m:
            state.update(chapter=roman_to_int(m.group(1)), chapter_title='',
                         section=0, section_title='')
            return True
        if text in CHAPTER_TITLES:
            state['chapter_title'] = title_case(text)
            return True

        m = RE_SECTION.match(text)
        if m:
            state.update(section=parse_num(m.group(1)),
                         section_title=title_case(re.sub(r'\s+', ' ', m.group(2)).strip()))
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

        m = RE_PARA_NUM.match(text)
        if m:
            flush()
            current = {
                'number': int(m.group(1)),
                **{k: state[k] for k in state},
                'text': m.group(2).strip(),
            }
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
                current['text'] += '\n\n' + text

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
        m = RE_NOTE_NUM.match(text)
        if m:
            footnotes.append({
                'part': part, 'chapter': chapter,
                'number': int(m.group(1)),
                'text': m.group(2).strip(),
            })
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
    with open(EN_SRC, encoding='iso-8859-1') as f:
        html = f.read()

    notes_split = html.split('NOTES</b>', 1)
    body_html = notes_split[0]
    notes_html = notes_split[1] if len(notes_split) > 1 else ''
    body_html = body_html[body_html.find('<hr />'):]

    desc, desc_post = _extract_frontmatter(body_html)
    paragraphs = _walk_body(BeautifulSoup(body_html, 'html.parser'))
    footnotes = _extract_footnotes(notes_html)

    la = _extract_latin_headings()
    for p in paragraphs:
        p['heading_la'] = la.get(p['number'], '')

    return {
        'name': NAME,
        'source_url': SOURCE_URL,
        'desc': desc,
        'desc_post': desc_post,
        'paragraphs': paragraphs,
        'footnotes': footnotes,
    }
