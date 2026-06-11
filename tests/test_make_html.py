"""Golden-output test for the web renderer.

`make_html.py` is a CLI script that renders at import time, so it is
exercised end-to-end: write a small synthetic TOML into `build/`, run the
script, and assert on the emitted HTML. This covers escaping, inline
markup, footnote-ref linking, external-link safety, stable IDs, and the
JS placeholder substitution.
"""

import subprocess
import sys
import unittest

from core import write_toml
from project import BUILD, ROOT, SITE

SLUG = 'audit_fixture'

PARAGRAPHS = [{
    'number': 1,
    'text': (
        'A paragraph with *emphasis*, **bold**, the 19<sup>th</sup> '
        'century, an A & B ampersand, a footnote ref (1), '
        '[a good link](https://example.test/x) and '
        '[a bad link](javascript:alert1).'
    ),
}]

FOOTNOTES = [{'number': 1, 'text': 'A note citing *Gaudium et spes*.'}]


class MakeHtmlGoldenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        BUILD.mkdir(exist_ok=True)
        cls.toml_path = BUILD / f'{SLUG}.toml'
        cls.html_path = SITE / f'{SLUG}.html'
        write_toml(
            cls.toml_path, name='Fixture & Co', hue=42,
            paragraphs=PARAGRAPHS, footnotes=FOOTNOTES,
        )
        result = subprocess.run(
            [sys.executable, 'make_html.py', SLUG],
            cwd=ROOT, capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f'make_html.py failed:\n{result.stderr}')
        cls.html = cls.html_path.read_text()

    @classmethod
    def tearDownClass(cls):
        cls.toml_path.unlink(missing_ok=True)
        cls.html_path.unlink(missing_ok=True)

    def test_inline_markup_renders_as_html(self):
        self.assertIn('<em>emphasis</em>', self.html)
        self.assertIn('<strong>bold</strong>', self.html)
        self.assertIn('19<sup>th</sup>', self.html)

    def test_document_text_is_escaped(self):
        self.assertIn('A &amp; B ampersand', self.html)
        self.assertIn('Fixture &amp; Co', self.html)

    def test_footnote_ref_links_to_drawer_note(self):
        self.assertIn('<sup><a href="#fn-0-0-1">1</a></sup>', self.html)
        self.assertIn('id="fn-0-0-1"', self.html)
        self.assertIn('<em>Gaudium et spes</em>', self.html)

    def test_http_links_are_linkified_and_other_schemes_are_not(self):
        self.assertIn('href="https://example.test/x"', self.html)
        self.assertIn('a good link</a>', self.html)
        self.assertNotIn('javascript:', self.html)
        self.assertIn('a bad link', self.html)

    def test_paragraph_id_is_stable(self):
        self.assertIn('id="para-1"', self.html)

    def test_js_placeholders_are_substituted(self):
        self.assertNotIn('__INDICATOR_JSON__', self.html)
        self.assertNotIn('__DOC_NAME__', self.html)
        self.assertIn('"Fixture & Co"', self.html)


if __name__ == '__main__':
    unittest.main()
