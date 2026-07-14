"""Extractor for *Fratelli Tutti* — the modern Bootstrap Vatican.va template.

LS-shaped (two-phase body/tail split for the same reason: titled prayer
appendices interleave before the footnote definitions), with two drifts:

  - **Chapter titles are centred but not bold.** LS's `has_b` discriminator
    doesn't apply; a centred line while a `CHAPTER N` marker is pending is
    the title (`DARK CLOUDS OVER A CLOSED WORLD`), all-caps plain text.
  - **No Roman section tier.** Empty named anchors followed by all-caps text
    (`SHATTERED DREAMS`) become auto-numbered bare sections (the LF/MH idiom).
    The 45 italic-only topical headers form the finer sub-heading tier.

Body cites are `<a name="_ftnrefN" href="#_ftnN">[N]</a>`; definitions carry
both `name="_ftnN"` and a backref href. `clean_text` unwraps the `#_ftn`
hrefs so the canonical `[N]` → `(N)` pass sees plain markers.

The tail holds two titled prayers (centred italic title + `<br/>` verse
paragraphs), an italic "Given in Assisi…" promulgation, and a centred
*non-bold* `Franciscus` — caught by `_modern.is_signature_trailer`, not
LS's bold-trailer branch.
"""

import re

from core import (
    HeadingState,
    assign_footnote_context,
    clean_text,
    is_centred,
    is_promulgation,
    normalise_footnote_refs,
    numbered_paragraph,
    only_child_is,
    paragraph_record,
    parse_footnote,
    title_case,
)
from project import SOURCES

from ._modern import (
    chapter_word_marker,
    encyclical_front_matter,
    is_signature_trailer,
    load_main,
)


EN_SRC = SOURCES / 'Fratelli tutti_en.html'

NAME = 'Fratelli Tutti'
HUE = 75
SOURCE_URL = ('https://www.vatican.va/content/francesco/en/encyclicals/documents/'
              'papa-francesco_20201003_enciclica-fratelli-tutti.html')
AUTHOR = 'Francis'
DATE = '2020-10-03'
IDENTIFIER = 'papal:fratelli-tutti:2020-10-03'

TITLE_UPPER = 'FRATELLI TUTTI'

RE_PARA     = re.compile(r'^(\d+)\s*\.\s+(.+)$', re.DOTALL)
# `\s*` after the closing bracket, not `\s+`: note 98's marker is glued to
# its text (`[98]Encyclical`).
RE_FOOTNOTE = re.compile(r'^\[\s*(\d+)\s*\]\s*(.+)$', re.DOTALL)

# Notes 86, 112, and 185 lose their opening bracket in the source (an empty
# definition anchor eats it): `86] Encyclical…`. Restore it so RE_FOOTNOTE
# sees a canonical marker.
RE_BROKEN_MARKER = re.compile(r'^(\d{1,3})\]')

# The Good Samaritan pericope (§56) and the eight scripture excerpts under
# §61 are fully italic source paragraphs with parenthesised citations.
# Canonicalise each as a semantic Markdown blockquote, with a citation footer.
RE_SCRIPTURE_BLOCK = re.compile(
    r'^\*“(.+)”\*\s*\((.+)\)\.$', re.DOTALL
)
RE_APPEAL_CLOSE = re.compile(r'”(?=\.\(285\)$)')


def split_glued_definitions(rich):
    """Yield each definition when a source <p> glues two together.

    Note 119's definition rides in note 118's paragraph. The guard is
    tight: only a whitespace-delimited `[N+1]` marker — the exact successor
    of the note just parsed — splits, so bracketed numbers in citation text
    cannot."""
    m = RE_FOOTNOTE.match(rich)
    if not m:
        yield rich
        return
    n = int(m.group(1))
    while True:
        nxt = re.search(rf'\s\[{n + 1}\]\s', rich)
        if not nxt:
            yield rich
            return
        yield rich[:nxt.start()]
        rich = rich[nxt.start() + 1:]
        n += 1


