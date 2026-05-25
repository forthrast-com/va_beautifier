"""Extractor for *Laudato Si'* — the modern Bootstrap Vatican.va template.

Structure (per <p> tag in <main>):
  - <p align="center">CHAPTER ONE</p>      — chapter delimiter (text → number)
  - <p align="center"><b>TITLE</b></p>     — chapter title (when preceded by CHAPTER N)
  - <p align="left"><b>I. TITLE</b></p>    — section heading (Roman prefix)
  - <p align="left"><i>Sub-heading</i></p> — sub-section heading
  - <p>N. Body text…</p>                   — numbered paragraph
  - <p>[N] Footnote text…</p>              — footnote (at tail of doc)

Inline refs use `[N]`; normalised to canonical `(N)` for the TOML.
No PART tier; no per-paragraph Latin micro-summary.
"""

import re
from bs4 import BeautifulSoup

from core import clean_text, only_child_is, roman_to_int, title_case


EN_SRC = 'sources/laudato_si_en.html'
LT_SRC = 'sources/laudato_si_lt.html'

NAME = "Laudato Si'"
SOURCE_URL = ('https://www.vatican.va/content/francesco/en/encyclicals/documents/'
              'papa-francesco_20150524_enciclica-laudato-si.html')

# The encyclical title arrives flat ("ENCYCLICAL LETTER LAUDATO SI' OF THE
# HOLY FATHER FRANCIS ON CARE FOR OUR COMMON HOME") — line breaks are
# typographic, not in the source. Re-split here so the renderer can centre
# the description block cleanly.
DESC = ("ENCYCLICAL LETTER\n"
        "OF THE HOLY FATHER FRANCIS\n"
        "ON CARE FOR OUR COMMON HOME")


# The `\s*` slack absorbs whitespace inserted by BeautifulSoup's text-node
# separator when an inline element falls between the number and its period
# (LS wraps the leading `1.` inside an <a> at every chapter break).
RE_PARA       = re.compile(r'^(\d+)\s*\.\s+(.+)$', re.DOTALL)
RE_FOOTNOTE   = re.compile(r'^\[\s*(\d+)\s*\]\s+(.+)$', re.DOTALL)
RE_SECTION_B  = re.compile(r'^([IVX]+)\s*\.\s+(.+)$')
RE_CHAPTER_C  = re.compile(r'^CHAPTER\s+([A-Z]+)$')
RE_INLINE_REF = re.compile(r'\[(\d{1,3})\]')

CHAPTER_WORDS = {
    'ONE': 1, 'TWO': 2, 'THREE': 3, 'FOUR': 4, 'FIVE': 5, 'SIX': 6,
    'SEVEN': 7, 'EIGHT': 8, 'NINE': 9, 'TEN': 10,
}

CHROME = ['script', 'style', 'meta', 'link', 'img', 'header',
          'footer', 'nav', 'svg', 'input', 'button', 'figure']


def _normalise_refs(text):
    return RE_INLINE_REF.sub(r'(\1)', text)


