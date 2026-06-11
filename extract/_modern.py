"""Helpers for the modern Bootstrap vatican.va dialect (LS, MH).

Underscore-prefixed so `parse.py`'s module discovery doesn't offer it
as a document.
"""

import re

from bs4 import BeautifulSoup

from core import br_lines, chapter_word_to_int, encyclical_split, split_around_title


# Non-content chrome that confuses tag walks when left in the tree.
CHROME = ['script', 'style', 'meta', 'link', 'img', 'header',
          'footer', 'nav', 'svg', 'input', 'button', 'figure']

RE_CHAPTER_WORD = re.compile(r'^CHAPTER\s+([A-Z]+)$')


def load_main(path, *, drop_chrome=False):
    """Parse a UTF-8 modern page; return `(soup, main-or-body)`."""
    with open(path, encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')
    if drop_chrome:
        for tag in soup(CHROME):
            tag.decompose()
    return soup, (soup.find('main') or soup.body)


def chapter_word_marker(text):
    """The chapter number for a `CHAPTER ONE` delimiter line, else None."""
    match = RE_CHAPTER_WORD.match(text)
    return chapter_word_to_int(match.group(1)) if match else None


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
