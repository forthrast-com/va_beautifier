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


def render_html_fixture(slug, paragraphs, footnotes, **doc_fields):
    BUILD.mkdir(exist_ok=True)
    toml_path = BUILD / f'{slug}.toml'
    html_path = SITE / f'{slug}.html'
    write_toml(
        toml_path, name='Fixture & Co', hue=42,
        paragraphs=paragraphs, footnotes=footnotes, **doc_fields,
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

    def test_canonical_blockquote_renders_quote_and_citation(self):
        html = render_html_fixture(
            'audit_blockquote_fixture',
            [{
                'number': 1,
                'text': (
                    'Introductory prose.\n\n'
                    '> Quoted text.\n>\n> — *Lk* 10:25–37'
                ),
            }],
            [],
        )
        self.assertIn(
            '<blockquote class="document-quote scripture-quote">',
            html,
        )
        self.assertIn('<p>Quoted text.</p>', html)
        self.assertIn(
            '<footer>— <cite><em>Lk</em> 10:25–37</cite></footer>',
            html,
        )
        self.assertNotIn('&gt; Quoted text', html)

    def test_uncited_blockquote_stays_quiet(self):
        html = render_html_fixture(
            'audit_declaration_fixture',
            [{'number': 1, 'text': '> A solemn declaration.'}],
            [],
        )
        self.assertIn('<blockquote class="document-quote">', html)
        self.assertNotIn('scripture-quote', html.split('</style>', 1)[-1])

    def test_structural_scripture_epigraph_uses_the_same_card(self):
        html = render_html_fixture(
            'audit_scripture_epigraph_fixture',
            [{
                'number': 1,
                'part': 1,
                'part_title': 'Verbum Dei',
                'part_subtitle': (
                    '> In the beginning was the Word\n>\n> — *Jn* 1:1'
                ),
                'text': 'Opening prose.',
            }],
            [],
        )
        self.assertIn(
            '<blockquote class="part-subtitle document-quote '
            'scripture-quote">',
            html,
        )


class MakeHtmlChapterLabelTests(unittest.TestCase):
    def test_long_layout_pins_only_the_current_paragraph_number(self):
        html = render_html_fixture(
            'audit_long_layout_fixture',
            [{'number': 1, 'text': 'Long document prose.'}],
            [],
            layout={'long': True},
        )
        self.assertIn('class="doc-audit_long_layout_fixture layout-long"', html)
        self.assertIn('.layout-long .para-num {', html)
        self.assertIn('function updateActiveNum()', html)
        self.assertIn('activePara.querySelector(\'.para-num\')', html)
        self.assertIn('top: calc(var(--bar-h) + 6px);', html)
        self.assertIn(
            "document.querySelectorAll('[data-sticky], h4.section-title')",
            html,
        )
        self.assertIn(
            "el.matches('h4.section-title') ? el.textContent : ''",
            html,
        )
        self.assertNotIn('activeNum.style.top =', html)
        self.assertNotIn('function placeNums()', html)

    def test_bare_chapter_drawer_labels_drop_the_prefix(self):
        # bare_chapters docs (SS, DCE) render body headings title-only; the
        # drawer contents and no-JS TOC labels must match, not re-add
        # "Chapter N: ".
        html = render_html_fixture(
            'audit_bare_chapter_fixture',
            [
                {'number': 1, 'text': 'Opening prose.'},
                {'number': 2, 'chapter': 1, 'chapter_title': 'Faith is Hope',
                 'text': 'Hopeful prose.'},
            ],
            [],
            layout={'bare_chapters': True},
        )
        self.assertNotIn('Chapter 1', html)
        self.assertIn('Faith is Hope', html)

    def test_trailing_conclusion_drawer_label_drops_the_prefix(self):
        # The conclusion suppression is independent of bare_chapters: a
        # numbered-chapter doc still shows its trailing Conclusion bare,
        # matching the body's is_unnumbered rendering.
        html = render_html_fixture(
            'audit_conclusion_fixture',
            [
                {'number': 1, 'text': 'Opening prose.'},
                {'number': 2, 'chapter': 1, 'chapter_title': 'Ideas',
                 'text': 'Numbered chapter prose.'},
                {'number': 3, 'chapter': 2, 'chapter_title': 'Conclusion',
                 'text': 'Closing prose.'},
            ],
            [],
        )
        self.assertIn('Chapter 1: Ideas', html)
        self.assertNotIn('Chapter 2: Conclusion', html)


class MakeHtmlPartNavTests(unittest.TestCase):
    def test_parted_documents_get_part_rows_in_contents_and_noscript_toc(self):
        # VD/DCE/GeS render Part I/II headings in the body and indicator;
        # the drawer contents tree and no-JS TOC must show the same
        # grouping, not a flat chapter list.
        html = render_html_fixture(
            'audit_parts_fixture',
            [
                {'number': 1, 'text': 'Opening prose.'},
                {'number': 2, 'part': 1, 'part_title': 'The Word of God',
                 'chapter': 1, 'chapter_title': 'The God Who Speaks',
                 'text': 'First part prose.'},
                {'number': 3, 'part': 2, 'part_title': 'The Word in the Church',
                 'chapter': 1, 'chapter_title': 'Receiving the Word',
                 'text': 'Second part prose.'},
            ],
            [],
        )
        # Em-dash separator: part titles routinely carry their own colon.
        self.assertIn('Part I — The Word of God', html)
        self.assertIn('Part II — The Word in the Church', html)
        self.assertIn('ntoc-part', html)
        # the part row precedes its first chapter row in the contents tree
        self.assertLess(
            html.index('Part I — The Word of God'),
            html.index('The God Who Speaks'),
        )


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
