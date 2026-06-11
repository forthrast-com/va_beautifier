"""Tests for the per-dialect helper modules under extract/."""

import tempfile
import unittest
from pathlib import Path

from bs4 import BeautifulSoup

import parse
from extract._modern import (
    chapter_word_marker,
    encyclical_front_matter,
    load_main,
)
from extract._oldflat import front_matter_text, load_split


class DiscoveryTests(unittest.TestCase):
    def test_dialect_helpers_are_not_offered_as_documents(self):
        available = parse._available()

        self.assertNotIn('_curia', available)
        self.assertNotIn('_modern', available)
        self.assertNotIn('_oldflat', available)
        self.assertIn('laudato_si', available)
        self.assertIn('gaudium_et_spes', available)


class ModernDialectTests(unittest.TestCase):
    def test_load_main_prefers_main_and_drops_chrome(self):
        html = ('<html><body><script>x()</script>'
                '<main><p>Body</p><figure>art</figure></main></body></html>')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'doc.html'
            path.write_text(html, encoding='utf-8')
            _, main = load_main(path, drop_chrome=True)

        self.assertEqual(main.name, 'main')
        self.assertIsNone(main.find('figure'))
        self.assertEqual(main.p.get_text(), 'Body')

    def test_chapter_word_marker(self):
        self.assertEqual(chapter_word_marker('CHAPTER THREE'), 3)
        self.assertIsNone(chapter_word_marker('CHAPTER XIV'))
        self.assertIsNone(chapter_word_marker('Chapter Three'))

    def test_encyclical_front_matter_splits_and_pivots(self):
        soup = BeautifulSoup(
            '<p>ENCYCLICAL LETTER<br>OF THE HOLY FATHER<br>'
            'LAUDATO SI’<br>ON CARE FOR OUR COMMON HOME</p>',
            'html.parser',
        )

        desc, desc_post = encyclical_front_matter(soup.p, 'LAUDATO SI')

        self.assertEqual(desc, 'ENCYCLICAL LETTER\nOF THE HOLY FATHER')
        self.assertEqual(desc_post, 'ON CARE FOR OUR COMMON HOME')

    def test_missing_front_matter_yields_empty_halves(self):
        self.assertEqual(encyclical_front_matter(None, 'X'), ('', ''))


class OldFlatDialectTests(unittest.TestCase):
    def test_load_split_partitions_at_notes_marker(self):
        html = '<p>Corps caf\xe9</p><b>NOTES</b><p>1. A note</p>'
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'doc.html'
            path.write_bytes(html.encode('iso-8859-1'))
            body, notes = load_split(path)

        self.assertIn('café', body)
        self.assertNotIn('A note', body)
        self.assertIn('A note', notes)

    def test_load_split_without_notes_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'doc.html'
            path.write_text('<p>Body only</p>', encoding='iso-8859-1')
            body, notes = load_split(path)

        self.assertIn('Body only', body)
        self.assertEqual(notes, '')

    def test_front_matter_text_finds_marker_paragraph(self):
        body = ('<p>[EN - FR]</p>'
                '<p>PASTORAL CONSTITUTION<br>GAUDIUM ET SPES</p>'
                '<p>1. Body</p>')

        self.assertEqual(
            front_matter_text(body, 'PASTORAL CONSTITUTION'),
            'PASTORAL CONSTITUTION\nGAUDIUM ET SPES',
        )
        self.assertEqual(front_matter_text(body, 'NOT PRESENT'), '')


if __name__ == '__main__':
    unittest.main()
