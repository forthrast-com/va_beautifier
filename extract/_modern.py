"""Helpers for the modern Bootstrap vatican.va dialect (LS, MH).

Underscore-prefixed so `parse.py`'s module discovery doesn't offer it
as a document.
"""

import re

from core import (
    br_lines,
    chapter_word_to_int,
    encyclical_split,
    is_centred,
    make_soup,
    repair,
    split_around_title,
)


# Non-content chrome that confuses tag walks when left in the tree.
CHROME = ['script', 'style', 'meta', 'link', 'img', 'header',
          'footer', 'nav', 'svg', 'input', 'button', 'figure']

RE_CHAPTER_WORD = re.compile(r'^CHAPTER\s+([A-Z]+)$')

# Footnote reference and definition anchors. The body cite carries
# `name="_ftnref{N}"`; the tail definition carries `name="_ftn{N}"`; both
# wrap the visible `[N]` marker. Word's *endnote* export (Caritas in
# Veritate) spells the same scheme `_edn{N}` / `_ednref{N}`.
RE_FOOTNOTE_ANCHOR = re.compile(r'^_(ftn|edn)(ref)?\d+$')


def load_main(path, *, drop_chrome=False, repairs=()):
    """Parse a UTF-8 modern page; return `(soup, main-or-body)`.

    `repairs` is a sequence of `(old, new)` markup fixes applied before
    parsing, for defects that are easier to state as raw markup than to
    unpick from the tree. Each goes through `core.repair`, so a snapshot
    that no longer contains the defect fails loudly rather than silently
    skipping the fix.
    """
    with open(path, encoding='utf-8') as f:
        raw = f.read()
    for old, new in repairs:
        raw = repair(raw, old, new, what=path.name)
    soup = make_soup(raw)
    if drop_chrome:
        for tag in soup(CHROME):
            tag.decompose()
    return soup, (soup.find('main') or soup.body)


def chapter_word_marker(text):
    """The chapter number for a `CHAPTER ONE` delimiter line, else None."""
    match = RE_CHAPTER_WORD.match(text)
    return chapter_word_to_int(match.group(1)) if match else None


def is_signature_trailer(tag, promulgation, signature):
    """True for the centred papal signature that trails the promulgation.

    The modern encyclicals close with `Given in …` (the promulgation) then a
    centred name line (`FRANCISCUS`, `JOHN PAUL II`). Capture the first such
    centred line once the promulgation has been seen and none taken yet.
    """
    return bool(promulgation) and not signature and is_centred(tag)


def strip_footnote_anchors(soup):
    """Unwrap footnote ref/def anchors to the bare `[N]` text they contain.

    `clean_text` only short-circuits footnote anchors whose `href` is a
    relative `#_ftn…` (the fragment-only form Verbum Domini uses). Lumen
    Fidei instead gives every footnote anchor an *absolute* cross-document
    href, so the generic `[text](href)` linkifier would wrap the `[N]`
    marker in a Markdown link. Replacing these anchors with their text up
    front lets the canonical `[N]` → `(N)` normalisation run on every modern
    page regardless of how the source spelt the href. Cross-references to
    *other* documents (no `_ftn` name) keep their anchors and stay linkable.
    """
    for anchor in soup.find_all('a', attrs={'name': RE_FOOTNOTE_ANCHOR}):
        anchor.replace_with(anchor.get_text())


def encyclical_front_matter(fm, title_upper):
    """Split a modern front-matter block into `(desc, desc_post)`.

    `fm` is the tag whose `<br>`-separated lines sandwich the all-caps
    title (or None when the locator found nothing); the halves are then
    pivoted at the `On …` subject line so the issuer sits above the
    title and the subject below it.
    """
    if fm is None:
        return '', ''
    pre, post = split_around_title(br_lines(fm), title_upper)
    return encyclical_split('\n'.join(pre), '\n'.join(post))
