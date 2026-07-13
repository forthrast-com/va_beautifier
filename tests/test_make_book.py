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

    def test_body_blockquote_reaches_pandoc_as_markdown(self):
        quote = '> Quoted text.\n>\n> — *Lk* 10:25–37'

        self.assertEqual(
            make_book._markdown_body_chunk(quote),
            f'::: {{.scripture-quote}}\n{quote}\n:::',
        )

    def test_uncited_body_blockquote_stays_plain(self):
        quote = '> A solemn declaration.'

        self.assertEqual(make_book._markdown_body_chunk(quote), quote)

    def test_appendix_stanzas_suppress_pdf_first_line_indents(self):
        rendered = make_book._markdown_appendix_body(
            'First stanza line\nSecond line\n\n'
            'Second stanza line\nAnother line'
        )

        self.assertEqual(rendered.count('first-line-indent: 0em'), 2)
        self.assertIn('First stanza line  \nSecond line', rendered)
        self.assertIn('Second stanza line  \nAnother line', rendered)

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

    def test_emit_markdown_disambiguates_duplicate_footnote_numbers(self):
        data = {
            'name': 'Sample Document',
            'paragraphs': [
                {
                    'number': 1,
                    'part': 0,
                    'chapter': 0,
                    'section': 0,
                    'text': (
                        'First paragraph with an uncited leading note.(1)\n\n'
                        'Then a repeated note number.(2)'
                    ),
                },
                {
                    'number': 2,
                    'part': 0,
                    'chapter': 0,
                    'section': 0,
                    'text': 'Second paragraph with the same note number.(2)',
                },
            ],
            'footnotes': [
                {
                    'part': 0,
                    'chapter': 0,
                    'number': 1,
                    'text': 'Uncited leading note.',
                },
                {
                    'part': 0,
                    'chapter': 0,
                    'number': 1,
                    'text': 'Cited body note.',
                },
                {
                    'part': 0,
                    'chapter': 0,
                    'number': 2,
                    'text': 'First duplicate note.',
                },
                {
                    'part': 0,
                    'chapter': 0,
                    'number': 2,
                    'text': 'Second duplicate note.',
                },
            ],
        }

        old_build = make_book.BUILD
        with tempfile.TemporaryDirectory() as tmp_dir:
            make_book.BUILD = Path(tmp_dir)
            try:
                md_path = make_book.emit_markdown(data, 'sample_doc')
                rendered = md_path.read_text(encoding='utf-8')
            finally:
                make_book.BUILD = old_build

        self.assertIn('uncited leading note.[^0-0-1-2]', rendered)
        self.assertIn('repeated note number.[^0-0-2-1]', rendered)
        self.assertIn('same note number.[^0-0-2-2]', rendered)
        self.assertNotIn('[^0-0-1-1]', rendered)
        self.assertIn('[^0-0-1-2]: Cited body note.', rendered)
        self.assertIn('[^0-0-2-1]: First duplicate note.', rendered)
        self.assertIn('[^0-0-2-2]: Second duplicate note.', rendered)

    def test_emit_markdown_preserves_body_verse_line_breaks(self):
        data = {
            'name': 'Sample Document',
            'paragraphs': [{
                'number': 1,
                'part': 0,
                'chapter': 0,
                'section': 0,
                'text': (
                    'A normal prose subparagraph with a note.(1)\n\n'
                    '*Mother, help our faith!\n'
                    'Open our ears to hear God’s word.\n'
                    'Teach us to follow.*'
                ),
            }],
            'footnotes': [{
                'part': 0,
                'chapter': 0,
                'number': 1,
                'text': 'A footnote line\nwrapped as source text.',
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

        self.assertIn(
            '**1.** A normal prose subparagraph with a note.[^0-0-1]\n\n',
            rendered,
        )
        self.assertIn(
            '`#block[#set par(first-line-indent: 0em); `{=typst}'
            '*Mother, help our faith!  \n'
            'Open our ears to hear God’s word.  \n'
            'Teach us to follow.*'
            '`]`{=typst}\n',
            rendered,
        )
        self.assertIn(
            '[^0-0-1]: A footnote line\nwrapped as source text.\n',
            rendered,
        )
        self.assertNotIn('A footnote line  \nwrapped as source text.', rendered)

    def test_emit_markdown_gates_dce_prayer_line_breaks_for_typst(self):
        data = {
            'name': 'Deus Caritas Est',
            'paragraphs': [{
                'number': 42,
                'part': 2,
                'chapter': 1,
                'chapter_title': 'Conclusion',
                'section': 0,
                'text': (
                    'To her we entrust the Church and her mission in the '
                    'service of love:\n\n'
                    '*Holy Mary, Mother of God,\n'
                    'you have given the world its true light,\n'
                    'Jesus, your Son – the Son of God.\n'
                    'in the midst of a thirsting world.*'
                ),
            }],
            'footnotes': [],
        }

        old_build = make_book.BUILD
        with tempfile.TemporaryDirectory() as tmp_dir:
            make_book.BUILD = Path(tmp_dir)
            try:
                md_path = make_book.emit_markdown(data, 'deus_caritas_est')
                rendered = md_path.read_text(encoding='utf-8')
            finally:
                make_book.BUILD = old_build

        self.assertIn(
            '**42.** To her we entrust the Church and her mission in the '
            'service of love:\n\n',
            rendered,
        )
        self.assertIn(
            '`#block[#set par(first-line-indent: 0em); `{=typst}'
            '*Holy Mary, Mother of God,  \n'
            'you have given the world its true light,  \n'
            'Jesus, your Son – the Son of God.  \n'
            'in the midst of a thirsting world.*'
            '`]`{=typst}\n',
            rendered,
        )

    def test_emit_markdown_keeps_vd_part_opener_on_one_pdf_page(self):
        data = {
            'name': 'Verbum Domini',
            'paragraphs': [{
                'number': 50,
                'part': 2,
                'part_title': 'Verbum in Ecclesia',
                'part_subtitle': (
                    '“But to all who received him he gave power\n'
                    'to become children of God”\n'
                    '(Jn 1:12)'
                ),
                'chapter': 1,
                'chapter_title': 'The Word of God and the Church',
                'section': 1,
                'section_title': 'The Church receives the word',
                'text': 'The Lord speaks his word so that it may be received.',
            }],
            'footnotes': [],
        }

        old_build = make_book.BUILD
        with tempfile.TemporaryDirectory() as tmp_dir:
            make_book.BUILD = Path(tmp_dir)
            try:
                md_path = make_book.emit_markdown(data, 'verbum_domini')
                rendered = md_path.read_text(encoding='utf-8')
            finally:
                make_book.BUILD = old_build

        self.assertIn('# Part II: Verbum in Ecclesia', rendered)
        self.assertIn('## Chapter 1: The Word of God and the Church', rendered)
        self.assertIn('### The Church receives the word', rendered)
        self.assertLess(
            rendered.index('# Part II: Verbum in Ecclesia'),
            rendered.index('“But to all who received him he gave power'),
        )
        self.assertLess(
            rendered.index('“But to all who received him he gave power'),
            rendered.index('## Chapter 1: The Word of God and the Church'),
        )
        self.assertLess(
            rendered.index('## Chapter 1: The Word of God and the Church'),
            rendered.index('### The Church receives the word'),
        )
        opener = rendered[
            rendered.index('# Part II: Verbum in Ecclesia'):
            rendered.index('### The Church receives the word')
        ]
        self.assertNotIn('#pagebreak(weak: true)', opener)

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
