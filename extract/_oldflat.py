"""Helpers for the old flat vatican.va dialect (GeS, SC).

Underscore-prefixed so `parse.py`'s module discovery doesn't offer it
as a document.
"""

from core import br_text, make_soup


def load_split(path):
    """Read an ISO-8859-1 old-flat page; split body from its NOTES block."""
    with open(path, encoding='iso-8859-1') as f:
        html = f.read()
    body, _, notes = html.partition('NOTES</b>')
    return body, notes


def front_matter_text(body_html, marker):
    """`br_text` of the front-matter `<p>` containing `marker`, or ''."""
    soup = make_soup(body_html)
    fm = next((p for p in soup.find_all('p')
               if marker in p.get_text()), None)
    return br_text(fm) if fm else ''
