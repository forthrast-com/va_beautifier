"""Extractor for *Ecclesia in Oceania* — John Paul II's 2001 post-synodal
apostolic exhortation.

Modern Bootstrap page, but an older (2001) export with its own footnote
dialect:

  - **Footnote refs** are neither LS's ``[N]`` nor the ``_ftn`` anchors.
    Each body cite is ``<sup><a name="fnref{N}">(</a><a href="#fn{N}">N</a>)</sup>``
    — the parentheses are literal source text and the marker is split across
    two anchors (one carries the back-reference ``name``, the other the
    ``href``). Both halves are unwrapped to their text so the cite collapses
    to a canonical ``(N)`` superscript, which the usual normalisation reduces
    to a bare ``(N)``.
  - **Definitions** live in a trailing ``NOTES`` block (not a tail of ``[N]``
    paragraphs), each ``<p>`` opening ``(N) text`` after the same anchor
    unwrap.

Structure: ``INTRODUCTION`` opens the part-0 group; Roman ``CHAPTER I`` …
``CHAPTER IV`` markers (centred, *not* bold) precede a centred-bold chapter
title; unnumbered all-bold topical headers become auto-numbered bare
sections; ``CONCLUSION`` is an unnumbered trailing chapter. The Roman
chapter numerals are parsed to arabic (as in FeR) so the conclusion keeps
the unnumbered path rather than being forced a numeral.
"""

import re

from core import (
    HeadingState,
    assign_footnote_context,
    canonical_blockquote,
    clean_text,
    heading_title,
    is_centred,
    is_promulgation,
    normalise_footnote_refs,
    numbered_paragraph,
    only_child_is,
    paragraph_record,
    parse_footnote,
    roman_to_int,
    title_case,
)
from project import SOURCES

from ._modern import (
    encyclical_front_matter,
    is_signature_trailer,
    load_main,
)


EN_SRC = SOURCES / 'ecclesia_in_oceania_en.html'

NAME = 'Ecclesia in Oceania'
HUE = 212
SOURCE_URL = ('https://www.vatican.va/content/john-paul-ii/en/apost_exhortations/'
              'documents/hf_jp-ii_exh_20011122_ecclesia-in-oceania.html')
AUTHOR = 'John Paul II'
DATE = '2001-11-22'
IDENTIFIER = 'papal:ecclesia-in-oceania:2001-11-22'

TITLE_UPPER = 'ECCLESIA IN OCEANIA'

RE_PARA = re.compile(r'^(\d+)\s*\.\s+(.+)$', re.DOTALL)
RE_CHAPTER = re.compile(r'^CHAPTER\s+([IVXLC]+)$')
# Footnote anchors: body cite `name="fnref{N}"`, definition `name="fn{N}"`;
# the matching half of each marker carries an `href="#fn…"` instead.
RE_FN_NAME = re.compile(r'^fn(ref)?\d+$')
RE_FN_HREF = re.compile(r'^#fn(ref)?\d+$')
# Definition lines after the `NOTES` heading open with a parenthesised number.
RE_NOTE = re.compile(r'^\((\d+)\)\s*(.+)$', re.DOTALL)
RE_SCRIPTURE = re.compile(
    r'^\*"(?P<body>.+)"\*\s+\((?P<citation>[^)]+)\)\.?$',
    re.DOTALL,
)


def _canonicalise_scripture(text):
    match = RE_SCRIPTURE.fullmatch(text.strip())
    if not match:
        return text
    citation = re.sub(r'(?<=\d)-(?=\d)', '–', match.group('citation'))
    return canonical_blockquote(match.group('body'), citation)


def _is_fn_anchor(anchor):
    return bool(
        RE_FN_NAME.match(anchor.get('name') or '')
        or RE_FN_HREF.match(anchor.get('href') or '')
    )


def _unwrap_fn_anchors(soup):
    """Replace the split footnote anchors with their literal text.

    Both the `name`-bearing and the `href`-bearing half of each marker are
    unwrapped, leaving the source's own parentheses (`<sup>(N)</sup>` in the
    body) for the canonical normalisation to finish.
    """
    for anchor in soup.find_all('a'):
        if _is_fn_anchor(anchor):
            anchor.replace_with(anchor.get_text())


def _extract_notes(note_ps):
    """Parse the `NOTES` block into footnote records.

    The marker anchor locates each note, but the visible ``(N)`` is brittle:
    the source occasionally opens an ``<i>`` on the number and only closes it
    a word later (note 21: ``<i>(21) Cf. Propositio </i>44.``), which would
    fuse the number to a stray emphasis run and make ``RE_NOTE`` miss it.
    Formatting wrapped around the marker is lifted first, then both halves of
    the marker are unwrapped, leaving a clean ``(N) …`` for ``RE_NOTE``.
    """
    notes = []
    for p in note_ps:
        marker = p.find('a', attrs={'name': RE_FN_NAME})
        if marker is None:
            continue
        for fmt in marker.find_parents(['i', 'b']):
            fmt.unwrap()
        for anchor in p.find_all('a'):
            if _is_fn_anchor(anchor):
                anchor.replace_with(anchor.get_text())
        note = parse_footnote(
            clean_text(p, preserve_formatting=True), RE_NOTE
        )
        if note:
            notes.append(note)
    return notes


