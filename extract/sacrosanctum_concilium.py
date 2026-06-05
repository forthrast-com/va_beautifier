"""Extractor for *Sacrosanctum Concilium* — old flat Vatican.va template.

Shape:
  - Sources served as ISO-8859-1 (EN) and latin-1 (LA); structure carried by
    <center><b>…</b></center> blocks and <p><b>…</b></p> headings.
  - Chapters delimited `CHAPTER N` inside <center>, followed by a centred
    bold title (chapter VI has a typo: the source splits 'CHAPTER' and
    'VI SACRED MUSIC' so we join the bolds inside each <center> and parse
    the combined string).
  - Sections under chapter I are `<p><b>N. Title</b></p>` or
    `<p><b>II. Title</b></p>` — the first uses an Arabic digit, the rest
    Romans. We accept either.
  - Sub-headings inside section III are `<p><i><b>A) Title</b></i></p>`
    through F).
  - Inline footnote refs use `[N]` (LS-style); normalised to canonical
    `(N)`. Notes block has no chapter delimiters — context is recovered
    from the first citing paragraph.
  - A ruled-off calendar declaration follows chapter VII; emitted through
    `appendices[]`, not invented as an eighth chapter.
"""

import re
from bs4 import BeautifulSoup

from core import (
    assign_footnote_context,
    clean_text,
    normalise_footnote_refs,
    paragraph_record,
    parse_footnote,
    parse_num,
    roman_to_int,
    title_case,
)
from project import SOURCES


EN_SRC = SOURCES / 'Sacrosanctum Concilium_en.html'

NAME = 'Sacrosanctum Concilium'
HUE = 268
SOURCE_URL = ('https://www.vatican.va/archive/hist_councils/ii_vatican_council/'
              'documents/vat-ii_const_19631204_sacrosanctum-concilium_en.html')
AUTHOR = 'Second Vatican Council'
DATE = '1963-12-04'
IDENTIFIER = 'council:sacrosanctum-concilium:1963-12-04'

RE_CHAPTER_BARE = re.compile(r'^CHAPTER\s+([IVX]+)\s*$')
RE_CHAPTER_COMBINED = re.compile(r'^CHAPTER\s+([IVX]+)\s+(.+)$', re.DOTALL)
RE_CHAPTER_NUM_PLUS = re.compile(r'^([IVX]+)\s+(.+)$', re.DOTALL)
RE_APPENDIX_LINE = re.compile(r'^APPENDIX(?:\s+(.+))?$', re.DOTALL)
RE_SECTION_BOLD = re.compile(r'^([IVX]+|\d+)\s*\.\s+(.+)$', re.DOTALL)
RE_SUBHEADING = re.compile(r'^([A-F])\)\s*(.+)$', re.DOTALL)
RE_PARA_NUM = re.compile(r'^\s*(\d+)\s*\.\s+(.+)$', re.DOTALL)
RE_FOOTNOTE = re.compile(r'^\[\s*(\d+)\s*\]\s*(.+)$', re.DOTALL)


def _br_text(tag):
    parts = []
    for child in tag.descendants:
        if hasattr(child, 'name') and child.name == 'br':
            parts.append('\n')
        elif isinstance(child, str):
            parts.append(child)
    return re.sub(r'[ \t]+', ' ', ''.join(parts)).strip()


def _extract_frontmatter(body_html):
    """The SC front matter is one <p> whose text concatenates the alt-language
    bar, 'CONSTITUTION ON THE SACRED LITURGY', 'SACROSANCTUM CONCILIUM',
    and 'SOLEMNLY PROMULGATED BY HIS HOLINESS POPE PAUL VI ON DECEMBER 4,
    1963'. Split the display title from its semantic promulgation."""
    soup = BeautifulSoup(body_html, 'html.parser')
    fm = next((p for p in soup.find_all('p')
               if 'CONSTITUTION ON THE SACRED LITURGY' in p.get_text()), None)
    if not fm:
        return '', ''
    text = re.sub(r'\s+', ' ', _br_text(fm)).strip()
    text = re.sub(r'^\[.*?\]\s*', '', text)
    m = re.match(
        r'(.+?)\s+SACROSANCTUM CONCILIUM\s+(.+)$', text, re.DOTALL
    )
    if not m:
        return text, ''
    return m.group(1).strip(), m.group(2).strip()


def _joined_bolds(tag):
    parts = [
        re.sub(r'\s+', ' ', b.get_text(' ', strip=True))
        for b in tag.find_all('b')
    ]
    return re.sub(r'\s+', ' ', ' '.join(p for p in parts if p)).strip()


