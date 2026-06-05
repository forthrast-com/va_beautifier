import re
import tempfile
import unittest
from pathlib import Path

from bs4 import BeautifulSoup

from core import (
    CANONICAL_FOOTNOTE_REF,
    assign_footnote_context,
    clean_text,
    int_to_roman,
    normalise_footnote_refs,
    normalise_footnote_text,
    paragraph_record,
    parse_footnote,
    read_toml,
    roman_to_int,
    write_toml,
)


class TextHelperTests(unittest.TestCase):
    def test_clean_text_preserves_lines_and_external_links(self):
        soup = BeautifulSoup(
            '<p>First<br>Second <a href="https://example.test/x">link</a> '
            '<a href="#_ftn1">[1]</a></p>',
            'html.parser',
        )

        self.assertEqual(
            clean_text(soup.p),
            'First\nSecond [link](https://example.test/x) [1]',
        )

    def test_clean_text_preserves_authored_inline_formatting_when_requested(self):
        soup = BeautifulSoup(
            '<p>A <i>title</i>, <b>claim</b>, 35<sup>th</sup> '
            '<a href="https://example.test/work"><i>Work</i></a> '
            '<sup><a href="#_ftn1">[1]</a></sup></p>',
            'html.parser',
        )

        self.assertEqual(
            clean_text(soup.p, preserve_formatting=True),
            'A *title*, **claim**, 35<sup>th</sup> '
            '[*Work*](https://example.test/work) [1]',
        )

    def test_footnote_refs_are_normalised_without_matching_years(self):
        text = normalise_footnote_refs(
            'Creation [12] and hope (13), in (2015).', bracketed=True
        )

        self.assertEqual(text, 'Creation(12) and hope(13), in (2015).')
        self.assertEqual(CANONICAL_FOOTNOTE_REF.findall(text), ['12', '13'])

    def test_formatted_footnote_refs_drop_source_superscripts(self):
        text = normalise_footnote_refs(
            'Creation<sup><sup>[46]</sup></sup> and hope [47].',
            bracketed=True,
        )

        self.assertEqual(text, 'Creation(46) and hope(47).')

    def test_roman_helpers_round_trip(self):
        for number in (1, 4, 9, 14, 42):
            self.assertEqual(roman_to_int(int_to_roman(number)), number)

    def test_footnote_text_uses_en_dash_between_numeric_ranges(self):
        self.assertEqual(
            normalise_footnote_text('See pp. 843-844; Prov 8:22-31.'),
            'See pp. 843–844; Prov 8:22–31.',
        )

    def test_footnote_text_leaves_compound_names_alone(self):
        self.assertEqual(
            normalise_footnote_text('See Marie-Curie and Levi-Strauss.'),
            'See Marie-Curie and Levi-Strauss.',
        )

    def test_footnote_text_rewrites_mangled_paragraph_citation(self):
        self.assertEqual(
            normalise_footnote_text(
                'Cf. Dignitas infinita, 2 April 2024, 6. 11.'
            ),
            'Cf. Dignitas infinita, 2 April 2024, nn. 6, 11.',
        )

    def test_footnote_text_leaves_unknown_work_trailing_numbers_alone(self):
        self.assertEqual(
            normalise_footnote_text('Some Work, vol. 6. p. 11.'),
            'Some Work, vol. 6. p. 11.',
        )