def extract():
    soup, main = load_main(EN_SRC, drop_chrome=True)
    ps = main.find_all('p')

    fm_p = ps[0] if ps else None
    subtitle_p = ps[1] if len(ps) > 1 else None
    desc_pre, desc_post = encyclical_front_matter(fm_p, TITLE_UPPER)

    notes_idx = next(
        (i for i, p in enumerate(ps) if clean_text(p) == 'NOTES'), None
    )
    if notes_idx is None:
        raise ValueError(
            f'{EN_SRC.name}: no centred "NOTES" heading found — '
            'cannot locate the end of the body text'
        )

    # Parse the notes before stripping the body anchors (the per-note
    # emphasis-lift needs the marker tags intact), then unwrap the body cites.
    raw_notes = _extract_notes(ps[notes_idx + 1:])
    _unwrap_fn_anchors(soup)

    paragraphs = []
    appendices = []
    promulgation = ''
    signature = ''

    state = HeadingState()
    pending_chapter_num = None
    prayer = None  # the closing "Prayer" appendix, once its heading is seen

    for p in ps[:notes_idx]:
        if p is fm_p or p is subtitle_p:
            continue
        text = clean_text(p)
        if not text:
            continue

        if is_centred(p):
            if is_signature_trailer(p, promulgation, signature):
                signature = clean_text(p, preserve_formatting=True)
                continue
            chapter = RE_CHAPTER.match(text)
            if chapter:
                pending_chapter_num = roman_to_int(chapter.group(1))
                continue
            if text == 'INTRODUCTION':
                state.set_part(0, 'Introduction')
                continue
            if text.upper().startswith('CONCLUSION'):
                state.part_title = ''
                state.set_chapter(state.chapter + 1, 'Conclusion')
                continue
            if pending_chapter_num is not None:
                # Leave the part-0 "Introduction" label behind once chapters
                # begin, so it doesn't bleed onto every chapter paragraph.
                state.part_title = ''
                state.set_chapter(pending_chapter_num, title_case(text))
                pending_chapter_num = None
            continue

        # unnumbered all-bold topical header → auto-numbered section
        if _is_all_bold(p):
            state.add_section(heading_title(text))
            continue

        # Italic-only header → finer sub-heading tier (e.g. "The Permanent
        # Diaconate"), except the closing "Prayer" which titles the trailing
        # prayer block and is lifted into its own appendix region. The
        # promulgation dateline is also a lone italic <p>; let it fall through
        # to its own branch rather than be mistaken for a heading.
        if only_child_is(p, 'i') and not is_promulgation(text):
            if text == 'Prayer':
                prayer = {'title': 'Prayer', 'kind': 'prayer', 'text': ''}
                appendices.append(prayer)
            else:
                state.sub_heading = heading_title(text)
            continue

        numbered = numbered_paragraph(p, RE_PARA)
        if numbered:
            paragraphs.append(paragraph_record(
                *numbered, bracketed_refs=True, **state.kwargs(),
            ))
            continue

        if is_promulgation(text):
            promulgation = clean_text(p, preserve_formatting=True)
            continue

        rich = normalise_footnote_refs(
            clean_text(p, preserve_formatting=True), bracketed=True
        )
        rich = _canonicalise_scripture(rich)
        # Once the "Prayer" heading is open, its verse forms the appendix body
        # rather than folding back into the conclusion's last paragraph.
        if prayer is not None:
            prayer['text'] = f"{prayer['text']}\n\n{rich}".strip()
            continue

        # unnumbered continuation prose following a numbered paragraph
        if paragraphs:
            paragraphs[-1]['text'] += '\n\n' + rich

    footnotes = assign_footnote_context(raw_notes, paragraphs)

    return {
        'name': NAME,
        'hue': HUE,
        'source_url': SOURCE_URL,
        'author': AUTHOR,
        'issued_by': 'John Paul II',
        'pontificate': 'John Paul II',
        'date': DATE,
        'identifier': IDENTIFIER,
        'type': 'apostolic_exhortation',
        'subtitle': ('on Jesus Christ and the Peoples of Oceania: '
                     'Walking His Way, Telling His Truth, Living His Life'),
        # The pope is already named in `desc` ("POST-SYNODAL APOSTOLIC
        # EXHORTATION … OF HIS HOLINESS POPE JOHN PAUL II"), so the
        # title-page foot stays bare.
        'show_title_author': False,
        'desc': desc_pre,
        'desc_post': desc_post,
        'promulgation': promulgation,
        'signature': signature,
        'layout': {'long': True, 'bare_sections': True},
        'paragraphs': paragraphs,
        'footnotes': footnotes,
        'appendices': appendices,
    }


def _is_all_bold(p):
    """True when every visible character of `p` sits inside a `<b>`."""
    bolds = p.find_all('b')
    return bool(bolds) and p.get_text(strip=True) == ''.join(
        b.get_text(strip=True) for b in bolds
    )
