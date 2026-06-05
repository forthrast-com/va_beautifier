import unittest

from make_book import (
    _end_matter_html,
    _end_matter_typst,
    _markdown_preserve_breaks,
    _pdf_accent,
)


class EndMatterRenderTests(unittest.TestCase):
    def test_appendix_markdown_preserves_poetic_line_breaks(self):
        rendered = _markdown_preserve_breaks('First line\nSecond line\n\nNext stanza')

        self.assertEqual(rendered, 'First line  \nSecond line\n\nNext stanza')

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

    def test_pdf_accent_is_document_specific_and_muted(self):
        self.assertEqual(_pdf_accent(140), '#3d714e')
        self.assertNotEqual(_pdf_accent(140), _pdf_accent(230))


if __name__ == '__main__':
    unittest.main()