def extract():
    soup, main = load_main(EN_SRC, drop_chrome=True)
    ps = main.find_all('p')

    fm_p = next((p for p in ps if 'ENCYCLICAL LETTER' in p.get_text()), None)
    desc_pre, desc_post = encyclical_front_matter(fm_p, TITLE_UPPER)

    # Cap body accumulation at the last numbered paragraph (§287); the
    # prayers, promulgation, and signature stream in after it.
    last_body_idx = max(
        (i for i, p in enumerate(ps) if RE_PARA.match(clean_text(p))),
        default=-1,
    )

    paragraphs = []
    footnotes = []
    appendices = []
    promulgation = ''
    signature = ''

    # ─── Phase 1: body walk (idx 0 .. last_body_idx) ─────────────────────
    state = HeadingState()
    pending_chapter_num = None

    for i in range(last_body_idx + 1):
        p = ps[i]
        text = clean_text(p)
        if not text or p is fm_p:
            continue

        # Chapter marker, then its centred (non-bold) all-caps title.
        if is_centred(p):
            chapter_num = chapter_word_marker(text)
            if chapter_num is not None:
                pending_chapter_num = chapter_num
                continue
            if pending_chapter_num is not None:
                state.set_chapter(pending_chapter_num, title_case(text))
                pending_chapter_num = None
            continue

        # Primary division: an empty named anchor followed by all-caps text
        # in an otherwise plain paragraph. Without this branch the
        # continuation fallback glues headings such as `SHATTERED DREAMS`
        # onto the preceding numbered paragraph.
        named_anchor = p.find('a', attrs={'name': True}, recursive=False)
        if named_anchor and not named_anchor.get_text(strip=True) \
                and text.isupper():
            state.add_section(title_case(text))
            continue

        # Italic-only topical header → finer sub-heading within the open
        # all-caps division.
        if only_child_is(p, 'i'):
            state.sub_heading = text
            continue

        numbered = numbered_paragraph(p, RE_PARA)
        if numbered:
            paragraphs.append(paragraph_record(
                *numbered, bracketed_refs=True, **state.kwargs(),
            ))
            continue

        # Unnumbered continuation prose under the open paragraph.
        if paragraphs and not p.find('b'):
            continuation = normalise_footnote_refs(
                clean_text(p, preserve_formatting=True), bracketed=True
            )
            scripture = RE_SCRIPTURE_BLOCK.match(continuation)
            if scripture:
                citation = re.sub(r'(?<=\d)-(?=\d)', '–', scripture.group(2))
                continuation = (
                    f'> {scripture.group(1)}\n>\n> — {citation}'
                )
            elif (paragraphs[-1]['number'] == 285
                  and continuation.startswith('“In the name')):
                appeal_line = RE_APPEAL_CLOSE.sub('', continuation[1:])
                separator = (
                    '\n>\n> ' if '\n\n> ' in paragraphs[-1]['text']
                    else '\n\n> '
                )
                paragraphs[-1]['text'] += separator + appeal_line
                continue
            paragraphs[-1]['text'] += '\n\n' + continuation

    # ─── Phase 2: tail walk (prayers → promulgation → signature → notes) ─
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

        rich = RE_BROKEN_MARKER.sub(
            r'[\1]', clean_text(p, preserve_formatting=True), count=1)
        pieces = [
            parse_footnote(piece, RE_FOOTNOTE, bracketed_refs=True)
            for piece in split_glued_definitions(rich)
        ]
        if all(pieces) and pieces:
            _flush()
            footnotes.extend(pieces)
            continue

        # Italic-only block: a prayer title or the promulgation.
        if only_child_is(p, 'i'):
            _flush()
            if is_promulgation(text):
                promulgation = clean_text(p, preserve_formatting=True)
                continue
            current = {'title': text, 'kind': 'prayer', 'text': ''}
            continue

        # Centred name line after the promulgation ("Franciscus", not bold).
        if is_signature_trailer(p, promulgation, signature):
            signature = clean_text(p, preserve_formatting=True)
            continue

        # Verse body of the open prayer.
        if current is not None:
            if current['text']:
                current['text'] += '\n\n'
            current['text'] += normalise_footnote_refs(
                clean_text(p, preserve_formatting=True), bracketed=True
            )

    _flush()

    footnotes = assign_footnote_context(footnotes, paragraphs)

    return {
        'name': NAME,
        'hue': HUE,
        'source_url': SOURCE_URL,
        'author': AUTHOR,
        'issued_by': 'Francis',
        'pontificate': 'Francis',
        'date': DATE,
        'identifier': IDENTIFIER,
        'type': 'encyclical',
        'subtitle': 'on Fraternity and Social Friendship',
        # The pope is already named in `desc`, so the title-page foot stays
        # bare (the LS precedent).
        'show_title_author': False,
        'desc': desc_pre,
        'desc_post': desc_post,
        'promulgation': promulgation,
        'signature': signature,
        'layout': {'long': True, 'bare_sections': True, 'mobile_inline': True, 'section_indicator': True},
        'paragraphs': paragraphs,
        'footnotes': footnotes,
        'appendices': appendices,
    }
