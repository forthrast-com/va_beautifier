"""Extractor for *Gaudium et Spes* — the old flat Vatican.va template.

Quirks:
  - Sources served as ISO-8859-1 (EN) and latin-1 (LA), not UTF-8.
  - Structure carried by <b> headings and <center> blocks, not classes.
  - Inline footnote refs use `(N)` (already canonical).
  - Latin source provides a per-paragraph micro-summary (`heading_la`),
    keyed by paragraph number — this is a GeS-specific affordance.
"""

import re
from bs4 import NavigableString, Tag

from core import (
    HeadingState,
    assign_footnote_context,
    clean_text,
    flatten_ws,
    make_soup,
    normalise_footnote_refs,
    numbered_paragraph,
    paragraph_record,
    parse_num,
    parse_footnote,
    repair,
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
        text = flatten_ws(text)

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
                title_case(flatten_ws(m.group(2))),
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
                bt = flatten_ws(b.get_text(separator=' '))
                if bt:
                    process_bold_heading(bt)
            if tag.name == 'center':
                continue
            if tag.find('b') and RE_SECTION.match(
                flatten_ws(tag.find('b').get_text())
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
    notes_soup = make_soup(notes_html)
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
        soup = make_soup(f.read())
    bolds = [flatten_ws(b.get_text(' ', strip=True))
             for b in soup.find_all('b')
             if flatten_ws(b.get_text(' ', strip=True))]
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

    # §62's closing marker is typed (16) in a chapter whose note block stops
    # at 15 — the document's only cite with no note, while note 15 is the
    # only note with no cite. Note 15 is "Dogmatic Constitution on the
    # Church, Chapter IV, n. 37", and the Latin edition (which numbers
    # continuously) carries exactly that citation as (138), attached to the
    # identical sentence: "iusta libertas inquirendi, cogitandi necnon
    # mentem suam in humilitate et fortitudine aperiendi in iis in quibus
    # peritia gaudent (138)". So (16) is a typo for (15), not a lost note.
    body_html = repair(
        body_html,
        'they enjoy competence.(16)',
        'they enjoy competence.(15)',
        what='GeS §62 cite mistyped as (16)',
    )

    # §57 lost its (3) marker outright: the Latin carries four cites here
    # (125–128) against the English's three, and at the constant offset of
    # 123 the survivors line up exactly — EN (2) = LA (125) "Col. 3:2",
    # EN (4) = LA (127) "Prov. 8:30-31". The gap is EN note 3, "Cf. Gen.
    # 1:28", which the Latin places mid-clause: "terrae subiiciendae (126)
    # creationisque perficiendae". Restored at the matching English point,
    # after the punctuation per this document's house style. Without it the
    # note is cited nowhere, and an uncited note never reaches the books —
    # Gen 1:28 was absent from the EPUB and all three PDFs.
    body_html = repair(
        body_html,
        'that he should subdue the earth, perfect creation',
        'that he should subdue the earth,(3) perfect creation',
        what='GeS §57 dropped its (3) cite',
    )

    # §14 carries two faults that explain each other. Its first marker is
    # typed (6) — "1 Cor. 6:13-20", which is about the *body* — while
    # sitting on "raise their voice in free praise of the Creator", where
    # note 5 ("Dan. 3:57-90", the Benedicite, all creation praising God)
    # belongs and which is otherwise cited nowhere. The clause 1 Cor. 6
    # actually serves, "man glorify God in his body", carries no marker at
    # all. The Latin has all three in order — (13) Dan at "vocem
    # attollant", (14) I Cor at "glorificet in corpore suo", (15) at "corda
    # scrutatur" — against the English's two.
    body_html = repair(
        body_html,
        'praise of the Creator.(6)',
        'praise of the Creator.(5)',
        what='GeS §14 first cite mislabelled (6) for (5)',
    )
    body_html = repair(
        body_html,
        'glorify God in his body and forbid it',
        'glorify God in his body(6) and forbid it',
        what='GeS §14 dropped its (6) cite',
    )

    # §18 loses the cite for note 15, "1 Cor. 15:56-57" — "the sting of
    # death is sin … thanks be to God, who gives us the victory". The Latin
    # marks it (23) at "ad vitam resurgens adeptus est".
    body_html = repair(
        body_html,
        'He freed man from death.',
        'He freed man from death.(15)',
        what='GeS §18 dropped its (15) cite',
    )

    # §64 loses the cite for note 2 (Quadragesimo Anno) on the quoted phrase
    # it supports; the Latin marks it (140) at "intra fines ordinis moralis".
    body_html = repair(
        body_html,
        "moral order,&quot; so that God's plan",
        "moral order,&quot;(2) so that God's plan",
        what='GeS §64 dropped its (2) cite',
    )

    # Part II chapter 1 mislabels two markers rather than losing them, so
    # the marker *count* matches the Latin and only the orphaned notes give
    # it away — §48 cites (6) twice and §52 repeats (13), while notes 5 and
    # 15 are cited nowhere. Both are settled by content: §48's first (6)
    # sits on "He loved the Church and handed Himself over on her behalf",
    # which is note 5, "Eph. 5:25", verbatim; §52's on "redeeming the
    # present time", which is note 15, "Eph. 5:16".
    body_html = repair(
        body_html,
        'handed Himself over on her behalf,(6)',
        'handed Himself over on her behalf,(5)',
        what='GeS §48 cite mislabelled (6) for (5)',
    )
    body_html = repair(
        body_html,
        'redeeming the present time(13)',
        'redeeming the present time(15)',
        what='GeS §52 cite mislabelled (13) for (15)',
    )

    # §75 loses the cite for note 7 (Mater et Magistra, on socialization).
    # The Latin marks it (161) immediately after "socializationem", so it is
    # placed on the term rather than at the end of the sentence.
    body_html = repair(
        body_html,
        'between socialization and the autonomy',
        'between socialization(7) and the autonomy',
        what='GeS §75 dropped its (7) cite',
    )

    desc, promulgation = _extract_frontmatter(body_html)
    paragraphs = _walk_body(make_soup(body_html))
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
        'type': 'council_constitution',
        'kind_long': 'Pastoral Constitution on the Church in the Modern World',
        'desc': desc,
        'desc_post': '',
        'promulgation': title_case(promulgation),
        'paragraphs': paragraphs,
        'footnotes': footnotes,
    }
