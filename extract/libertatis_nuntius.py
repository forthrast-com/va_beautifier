"""Extractor for *Libertatis Nuntius* — the 1984 CDF instruction on
certain aspects of the "Theology of Liberation".

Shape — a fourth variant, flatter than anything else implemented:
  - No `<main>`, no `<center>`, no named anchors anywhere. The document is
    180 sibling `<p>` tags whose `align` attribute is the only structural
    signal, so the walk keys on `is_centred` + child shape throughout.
  - Chapters are centred bold `<p>` carrying a Roman numeral and title
    split across a `<br/>`: `I<br/>AN INSPIRATION`. Chapter IX spells its
    numeral `IX.` with a trailing stop; the others don't. A final centred
    bold `CONCLUSION` closes the document with no numeral, which
    `core.is_unnumbered_chapter` already renders title-only.
  - **Paragraph numbers restart at 1 in every chapter** (I.1–9, II.1–4, …
    XI.1–18), which is how the instruction is cited. That's the
    `chapter_numbering` layout flag: anchors become `para-{chapter}-{n}`
    and the continuity invariant checks each chapter's own run.
  - Five unnumbered paragraphs open the document before chapter I. They
    carry `hide_number` and sequential numbers so they still anchor.
  - Body cites are bare `[N]` (LS-style); definitions live in a trailing
    block after a centred bold `Footnotes` heading, each a `<p>` opening
    `(N) …`. Notes are numbered globally 1–35 even though paragraphs
    aren't, so the default `assign_footnote_context` scoping applies.
  - End matter: two italic promulgation paragraphs, then Ratzinger
    (centred) and Bovone (right-aligned), each a bold name over an italic
    role. Both become `signatories[]`.

Two defects in the snapshot, handled differently because only one is
recoverable. Chapter VI runs 1–5 then jumps to 7: the missing ¶6 is simply
not on the page, so it is recorded in `KNOWN_SOURCE_DEFECTS`
(`tests/test_pipeline_invariants.py`) rather than invented. The same
chapter's §5 types its Puebla marker as `[19]`, a number already spent at
§3 — that one *is* recoverable and is repaired at load; see `extract()`.
"""

import re

from core import (
    assign_footnote_context,
    br_text,
    clean_text,
    extract_footnotes,
    flatten_ws,
    is_centred,
    make_soup,
    paragraph_record,
    repair,
    roman_to_int,
    title_case,
)
from project import SOURCES


EN_SRC = SOURCES / 'theology_of_liberation_en.html'

NAME = 'Libertatis Nuntius'
HUE = 320
SOURCE_URL = (
    'https://www.vatican.va/roman_curia/congregations/cfaith/documents/'
    'rc_con_cfaith_doc_19840806_theology-liberation_en.html'
)
AUTHOR = 'Joseph Cardinal Ratzinger'
DATE = '1984-08-06'
IDENTIFIER = 'cdf:libertatis-nuntius:1984-08-06'

RE_PARA = re.compile(r'^(\d+)\s*\.\s+(.+)$', re.DOTALL)
RE_NOTE = re.compile(r'^\((\d+)\)\s*(.+)$', re.DOTALL)
# `I`, `IX.` — the numeral line of a chapter head, stop optional.
RE_CHAPTER_NUM = re.compile(r'^([IVXL]+)\.?$')

DESC = 'Congregation for the Doctrine of the Faith'
TITLE_LINE = 'INSTRUCTION ON CERTAIN ASPECTS'
NOTES_HEADING = 'Footnotes'


def _is_bold_heading(tag):
    """A centred (or right-aligned) `<p>` whose whole text is bold.

    Every structural marker in this source has that shape: chapter heads,
    the notes heading, and the two signature blocks. Body prose is
    `align="left"` and never wholly bold.
    """
    bolds = tag.find_all('b')
    if not bolds:
        return False
    return tag.get_text(strip=True) == ''.join(
        b.get_text(strip=True) for b in bolds
    ) or bool(tag.find('b'))


def _chapter_head(tag):
    """`(number, title)` for a centred bold chapter head, else None.

    The numeral and title are separated by a `<br/>`, so read the tag with
    `br_text` and split on the line break rather than guessing where the
    Roman numeral stops — `I AN INSPIRATION` has no other delimiter, and a
    greedy `^[IVX]+` would happily eat the `I` of a title.
    """
    if not is_centred(tag) or not tag.find('b'):
        return None
    lines = [line.strip() for line in br_text(tag).splitlines() if line.strip()]
    if len(lines) != 2:
        return None
    match = RE_CHAPTER_NUM.match(lines[0])
    if not match:
        return None
    return roman_to_int(match.group(1)), title_case(flatten_ws(lines[1]))


def _signatory(tag):
    """`{name, role}` for a bold-name-over-italic-role signature block.

    Bovone's role runs over two `<br/>`-separated lines ("Titular Archbishop
    of Caesarea in Numidia" / "Secretary"); `br_text` keeps the break so the
    join can punctuate it rather than running the two into one phrase.
    """
    bold = tag.find('b')
    italic = tag.find('i')
    if not bold or not italic:
        return None
    name = flatten_ws(bold.get_text(' ', strip=True))
    lines = [flatten_ws(line) for line in br_text(italic).splitlines()]
    role = ', '.join(line for line in lines if line)
    if not name or not role:
        return None
    return {'name': name, 'role': role}


def _is_wholly_italic(tag):
    """True when the paragraph's entire visible text sits inside `<i>`.

    The instruction's two closing promulgation paragraphs have that shape;
    body prose only ever italicises fragments (titles, quoted terms).
    """
    italics = tag.find_all('i')
    if not italics:
        return False
    return tag.get_text(strip=True) == ''.join(
        i.get_text(strip=True) for i in italics
    )


