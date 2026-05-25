"""Extractor for *Magnifica Humanitas* -- Leo XIV's 2026 AI encyclical.

The source uses the modern Vatican rich-text template, but unlike *Laudato
Si'* its primary section headings are unnumbered.  Synthetic section numbers
give the renderer stable IDs; the renderer suppresses their visible prefixes.
Bold-italic headings nested below primary headings become `sub_heading`.
"""

import re

from bs4 import BeautifulSoup

from core import clean_text, title_case


EN_SRC = 'sources/magnifica_humanitas_en.html'

NAME = 'Magnifica Humanitas'
SOURCE_URL = ('https://www.vatican.va/content/leo-xiv/en/encyclicals/documents/'
              '20260515-magnifica-humanitas.html')

# Front-matter signal: the abstract block sits in a div whose class list
# includes "abstract"; its first <p> carries the encyclical-letter preamble
# with the title sandwiched in the middle (separated by <br/> tags).
TITLE_UPPER = 'MAGNIFICA HUMANITAS'

RE_PARA = re.compile(r'^(\d+)\.\s+(.+)$', re.DOTALL)
RE_FOOTNOTE = re.compile(r'^\[\s*(\d+)\s*\]\s*(.+)$', re.DOTALL)
RE_CHAPTER = re.compile(r'^CHAPTER\s+([A-Z]+)$')
RE_INLINE_REF = re.compile(r'\[(\d{1,3})\]')
RE_SPACE_BEFORE_REF = re.compile(r' +(\(\d{1,3}\))')

CHAPTER_WORDS = {
    'ONE': 1, 'TWO': 2, 'THREE': 3, 'FOUR': 4, 'FIVE': 5,
}


def _normalise_refs(text):
    text = RE_INLINE_REF.sub(r'(\1)', text)
    return RE_SPACE_BEFORE_REF.sub(r'\1', text)


def _heading_text(p):
    text = re.sub(r'\s+', ' ', p.get_text(separator=' ', strip=True)).strip()
    return text.replace('R esponsibility', 'Responsibility')


def _title(text):
    return title_case(text).replace(' Ai', ' AI')


def _br_lines(tag):
    """get_text but with <br/> rendered as line breaks. Preserves the
    line structure of the source's centred title block, where the title
    sits between preamble and subtitle lines."""
    parts = []
    for child in tag.descendants:
        if hasattr(child, 'name') and child.name == 'br':
            parts.append('\n')
        elif isinstance(child, str):
            parts.append(child)
    raw = ''.join(parts)
    return [re.sub(r'\s+', ' ', ln).strip()
            for ln in raw.splitlines()
            if ln.strip()]


def _split_around_title(lines, title_upper):
    """Partition front-matter lines around the title line. Returns
    (pre_lines, post_lines). Title comparison is case-insensitive and
    strips trailing punctuation so 'MAGNIFICA HUMANITAS' matches even
    when the source decorates it."""
    norm = lambda s: re.sub(r'[^A-Z ]', '', s.upper()).strip()
    target = norm(title_upper)
    pre, post, seen = [], [], False
    for ln in lines:
        if not seen and norm(ln) == target:
            seen = True
            continue
        (post if seen else pre).append(ln)
    return pre, post


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
        fm_lines = _br_lines(abstract.find('p'))
        pre, post = _split_around_title(fm_lines, TITLE_UPPER)
        desc_pre = '\n'.join(pre)
        desc_post = '\n'.join(post)

    paragraphs = []
    footnotes = []
    promulgation = ''
    signature = ''

    chapter = 0
    chapter_title = ''
    chapter_subtitle = ''
    section = 1
    section_title = 'Introduction'
    sub_heading = ''
    pending_chapter_title = False
    in_conclusion = False

    for p in ps[first_body_idx:first_note_idx]:
        text = clean_text(p)
        if not text:
            continue

        m = RE_PARA.match(text)
        if m:
            pending_chapter_title = False
            paragraphs.append({
                'number': int(m.group(1)),
                'part': 0, 'part_title': '',
                'chapter': chapter, 'chapter_title': chapter_title,
                'chapter_subtitle': chapter_subtitle,
                'section': section, 'section_title': section_title,
                'sub_heading': sub_heading,
                'heading_la': '',
                'text': _normalise_refs(m.group(2).strip()),
            })
            continue

        heading = _heading_text(p)
        mc = RE_CHAPTER.match(heading)
        if mc and mc.group(1) in CHAPTER_WORDS:
            chapter = CHAPTER_WORDS[mc.group(1)]
            chapter_title = ''
            chapter_subtitle = ''
            section = 0
            section_title = ''
            sub_heading = ''
            pending_chapter_title = True
            in_conclusion = False
            continue

        if heading == 'CONCLUSION':
            # The TOC at the top of the source lists CONCLUSION parallel to
            # the numbered chapters, so it earns its own chapter slot rather
            # than being demoted to a final section. Its bold-italic
            # sub-titles then become sections of that chapter.
            chapter += 1
            chapter_title = 'Conclusion'
            chapter_subtitle = ''
            section = 0
            section_title = ''
            sub_heading = ''
            pending_chapter_title = False
            in_conclusion = True
            continue

        if p.find('b'):
            if pending_chapter_title and heading.isupper():
                if not chapter_title:
                    chapter_title = _title(heading)
                else:
                    separator = ' ' if chapter_subtitle else ''
                    chapter_subtitle += separator + _title(heading)
                continue

            subordinate = (not in_conclusion
                           and p.find('i') is not None
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
            promulgation = text
            continue

        # Papal signature: a short centred trailer after the dedication line,
        # e.g. "LEO PP. XIV". Match by position (post-promulgation) plus the
        # MS-Word centred-paragraph style so we don't catch stray prose.
        style = (p.get('style') or '').lower().replace(' ', '')
        if promulgation and 'text-align:center' in style and text:
            signature = text

    for p in ps[first_note_idx:]:
        text = clean_text(p)
        m = RE_FOOTNOTE.match(text)
        if m:
            footnotes.append({
                'part': 0,
                'chapter': 0,
                'number': int(m.group(1)),
                'text': _normalise_refs(m.group(2).strip()),
            })

    fn_to_chapter = {}
    for p in paragraphs:
        for ref in re.findall(r'\((\d{1,3})\)', p['text']):
            fn_to_chapter.setdefault(int(ref), p['chapter'])
    for fn in footnotes:
        fn['chapter'] = fn_to_chapter.get(fn['number'], 0)

    return {
        'name': NAME,
        'source_url': SOURCE_URL,
        'desc': desc_pre,
        'desc_post': desc_post,
        'promulgation': promulgation,
        'signature': signature,
        'paragraphs': paragraphs,
        'footnotes': footnotes,
    }
