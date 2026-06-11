"""Helpers for the Curia Word-export dialect (AeN, QVH).

Underscore-prefixed so `parse.py`'s module discovery doesn't offer it
as a document.
"""

import re

from bs4 import BeautifulSoup

from core import (
    assign_footnote_context,
    clean_text,
    normalise_footnote_refs,
    normalise_footnote_text,
)


NOTE_ANCHOR = re.compile(
    r'<a\b(?=[^>]*\bname=["\']_ftn(\d+)["\'])[^>]*>.*?</a>',
    re.IGNORECASE | re.DOTALL,
)


def load_source(path):
    with path.open(encoding='utf-8') as source:
        return BeautifulSoup(source.read(), 'html.parser')


def text(tag):
    return re.sub(r'\s+', ' ', clean_text(tag)).strip()


def rich_text(tag):
    return clean_text(tag, preserve_formatting=True)


def prose_text(tag):
    """Return formatted Curia prose without Word-export line wrapping."""
    return re.sub(r'\s+', ' ', rich_text(tag)).strip()


def anchored_footnotes(soup, paragraphs):
    """Extract Word-export footnotes between named anchors.

    Some Curia pages make each note a paragraph; others leave note 1 bare
    inside an enclosing div. Splitting at `_ftnN` anchors handles both forms.
    """
    markup = soup.decode()
    anchors = list(NOTE_ANCHOR.finditer(markup))
    notes = []
    for index, anchor in enumerate(anchors):
        end = anchors[index + 1].start() if index + 1 < len(anchors) else len(markup)
        holder = BeautifulSoup(
            '<div>' + markup[anchor.end():end] + '</div>', 'html.parser'
        ).div
        body = normalise_footnote_text(
            normalise_footnote_refs(prose_text(holder), bracketed=True)
        )
        notes.append({
            'part': 0,
            'chapter': 0,
            'number': int(anchor.group(1)),
            'text': body,
        })
    return assign_footnote_context(notes, paragraphs)