def _walk_body(corpo):
    state = {
        'part': 0, 'part_title': '',
        'chapter': 0, 'chapter_title': '',
        'section': 0, 'section_title': '',
        'sub_heading': '',
    }
    paragraphs = []
    appendices = []
    current = None
    seen_frontmatter = False
    appendix_active = False
    appendix_title = ''
    appendix_blocks = []
    appendix_item_num = 0
    # SC numbers paragraphs globally 1..130. A few paragraphs (notably ¶22
    # under chapter 1, section 3) carry an internal `1.` / `2.` / `3.` list
    # that the source renders as siblings of the parent paragraph. Track
    # the last accepted body number so we can recognise the next paragraph
    # only when its leading digit is the expected successor.
    last_num = 0

    def flush():
        if current is not None:
            paragraphs.append(dict(current))

    def set_chapter(num, title=''):
        state.update(chapter=num, chapter_title=title,
                     section=0, section_title='',
                     sub_heading='')

    for tag in corpo.find_all(['p', 'center', 'li', 'hr']):
        if tag.name == 'hr':
            # The source rules off the calendar declaration from article 130.
            if current is not None and not appendix_active:
                current['break_after'] = True
            continue
        if tag.name == 'center':
            joined = _joined_bolds(tag)
            if not joined:
                continue

            if 'CONSTITUTION ON THE SACRED LITURGY' in joined:
                continue
            if joined == 'INTRODUCTION':
                state.update(part=0, part_title='Introduction',
                             chapter=0, chapter_title='',
                             section=0, section_title='', sub_heading='')
                seen_frontmatter = True
                continue

            mc = RE_CHAPTER_BARE.match(joined)
            if mc:
                set_chapter(roman_to_int(mc.group(1)))
                state['part_title'] = ''
                continue
            mc = RE_CHAPTER_COMBINED.match(joined)
            if mc:
                set_chapter(roman_to_int(mc.group(1)),
                            title_case(mc.group(2).strip()))
                state['part_title'] = ''
                continue

            ma = RE_APPENDIX_LINE.match(joined)
            if ma:
                flush()
                current = None
                title = (ma.group(1) or '').strip()
                appendix_title = title_case(title) if title else 'Appendix'
                appendix_active = True
                continue
            continue

        # <p> handling
        text = clean_text(tag)
        if not text:
            continue

        bolds = tag.find_all('b')
        all_bold = bool(bolds) and tag.get_text(strip=True) == \
            ''.join(b.get_text(strip=True) for b in bolds)
        italic_bold = (
            tag.find('i') is not None and tag.find('b') is not None
        )

        # Skip the language-switch chrome line.
        if text.startswith('['):
            continue
        if 'CONSTITUTION ON THE SACRED LITURGY' in text:
            continue

        if appendix_active:
            # The centred bold title was already captured from its parent
            # `<center>`; retain the appendix prose and numbered list items.
            if all_bold:
                continue
            rich = clean_text(tag, preserve_formatting=True)
            if tag.name == 'li':
                appendix_item_num += 1
                rich = f'{appendix_item_num}. {rich}'
            appendix_blocks.append(rich)
            continue

        # Sub-heading: italic+bold A)..F)
        if italic_bold:
            ms = RE_SUBHEADING.match(text)
            if ms:
                state['sub_heading'] = title_case(ms.group(2).strip())
                continue

        # Standalone bold heading (no italic wrap)
        if all_bold and not appendix_active:
            # Section heading: leading "N." or "II."
            msec = RE_SECTION_BOLD.match(text)
            if msec:
                state.update(
                    section=parse_num(msec.group(1)),
                    section_title=title_case(msec.group(2).strip()),
                    sub_heading='',
                )
                continue
            # Chapter-title row that follows a bare "CHAPTER N" center
            if state['chapter'] and not state['chapter_title']:
                state['chapter_title'] = title_case(text)
                continue
            # Chapter-title row already set but a second centred title repeats
            # — ignore quietly.
            continue

        # Body paragraph. Only accept the next strictly-greater number so
        # `<p>1.` / `<p>2.` list items embedded inside a paragraph (¶22's
        # numbered norms etc.) don't fork off as new records; source typos
        # that skip an index (¶87 is mislabelled "81." in the snapshot
        # then resumes at 88) survive as a gap rather than a stuck parser.
        mp = RE_PARA_NUM.match(text)
        if mp and not appendix_active and int(mp.group(1)) > last_num:
            flush()
            rich = clean_text(tag, preserve_formatting=True)
            mr = RE_PARA_NUM.match(rich)
            current = paragraph_record(
                int(mp.group(1)), mr.group(2),
                bracketed_refs=True, **state
            )
            last_num = int(mp.group(1))
            continue

        # Continuation line under the currently open paragraph
        if current is not None and seen_frontmatter:
            current['text'] += '\n\n' + normalise_footnote_refs(
                clean_text(tag, preserve_formatting=True),
                bracketed=True,
            )

    flush()
    if appendix_blocks:
        appendices.append({
            'title': appendix_title,
            'kind': 'declaration',
            'text': '\n\n'.join(appendix_blocks),
        })
    return paragraphs, appendices


def _extract_footnotes(notes_html):
    soup = BeautifulSoup(notes_html, 'html.parser')
    footnotes = []
    for tag in soup.find_all('p'):
        rich = clean_text(tag, preserve_formatting=True)
        note = parse_footnote(rich, RE_FOOTNOTE, bracketed_refs=True)
        if note:
            footnotes.append(note)
    return footnotes


def extract():
    with open(EN_SRC, encoding='iso-8859-1') as f:
        html = f.read()

    notes_split = html.split('NOTES</b>', 1)
    body_html = notes_split[0]
    notes_html = notes_split[1] if len(notes_split) > 1 else ''

    # Source placement is decorative; promulgation is end matter in the
    # canonical edition, consistently with the other document dialects.
    desc, promulgation = _extract_frontmatter(body_html)

    soup = BeautifulSoup(body_html, 'html.parser')
    corpo = soup.find(id='corpo') or soup.body or soup
    paragraphs, appendices = _walk_body(corpo)
    footnotes = assign_footnote_context(_extract_footnotes(notes_html), paragraphs)

    return {
        'name': NAME,
        'hue': HUE,
        'source_url': SOURCE_URL,
        'author': AUTHOR,
        'date': DATE,
        'identifier': IDENTIFIER,
        'desc': desc,
        'desc_post': '',
        'promulgation': title_case(promulgation),
        'paragraphs': paragraphs,
        'footnotes': footnotes,
        'appendices': appendices,
    }