class FootnoteTests(unittest.TestCase):
    def test_parse_footnote_returns_canonical_record(self):
        note = parse_footnote(
            '[7] See also [8].',
            re.compile(r'^\[(\d+)\]\s+(.+)$'),
            bracketed_refs=True,
        )

        self.assertEqual(
            note,
            {'part': 0, 'chapter': 0, 'number': 7, 'text': 'See also(8).'},
        )

    def test_context_uses_lowest_heading_of_first_citation(self):
        paragraphs = [
            paragraph_record(
                1, 'Earlier note (3).', chapter=1, section=2,
                sub_heading='First heading',
            ),
            paragraph_record(
                2, 'Repeated note (3).', chapter=2, section=1,
                sub_heading='Later heading',
            ),
        ]

        assigned = assign_footnote_context(
            [{'part': 0, 'chapter': 0, 'number': 3, 'text': 'A note.'}],
            paragraphs,
        )

        self.assertEqual(assigned[0]['chapter'], 1)
        self.assertEqual(assigned[0]['section'], 2)
        self.assertEqual(assigned[0]['sub_heading'], 'First heading')

    def test_preserve_scope_disambiguates_reused_note_numbers(self):
        paragraphs = [
            paragraph_record(1, 'One (1).', part=1, chapter=1, section=2),
            paragraph_record(2, 'Two (1).', part=2, chapter=1, section=4),
        ]
        notes = [
            {'part': 2, 'chapter': 1, 'number': 1, 'text': 'Second part.'},
        ]

        assigned = assign_footnote_context(notes, paragraphs, preserve_scope=True)

        self.assertEqual(assigned[0]['part'], 2)
        self.assertEqual(assigned[0]['section'], 4)


class TomlTests(unittest.TestCase):
    def test_toml_round_trip_includes_hue_and_footnote_context(self):
        paragraph = paragraph_record(
            1, 'Text (1).', chapter=2, section=3, sub_heading='A heading'
        )
        note = {
            'part': 0,
            'chapter': 2,
            'section': 3,
            'sub_heading': 'A heading',
            'number': 1,
            'text': 'A note.',
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'sample.toml'
            write_toml(
                path,
                name='Sample',
                hue=230,
                paragraphs=[paragraph],
                footnotes=[note],
            )
            data = read_toml(path)

        self.assertEqual(data['hue'], 230)
        self.assertEqual(data['paragraphs'][0]['sub_heading'], 'A heading')
        self.assertEqual(data['footnotes'][0]['section'], 3)
        self.assertEqual(data['footnotes'][0]['sub_heading'], 'A heading')

    def test_toml_emits_imprint_metadata_with_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'imprint.toml'
            write_toml(
                path,
                name='Sample',
                author='A Pope',
                date='2024-01-15',
                identifier='papal:sample:2024-01-15',
                rights='© 2024 Holy See',
                paragraphs=[],
                footnotes=[],
            )
            data = read_toml(path)

        self.assertEqual(data['author'], 'A Pope')
        self.assertEqual(data['date'], '2024-01-15')
        self.assertEqual(data['identifier'], 'papal:sample:2024-01-15')
        self.assertEqual(data['rights'], '© 2024 Holy See')
        self.assertEqual(data['publisher'], 'circulars.forthrast.com')
        self.assertEqual(data['collection'], 'The Circulars (Vatican documents)')

    def test_toml_imprint_overrides_replace_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'imprint.toml'
            write_toml(
                path,
                name='Sample',
                publisher='Custom Press',
                collection='Other Series',
                paragraphs=[],
                footnotes=[],
            )
            data = read_toml(path)

        self.assertEqual(data['publisher'], 'Custom Press')
        self.assertEqual(data['collection'], 'Other Series')

    def test_toml_round_trip_preserves_structured_end_matter(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'end-matter.toml'
            write_toml(
                path,
                name='Sample',
                promulgation='*Approved this* Note *for publication.*',
                signature='*Ex audientia\nFranciscus*',
                appendices=[{
                    'title': 'Prayer',
                    'kind': 'prayer',
                    'text': 'First line\nSecond line',
                }],
                signatories=[{'name': 'A Name', 'role': 'Prefect'}],
                paragraphs=[],
                footnotes=[],
            )
            data = read_toml(path)

        self.assertEqual(data['signature'], '*Ex audientia\nFranciscus*')
        self.assertEqual(
            data['signatories'], [{'name': 'A Name', 'role': 'Prefect'}]
        )
        self.assertEqual(data['appendices'][0]['kind'], 'prayer')


if __name__ == '__main__':
    unittest.main()