def _walk_body(tags):
    """Route every body `<p>` to a paragraph, heading, or end-matter slot.

    Route, don't drop: an unclassified non-empty paragraph joins the open
    record as continuation prose rather than falling on the floor.
    """
    paragraphs = []
    signatories = []
    promulgation = []
    chapter = 0
    chapter_title = ''
    # Unnumbered-prose counter, reset per chapter. Both the opening preface
    # and the closing CONCLUSION are runs of numberless paragraphs; they get
    # sequential hidden numbers so each still anchors and appears in the
    # contents, while a chapter that *has* numbered paragraphs treats stray
    # prose as continuation of the open record instead.
    unnumbered = 0
    numbered_seen = False

    for tag in tags:
        text = clean_text(tag)
        if not text:
            continue
        # Front matter: the issuing body and the display title, both of
        # which the renderer supplies from metadata. The source sets both
        # in caps; `DESC` carries the cased form used for display.
        if text.upper() in (DESC.upper(),) or text.upper().startswith(TITLE_LINE):
            continue

        head = _chapter_head(tag)
        if head:
            chapter, chapter_title = head
            unnumbered, numbered_seen = 0, False
            continue

        if is_centred(tag) and _is_bold_heading(tag):
            # A centred bold line that isn't a numbered chapter head is
            # either `CONCLUSION` or a signature block.
            signatory = _signatory(tag)
            if signatory:
                signatories.append(signatory)
                continue
            chapter += 1
            chapter_title = title_case(flatten_ws(text))
            unnumbered, numbered_seen = 0, False
            continue

        if not is_centred(tag) and _signatory(tag):
            # Bovone's block is right-aligned, not centred.
            signatories.append(_signatory(tag))
            continue

        rich = clean_text(tag, preserve_formatting=True)
        match = RE_PARA.match(text)
        if match:
            numbered_seen = True
            rich_match = RE_PARA.match(rich)
            paragraphs.append(paragraph_record(
                int(match.group(1)),
                (rich_match or match).group(2),
                chapter=chapter,
                chapter_title=chapter_title,
                bracketed_refs=True,
            ))
            continue

        # End matter: the dateline stanza closing the instruction.
        if _is_wholly_italic(tag):
            promulgation.append(rich)
            continue

        if not numbered_seen:
            # Numberless prose in a chapter that has none — the preface and
            # the CONCLUSION. Number it so it still anchors, but keep the
            # number off the page.
            unnumbered += 1
            record = paragraph_record(
                unnumbered, rich,
                chapter=chapter, chapter_title=chapter_title,
                bracketed_refs=True,
            )
            record['hide_number'] = True
            paragraphs.append(record)
            continue

        paragraphs[-1]['text'] += '\n\n' + rich

    return paragraphs, signatories, '\n\n'.join(promulgation)


def extract():
    raw = EN_SRC.read_text(encoding='utf-8')

    # The snapshot types chapter VI §5's Puebla marker as `[19]`, a number
    # already spent at §3 — leaving note 20 defined but cited nowhere and
    # `[19]` the document's only backward-running marker. Note 20 is
    # "Cf. n. 1134–1165 and n. 1166–1205", the Puebla Final Document's
    # ranges for the preferential option for the poor and for the young,
    # which is precisely what the next sentence goes on to describe; note 19
    # (Gaudium et Spes 39 / Quadragesimo Anno) has nothing to do with
    # Puebla. Repaired at load so the walker sees the marker the text means.
    raw = repair(raw,
                 "Conference of 'Puebla' [19]",
                 "Conference of 'Puebla' [20]",
                 what='LN ch VI §5 Puebla marker mistyped as [19]')

    soup = make_soup(raw)
    tags = soup.find_all('p')

    # The notes heading splits body from definitions. Everything before it
    # is the instruction, everything after it a `(N) …` note.
    split = next(
        (i for i, p in enumerate(tags)
         if is_centred(p) and clean_text(p) == NOTES_HEADING),
        len(tags),
    )

    paragraphs, signatories, promulgation = _walk_body(tags[:split])
    footnotes = assign_footnote_context(
        extract_footnotes(tags[split + 1:], RE_NOTE, bracketed_refs=True),
        paragraphs,
    )

    return {
        'name': NAME,
        'hue': HUE,
        'source_url': SOURCE_URL,
        'author': AUTHOR,
        'issued_by': 'Congregation for the Doctrine of the Faith',
        'pontificate': 'John Paul II',
        'date': DATE,
        'identifier': IDENTIFIER,
        # A CDF instruction is the same species of document as Antiqua et
        # nova: a dicastery exercising the Pope's authority without speaking
        # in his voice. Same tile kind and authority rank.
        'type': 'curia_note',
        'subtitle': (
            'Instruction on Certain Aspects of the "Theology of Liberation"'
        ),
        'desc': DESC,
        # The source's own title, under the Latin incipit — the two lines
        # are the source's, split on its `<br/>`.
        'desc_post': 'INSTRUCTION ON CERTAIN ASPECTS OF THE\n'
                     '"THEOLOGY OF LIBERATION"',
        # The instruction is cited by Roman chapter numeral plus its
        # chapter-scoped paragraph number ("Libertatis Nuntius VII, 9"), so
        # the numerals belong on the page. The trailing Conclusion still
        # renders bare via `core.is_unnumbered_chapter`.
        'chapter_style': 'roman',
        'promulgation': promulgation,
        'layout': {
            'long': True,
            'mobile_inline': True,
            'chapter_numbering': True,
        },
        'paragraphs': paragraphs,
        'footnotes': footnotes,
        'signatories': signatories,
    }