def extract():
    with open(EN_SRC, encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')
    for t in soup(CHROME):
        t.decompose()

    main = soup.find('main') or soup.body
    ps = main.find_all('p')

    # LS ends with two appended prayers and a "Given in Rome…" promulgation
    # block. None of them are numbered, so without an end-of-body marker
    # they'd be vacuumed up as continuations of §246. Pre-compute the
    # last numbered-paragraph position to cap body accumulation.
    last_body_idx = max(
        (i for i, p in enumerate(ps) if RE_PARA.match(clean_text(p))),
        default=-1,
    )

    paragraphs = []
    footnotes = []
    appendices = []
    promulgation = ''

    # ─── Phase 1: body walk (idx 0 .. last_body_idx) ─────────────────────
    chapter = 0
    chapter_title = ''
    section = 0
    section_title = ''
    sub_heading = ''
    pending_chapter_num = None

    for i in range(last_body_idx + 1):
        p = ps[i]
        text = clean_text(p)
        if not text:
            continue

        align = (p.get('align') or '').lower()
        has_b = bool(p.find('b'))

        # chapter marker: <p align="center">CHAPTER ONE</p> (no <b>)
        if align == 'center' and not has_b:
            mc = RE_CHAPTER_C.match(text)
            if mc and mc.group(1) in CHAPTER_WORDS:
                pending_chapter_num = CHAPTER_WORDS[mc.group(1)]
                continue

        # centred bold: chapter title (after CHAPTER N) or encyclical title (skip)
        if align == 'center' and has_b:
            if pending_chapter_num is not None:
                chapter = pending_chapter_num
                chapter_title = title_case(text)
                pending_chapter_num = None
                section = 0; section_title = ''
                sub_heading = ''
            continue

        # section heading: <p>'s only child is a <b> whose text matches "I. TITLE".
        # `align="left"` is set on the first section of chapter 1 and nowhere
        # else; child-shape is the reliable signal. The centred chapter title
        # is caught above so won't reach this branch.
        if only_child_is(p, 'b'):
            ms = RE_SECTION_B.match(text)
            if ms:
                section = roman_to_int(ms.group(1))
                section_title = title_case(ms.group(2))
                sub_heading = ''
                continue

        # sub-heading: <p> whose only non-whitespace child is an <i>.
        # The `align` attribute is unreliable: the first sub-heading in a
        # section gets align="left" but subsequent ones come back blank.
        if only_child_is(p, 'i'):
            sub_heading = text
            continue

        # numbered paragraph
        m = RE_PARA.match(text)
        if m:
            paragraphs.append({
                'number': int(m.group(1)),
                'part': 0, 'part_title': '',
                'chapter': chapter, 'chapter_title': chapter_title,
                'section': section, 'section_title': section_title,
                'sub_heading': sub_heading,
                'heading_la': '',
                'text': _normalise_refs(m.group(2).strip()),
            })
            continue

        # The conclusion is divided from its invitation to prayer by a
        # centred source ornament. Preserve its function, not its glyphs.
        if text == '* * * * *' and paragraphs:
            paragraphs[-1]['break_after'] = True
            continue

        # continuation: unnumbered body para following a numbered one (rare in LS)
        if paragraphs and not has_b:
            paragraphs[-1]['text'] += '\n\n' + _normalise_refs(text)

    # ─── Phase 2: appendix walk (last_body_idx+1 .. end) ─────────────────
    # The tail of LS holds: two prayers (each `<i>Title</i>` followed by
    # several body paragraphs), an italic "Given in Rome…" promulgation,
    # a "Franciscus" signature, then the footnotes.
    current = None
    def _flush():
        nonlocal current
        if current and current['text']:
            appendices.append(current)
        current = None

    for i in range(last_body_idx + 1, len(ps)):
        p = ps[i]
        text = clean_text(p)
        if not text:
            continue

        # footnote definitions stream in at the very end
        mfn = RE_FOOTNOTE.match(text)
        if mfn:
            _flush()
            footnotes.append({
                'part': 0, 'chapter': 0,
                'number': int(mfn.group(1)),
                'text': _normalise_refs(mfn.group(2).strip()),
            })
            continue

        # italic-only block: prayer title, the promulgation, or signature
        if only_child_is(p, 'i'):
            if text.startswith('Given in') or text.startswith('Given at'):
                _flush()
                promulgation = text
                continue
            _flush()
            current = {'title': text, 'text': ''}
            continue

        # "Franciscus" and other centred bold trailers — ignore
        align = (p.get('align') or '').lower()
        if align == 'center' and p.find('b'):
            continue

        # body of current prayer
        if current is not None:
            if current['text']:
                current['text'] += '\n\n'
            current['text'] += _normalise_refs(text)

    _flush()

    # Back-fill footnote chapters by first-cite — keeps the renderer's
    # drawer-by-chapter grouping intact (see make_html.py:fn_section).
    fn_to_chapter = {}
    for p in paragraphs:
        for ref in re.findall(r'\((\d{1,3})\)', p['text']):
            n = int(ref)
            if n not in fn_to_chapter:
                fn_to_chapter[n] = p['chapter']
    for fn in footnotes:
        fn['chapter'] = fn_to_chapter.get(fn['number'], 0)

    return {
        'name': NAME,
        'source_url': SOURCE_URL,
        'desc': DESC,
        'promulgation': promulgation,
        'paragraphs': paragraphs,
        'footnotes': footnotes,
        'appendices': appendices,
    }
