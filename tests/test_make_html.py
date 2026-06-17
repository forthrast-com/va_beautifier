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
        '*cross\nline*, '
        '[a good link](https://example.test/x) and '
        '[a Vatican-relative link](/content/example.html) and '
        '[a bad link](javascript:alert1).'
    ),
}]

FOOTNOTES = [{'number': 1, 'text': 'A note citing *Gaudium et spes*.'}]


def render_html_fixture(slug, paragraphs, footnotes):
    BUILD.mkdir(exist_ok=True)
    toml_path = BUILD / f'{slug}.toml'
    html_path = SITE / f'{slug}.html'
    write_toml(
        toml_path, name='Fixture & Co', hue=42,
        paragraphs=paragraphs, footnotes=footnotes,
    )
    try:
        result = subprocess.run(
            [sys.executable, 'make_html.py', slug],
            cwd=ROOT, capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f'make_html.py failed:\n{result.stderr}')
        return html_path.read_text()
    finally:
        toml_path.unlink(missing_ok=True)
        html_path.unlink(missing_ok=True)


class MakeHtmlGoldenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
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
        self.assertIn('<em>cross<br>line</em>', self.html)
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
        self.assertIn('href="https://www.vatican.va/content/example.html"', self.html)
        self.assertNotIn('javascript:', self.html)
        self.assertIn('a bad link', self.html)

    def test_paragraph_id_is_stable(self):
        self.assertIn('id="para-1"', self.html)

    def test_js_placeholders_are_substituted(self):
        self.assertNotIn('__INDICATOR_JSON__', self.html)
        self.assertNotIn('__DOC_NAME__', self.html)
        self.assertIn('"Fixture & Co"', self.html)

    def test_generated_preamble_labels_nav_but_not_the_body(self):
        # The fixture opens with unnumbered part-0/chapter-0 prose and no
        # authored part_title, so the renderer generates a "Preamble" label
        # for navigation while suppressing it as an on-page heading.
        self.assertNotIn('class="part-title">Preamble', self.html)
        self.assertIn('<a id="ch-0"></a>', self.html)
        self.assertIn('Preamble', self.html)


class MakeHtmlCollisionTests(unittest.TestCase):
    def test_hidden_duplicate_paragraph_number_does_not_steal_visible_anchor(self):
        html = render_html_fixture(
            'audit_duplicate_para_fixture',
            [
                {
                    'number': 1,
                    'part': 0,
                    'part_title': 'Blessing',
                    'chapter': 0,
                    'section': 0,
                    'hide_number': True,
                    'text': 'A hidden opening paragraph.',
                },
                {
                    'number': 1,
                    'part': 0,
                    'part_title': 'Introduction',
                    'chapter': 0,
                    'section': 0,
                    'text': 'The visible numbered paragraph.',
                },
            ],
            [],
        )

        self.assertIn('id="para-1-1"', html)
        self.assertIn('id="para-1" data-para-num="1"', html)
        self.assertLess(
            html.index('id="para-1-1"'),
            html.index('id="para-1" data-para-num="1"'),
        )

    def test_duplicate_footnote_numbers_get_distinct_targets(self):
        html = render_html_fixture(
            'audit_duplicate_fn_fixture',
            [
                {
                    'number': 1,
                    'part': 0,
                    'chapter': 0,
                    'section': 0,
                    'text': 'Body citation after an uncited note.(1)\n\nFirst citation.(2)',
                },
                {
                    'number': 2,
                    'part': 0,
                    'chapter': 0,
                    'section': 0,
                    'text': 'Second citation.(2)',
                },
            ],
            [
                {
                    'part': 0,
                    'chapter': 0,
                    'section': 0,
                    'number': 1,
                    'text': 'Uncited prefatory note.',
                },
                {
                    'part': 0,
                    'chapter': 0,
                    'section': 0,
                    'number': 1,
                    'text': 'Body note after the uncited note.',
                },
                {
                    'part': 0,
                    'chapter': 0,
                    'section': 0,
                    'number': 2,
                    'text': 'First note.',
                },
                {
                    'part': 0,
                    'chapter': 0,
                    'section': 0,
                    'number': 2,
                    'text': 'Second note.',
                },
            ],
        )

        self.assertIn('<sup><a href="#fn-0-0-1-2">1</a></sup>', html)
        self.assertIn('<sup><a href="#fn-0-0-2-1">2</a></sup>', html)
        self.assertIn('<sup><a href="#fn-0-0-2-2">2</a></sup>', html)
        self.assertIn('id="fn-0-0-1-1"', html)
        self.assertIn('id="fn-0-0-1-2"', html)
        self.assertIn('id="fn-0-0-2-1"', html)
        self.assertIn('id="fn-0-0-2-2"', html)
        self.assertIn('Uncited prefatory note.', html)
        self.assertIn('Body note after the uncited note.', html)
        self.assertIn('First note.', html)
        self.assertIn('Second note.', html)


if __name__ == '__main__':
    unittest.main()
