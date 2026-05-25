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
DESC = ('ENCYCLICAL LETTER\n'
        'OF HIS HOLINESS POPE LEO XIV\n'
        'ON SAFEGUARDING THE HUMAN PERSON\n'
        'IN THE TIME OF ARTIFICIAL INTELLIGENCE')

RE_PARA = re.compile(r'^(\d+)\.\s+(.+)$', re.DOTALL)
RE_FOOTNOTE = re.compile(r'^\[\s*(\d+)\s*\]\s*(.+)$', re.DOTALL)
RE_CHAPTER = re.compile(r'^CHAPTER\s+([A-Z]+)$')
RE_INLINE_REF = re.compile(r'\[(\d{1,3})\]')

CHAPTER_WORDS = {
    'ONE': 1, 'TWO': 2, 'THREE': 3, 'FOUR': 4, 'FIVE': 5,
}


def _normalise_refs(text):
    return RE_INLINE_REF.sub(r'(\1)', text)


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

    paragraphs = []
    footnotes = []
    promulgation = ''

    chapter = 0
    chapter_title = ''
    chapter_subtitle = ''
    section = 1
    section_title = 'Introduction'
    sub_heading = ''
    pending_chapter_title = False

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
            continue

        if heading == 'CONCLUSION':
            section += 1
            section_title = 'Conclusion'
            sub_heading = ''
            pending_chapter_title = False
            continue

        if p.find('b'):
            if pending_chapter_title and heading.isupper():
                if not chapter_title:
                    chapter_title = _title(heading)
                else:
                    separator = ' ' if chapter_subtitle else ''
                    chapter_subtitle += separator + _title(heading)
                continue

            subordinate = (p.find('i') is not None and chapter != 0
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
        'desc': DESC,
        'promulgation': promulgation,
        'paragraphs': paragraphs,
        'footnotes': footnotes,
    }
