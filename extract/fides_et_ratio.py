"""Extractor for *Fides et Ratio* — John Paul II's 1998 encyclical.

Modern Bootstrap page, but an older export than LS/LF with two quirks of
its own:

  - **Chapters** are single centred-bold lines joining the label and title
    with a dash: ``CHAPTER I - THE REVELATION OF GOD'S WISDOM``. The Roman
    numeral is split off as the chapter number; ``INTRODUCTION`` opens the
    chapter-0 group (labelled by the renderer) and ``CONCLUSION`` is a
    trailing unnumbered chapter. Unnumbered bold topical headers within a
    chapter become auto-numbered sections, as in *Magnifica Humanitas*.
  - **Footnotes** use neither LS's ``[N]`` nor the modern ``_ftn`` anchors.
    Body cites are ``<sup><a name="-N">N</a></sup>``; the definitions are a
    run of loose inline blocks after an ``<hr>``, each
    ``<font><b><a name="$N">N</a></b></font> text`` separated by ``<br><br>``
    (the ``$`` percent-encoded as ``%24`` in the anchor name). Body cites are
    rewritten to canonical ``(N)`` superscripts up front; the definitions are
    recovered by splitting the content markup on the definition anchors.
"""

import re

from bs4 import BeautifulSoup

from core import (
    HeadingState,
    assign_footnote_context,
    clean_text,
    heading_title,
    is_centred,
    is_promulgation,
    normalise_footnote_refs,
    normalise_footnote_text,
    numbered_paragraph,
    only_child_is,
    paragraph_record,
    roman_to_int,
)
from project import SOURCES

from ._modern import encyclical_front_matter, load_main


EN_SRC = SOURCES / 'fides_et_ratio_en.html'

NAME = 'Fides et Ratio'
HUE = 8
SOURCE_URL = ('https://www.vatican.va/content/john-paul-ii/en/encyclicals/'
              'documents/hf_jp-ii_enc_14091998_fides-et-ratio.html')
AUTHOR = 'John Paul II'
DATE = '1998-09-14'
IDENTIFIER = 'papal:fides-et-ratio:1998-09-14'

TITLE_UPPER = 'FIDES ET RATIO'

RE_PARA = re.compile(r'^(\d+)\s*\.\s+(.+)$', re.DOTALL)
RE_CHAPTER = re.compile(r'^CHAPTER\s+([IVXLC]+)\b\s*[-–—]\s*(.+)$', re.DOTALL)

# Body footnote cites: <a name="-X">N</a> inside a <sup>, where the visible
# number N is the anchor text and the name suffix X is the source's own
# base-36-ish label (`-A` = note 10, `-1A` = note 46), *not* the number.
RE_BODY_REF_ANCHOR = re.compile(r'^-[0-9A-Za-z]+$')
# Footnote definitions: <font…><b><a name="%24…">N</a></b></font> opens each.
RE_DEF = re.compile(
    r'<font[^>]*>\s*<b>\s*<a\b[^>]*\bname="%24[^"]*"[^>]*>\s*(\d+)\s*</a>'
    r'\s*</b>\s*</font>',
    re.IGNORECASE | re.DOTALL,
)


def _canonicalise_body_refs(soup):
    """Rewrite ``<sup><a name="-N">N</a></sup>`` cites to ``<sup>(N)</sup>``.

    Replacing only the anchor leaves the enclosing ``<sup>`` in place, which
    ``normalise_footnote_refs`` then collapses to a bare ``(N)`` — the same
    path the canonical superscript references already take.
    """
    for anchor in soup.find_all('a', attrs={'name': RE_BODY_REF_ANCHOR}):
        anchor.replace_with(f'({anchor.get_text().strip()})')


def _footnotes(soup):
    """Recover the loose inline footnote definitions after the body.

    Definitions are not wrapped in ``<p>`` tags, so we work on the markup of
    the div that holds them and split on the definition-anchor boundaries —
    the same tactic ``_curia.anchored_footnotes`` uses for Word exports.
    """
    first = soup.find('a', attrs={'name': re.compile(r'^%24')})
    if first is None:
        raise ValueError(
            f'{EN_SRC.name}: no footnote definition anchor (name="$N") found — '
            'source structure has changed or the snapshot is not this dialect'
        )
    markup = str(first.find_parent('div'))
    defs = list(RE_DEF.finditer(markup))
    notes = []
    for index, match in enumerate(defs):
        end = defs[index + 1].start() if index + 1 < len(defs) else len(markup)
        body = BeautifulSoup(
            '<p>' + markup[match.end():end] + '</p>', 'html.parser'
        ).p
        text = normalise_footnote_text(
            normalise_footnote_refs(clean_text(body, preserve_formatting=True))
        )
        notes.append({
            'part': 0, 'chapter': 0, 'number': int(match.group(1)), 'text': text,
        })
    return notes


