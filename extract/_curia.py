"""Helpers for the Curia Word-export dialect (AeN, QVH).

Underscore-prefixed so `parse.py`'s module discovery doesn't offer it
as a document.
"""

import re

from core import (
    assign_footnote_context,
    clean_text,
    flatten_ws,
    make_soup,
    normalise_footnote_refs,
    normalise_footnote_text,
    notes_between_anchors,
)


NOTE_ANCHOR = re.compile(
    r'<a\b(?=[^>]*\bname=["\']_ftn(\d+)["\'])[^>]*>.*?</a>',
    re.IGNORECASE | re.DOTALL,
)


def load_source(path):
    with path.open(encoding='utf-8') as source:
        return make_soup(source.read())


def text(tag):
    return flatten_ws(clean_text(tag))


def rich_text(tag):
    return clean_text(tag, preserve_formatting=True)


def prose_text(tag):
    """Return formatted Curia prose without Word-export line wrapping."""
    return flatten_ws(rich_text(tag))


def anchored_footnotes(soup, paragraphs):
    """Extract Word-export footnotes between named anchors.

    Some Curia pages make each note a paragraph; others leave note 1 bare
    inside an enclosing div. Splitting at `_ftnN` anchors handles both forms.
    """
    def text_of(slice_markup):
        holder = make_soup('<div>' + slice_markup + '</div>').div
        return normalise_footnote_text(
            normalise_footnote_refs(prose_text(holder), bracketed=True)
        )

    notes = notes_between_anchors(soup.decode(), NOTE_ANCHOR, text_of=text_of)
    return assign_footnote_context(notes, paragraphs)
