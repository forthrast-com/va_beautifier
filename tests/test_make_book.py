import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import textwrap
import unittest

import make_book
from make_book import (
    _copyright_page_typst,
    _end_matter_html,
    _end_matter_typst,
    _markdown_preserve_breaks,
    _normalise_vatican_links,
    _pdf_accent,
    _typ_inline,
)
from project import ROOT


def _inline_text(inlines):
    parts = []
    for inline in inlines:
        kind = inline.get('t')
        if kind == 'Str':
            parts.append(inline.get('c', ''))
        elif kind == 'Space':
            parts.append(' ')
        elif kind in ('Emph', 'Strong'):
            parts.append(_inline_text(inline.get('c', [])))
    return ''.join(parts)


class EndMatterRenderTests(unittest.TestCase):
    def test_pdf_colophon_has_document_and_edition_metadata(self):
        rendered = _copyright_page_typst({
            'name': 'Sample',
            'author': 'An Author',
            'issued_by': 'A Dicastery',
            'pontificate': 'A Pope',
            'date': '2026-03-04',
            'source_url': 'https://www.vatican.va/sample.html',
            'identifier': 'sample:2026-03-04',
            'publisher': 'circulars.forthrast.com',
            'collection': 'The Circulars (Vatican documents)',
        })

        self.assertIn('[About this edition]', rendered)
        self.assertIn('[DOCUMENT]', rendered)
        self.assertIn('[EDITION]', rendered)
        self.assertIn('[Issued By]', rendered)
        self.assertIn('[Pontificate]', rendered)
        self.assertIn('[A5 reader PDF]', rendered)
        self.assertIn('[Source Code]', rendered)
        self.assertNotIn('[· · ·]', rendered)

    def test_pdf_colophon_omits_duplicate_pontificate(self):
        rendered = _copyright_page_typst({
            'name': 'Sample',
            'issued_by': 'A Pope',
            'pontificate': 'A Pope',
        })

        self.assertIn('[Issued By]', rendered)
        self.assertNotIn('[Pontificate]', rendered)

    def test_appendix_markdown_preserves_poetic_line_breaks(self):
        rendered = _markdown_preserve_breaks('First line\nSecond line\n\nNext stanza')

        self.assertEqual(rendered, 'First line  \nSecond line\n\nNext stanza')

    def test_book_markdown_expands_vatican_relative_links(self):
        self.assertEqual(
            _normalise_vatican_links('[Doc](/content/example.html)'),
            '[Doc](https://www.vatican.va/content/example.html)',
        )

    def test_emit_markdown_preserves_multi_paragraph_footnote_continuation(self):
        data = {
            'name': 'Sample Document',
            'paragraphs': [{
                'number': 1,
                'part': 0,
                'chapter': 0,
                'section': 0,
                'text': 'Body with a note.(1)',
            }],
            'footnotes': [{
                'part': 0,
                'chapter': 0,
                'number': 1,
                'text': 'First note paragraph.\n\nSecond note paragraph.',
            }],
        }

        old_build = make_book.BUILD
        with tempfile.TemporaryDirectory() as tmp_dir:
            make_book.BUILD = Path(tmp_dir)
            try:
                md_path = make_book.emit_markdown(data, 'sample_doc')
                rendered = md_path.read_text(encoding='utf-8')
            finally:
                make_book.BUILD = old_build

        self.assertIn('[^0-0-1]: First note paragraph.', rendered)
        self.assertIn('\n    \n    Second note paragraph.\n', rendered)

    @unittest.skipUnless(shutil.which('pandoc'), 'pandoc not found')
    def test_epub_filter_strips_synthetic_metadata_title_h1(self):
        source = textwrap.dedent("""\
            ---
            title: Sample Document
            ---

            # Sample Document

            # Part One

            Body text.
            """)
        result = subprocess.run(
            [
                'pandoc',
                '-f', 'markdown+smart',
                '-t', 'json',
                f'--lua-filter={ROOT / "templates" / "strip_fn_backlink.lua"}',
            ],
            input=source,
            text=True,
            capture_output=True,
            check=True,
        )
        blocks = json.loads(result.stdout)['blocks']

        self.assertEqual(blocks[0]['t'], 'Header')
        self.assertEqual(_inline_text(blocks[0]['c'][2]), 'Part One')
        self.assertFalse(any(
            block['t'] == 'Header'
            and _inline_text(block['c'][2]) == 'Sample Document'
            for block in blocks
        ))

    def test_html_preserves_formatting_signature_break_and_signatories(self):
        rendered = _end_matter_html(
            '*Approved this* Note *for publication.*',
            [{'name': 'A Name', 'role': 'Prefect'}],
            '*Ex audientia\nFranciscus*',
        )

        self.assertIn('<em>Approved this</em> Note <em>for publication.</em>',
                      rendered)
        # No <hr> in the EPUB colophon — see make_book._end_matter_html.
        self.assertNotIn('<hr ', rendered)
        self.assertIn('A Name<br /><em>Prefect</em>', rendered)
        self.assertIn('<em>Ex audientia<br />Franciscus</em>', rendered)

    def test_typst_preserves_formatting_signature_break_and_signatories(self):
        rendered = _end_matter_typst(
            '*Approved this* Note *for publication.*',
            [{'name': 'A Name', 'role': 'Prefect'}],
            '*Ex audientia\nFranciscus*',
        )

        self.assertIn('#emph[Approved this] Note #emph[for publication.]',
                      rendered)
        self.assertIn('stroke: (paint: rgb("#756d60"), thickness: 0.5pt)',
                      rendered)
        self.assertIn('A Name', rendered)
        self.assertIn('#text(size: 9pt, style: "italic")[Prefect]', rendered)
        self.assertIn('#emph[Ex audientia \\\n    Franciscus]', rendered)

    def test_typst_nests_bold_italic_markup(self):
        self.assertEqual(
            _typ_inline('***Both***'),
            '#strong[#emph[Both]]',
        )

    def test_pdf_accent_is_document_specific_and_muted(self):
        self.assertEqual(_pdf_accent(140), '#3d714e')
        self.assertNotEqual(_pdf_accent(140), _pdf_accent(230))


if __name__ == '__main__':
    unittest.main()