def extract():
    soup, main = load_main(EN_SRC, drop_chrome=True)
    _canonicalise_body_refs(soup)
    ps = main.find_all('p')

    desc_pre, desc_post = encyclical_front_matter(ps[0] if ps else None,
                                                  TITLE_UPPER)

    paragraphs = []
    promulgation = ''
    signature = ''

    state = HeadingState()
    seen_numbered = False
    last_chapter = 0

    for p in ps[1:]:
        text = clean_text(p)
        if not text:
            continue

        if is_centred(p):
            chapter = RE_CHAPTER.match(text)
            if chapter:
                last_chapter = roman_to_int(chapter.group(1))
                # Leave the preface regions: chapters carry no part_title.
                state.part_title = ''
                state.set_chapter(last_chapter, heading_title(chapter.group(2)))
                continue
            if text.upper().startswith('CONCLUSION'):
                last_chapter += 1
                state.part_title = ''
                state.set_chapter(last_chapter, 'Conclusion')
                continue
            # Two preface headings open the document: the apostolic "Blessing"
            # over the greeting and the "two wings" epigraph, then the
            # "Introduction". Both are kept as authored part-0 titles so they
            # render as real headings on every surface (not the generated
            # Preamble, which is only for openings the source leaves untitled).
            if text.upper().startswith('INTRODUCTION'):
                # The source heading is 'INTRODUCTION - "KNOW YOURSELF"'; the
                # Delphic maxim is a decorative subtitle, so the navigable
                # heading is just "Introduction".
                state.part_title = 'Introduction'
                continue
            if text == 'Blessing':
                state.part_title = 'Blessing'
                continue
            # The papal signature is the centred trailer after the promulgation.
            if promulgation and not signature:
                signature = clean_text(p, preserve_formatting=True)
            continue

        # unnumbered bold topical header → auto-numbered section
        # (`<b>…</b>` or `<b><i>…</i></b>`; the sole child is the <b> either way)
        if only_child_is(p, 'b'):
            state.set_section(state.section + 1, heading_title(text))
            continue

        numbered = numbered_paragraph(p, RE_PARA)
        if numbered:
            seen_numbered = True
            paragraphs.append(paragraph_record(
                *numbered, bracketed_refs=True, **state.kwargs(),
            ))
            continue

        if is_promulgation(text):
            promulgation = clean_text(p, preserve_formatting=True)
            continue

        # Prefatory prose before the first numbered paragraph (the apostolic
        # blessing and the "Faith and reason are like two wings" epigraph)
        # carries no number; keep it as hidden-number intro paragraphs.
        if not seen_numbered:
            paragraphs.append(paragraph_record(
                len(paragraphs) + 1,
                clean_text(p, preserve_formatting=True),
                bracketed_refs=True, **state.kwargs(),
            ))
            paragraphs[-1]['hide_number'] = True
            continue

        # unnumbered continuation prose following a numbered paragraph
        if paragraphs:
            paragraphs[-1]['text'] += '\n\n' + normalise_footnote_refs(
                clean_text(p, preserve_formatting=True)
            )

    footnotes = assign_footnote_context(_footnotes(soup), paragraphs)

    return {
        'name': NAME,
        'hue': HUE,
        'source_url': SOURCE_URL,
        'author': AUTHOR,
        'issued_by': 'John Paul II',
        'pontificate': 'John Paul II',
        'date': DATE,
        'identifier': IDENTIFIER,
        # The pope is already named in `desc` ("ENCYCLICAL LETTER … OF THE
        # SUPREME PONTIFF JOHN PAUL II"), so the title-page foot stays bare.
        'show_title_author': False,
        'desc': desc_pre,
        'desc_post': desc_post,
        'promulgation': promulgation,
        'signature': signature,
        'paragraphs': paragraphs,
        'footnotes': footnotes,
    }
