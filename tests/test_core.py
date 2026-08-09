import re
import tempfile
import unittest
from pathlib import Path

from bs4 import BeautifulSoup

from core import (
    CANONICAL_FOOTNOTE_REF,
    HeadingState,
    assign_footnote_context,
    br_text,
    canonical_blockquote,
    ch_order_label,
    clean_text,
    encyclical_split,
    flatten_ws,
    heading_title,
    inline_markup_to_html,
    int_to_roman,
    is_centred,
    is_promulgation,
    is_unnumbered_chapter,
    normalise_footnote_refs,
    normalise_footnote_text,
    numbered_paragraph,
    paragraph_record,
    parse_footnote,
    read_toml,
    repair,
    roman_to_int,
    title_case,
    write_toml,
)


class TextHelperTests(unittest.TestCase):
    def test_canonical_blockquote_preserves_blocks_and_citation(self):
        self.assertEqual(
            canonical_blockquote(
                'First line\nSecond line\n\nNext stanza',
                '*Lk* 10:25–37',
            ),
            '> First line\n> Second line\n>\n> Next stanza\n>\n'
            '> — *Lk* 10:25–37',
        )

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

    def test_clean_text_collapses_non_breaking_spaces(self):
        # Word exports scatter \xa0, often glued to a real space — which
        # would render as visible double spacing in justified text.
        soup = BeautifulSoup(
            '<p>a force of\xa0 good, examined\xa0in\xa0silence</p>',
            'html.parser',
        )

        self.assertEqual(
            clean_text(soup.p),
            'a force of good, examined in silence',
        )

    def test_clean_text_tightens_parenthetical_citation_edges(self):
        soup = BeautifulSoup(
            '<p>See ( <i>Gal</i> 5:22) and (ed. cit. IV, 371 b ).</p>',
            'html.parser',
        )

        self.assertEqual(
            clean_text(soup.p, preserve_formatting=True),
            'See (*Gal* 5:22) and (ed. cit. IV, 371 b).',
        )

    def test_flatten_ws_collapses_newlines_unlike_clean_text(self):
        # The distinguishing behaviour: flatten_ws folds line breaks into
        # spaces (layout noise), where clean_text keeps them (content).
        self.assertEqual(flatten_ws('  a\n  b \t c\n'), 'a b c')
        soup = BeautifulSoup('<p>First<br>Second</p>', 'html.parser')
        self.assertEqual(clean_text(soup.p), 'First\nSecond')
        self.assertEqual(flatten_ws(clean_text(soup.p)), 'First Second')

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

    def test_repair_applies_and_refuses_to_no_op(self):
        self.assertEqual(repair('a 81. b', '81.', '87.'), 'a 87. b')
        # The point of the helper: a snapshot that no longer contains the
        # defect must fail, not silently skip the fix and reintroduce the
        # bug the repair exists to prevent.
        with self.assertRaises(ValueError):
            repair('already fixed', '81.', '87.')
        # Wrong multiplicity is equally suspect — the repair was written
        # against one known occurrence.
        with self.assertRaises(ValueError):
            repair('81. and 81.', '81.', '87.')

    def test_roman_helpers_round_trip(self):
        for number in (1, 4, 9, 14, 42):
            self.assertEqual(roman_to_int(int_to_roman(number)), number)

    def test_title_case_capitalises_through_opening_punctuation(self):
        # str.capitalize() uppercases position zero and lowercases the rest,
        # so a quoted or parenthesised word was never capitalised at all.
        # Vatican titles quote heavily: FT shipped a section heading reading
        # 'Beyond a World of “associates”'.
        self.assertEqual(
            title_case('"THEOLOGY OF LIBERATION"', small_words=True),
            '"Theology of Liberation"',
        )
        self.assertEqual(
            title_case('BEYOND A WORLD OF “ASSOCIATES”'),
            'Beyond a World of “Associates”',
        )
        self.assertEqual(
            title_case('(THEOLOGY OF LIBERATION)'), '(Theology of Liberation)')
        # Elided particles and numerals keep their existing handling.
        self.assertEqual(title_case("L'OSSERVATORE ROMANO"), "L'Osservatore Romano")
        self.assertEqual(title_case('POPE LEO XIV'), 'Pope Leo XIV')

    def test_title_case_distinguishes_words_from_canonical_roman_numerals(self):
        self.assertEqual(
            title_case('CIVIC AND POLITICAL LOVE'),
            'Civic and Political Love',
        )
        self.assertEqual(title_case('VATICAN II'), 'Vatican II')

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

    def test_encyclical_split_pivots_at_on_line(self):
        pre, post = encyclical_split(
            'ENCYCLICAL LETTER',
            'OF THE HOLY FATHER\nFRANCIS\nON CARE FOR OUR COMMON HOME',
        )

        self.assertEqual(
            pre, 'ENCYCLICAL LETTER\nOF THE HOLY FATHER\nFRANCIS'
        )
        self.assertEqual(post, 'ON CARE FOR OUR COMMON HOME')

    def test_encyclical_split_leaves_untouched_when_no_on_line(self):
        pre, post = encyclical_split('TITLE', 'A subtitle without the pivot')

        self.assertEqual(pre, 'TITLE')
        self.assertEqual(post, 'A subtitle without the pivot')

    def test_encyclical_split_no_op_when_first_line_already_on(self):
        pre, post = encyclical_split(
            'ENCYCLICAL LETTER\nOF HIS HOLINESS',
            'ON SAFEGUARDING THE HUMAN PERSON',
        )

        self.assertEqual(pre, 'ENCYCLICAL LETTER\nOF HIS HOLINESS')
        self.assertEqual(post, 'ON SAFEGUARDING THE HUMAN PERSON')


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

    def test_scope_miss_keeps_the_scope_the_source_gave_it(self):
        # Under preserve_scope a note is often cited from outside its own
        # part/chapter (two GeS notes are). The scoped lookup misses, and the
        # note must keep its own scope rather than being re-homed.
        paragraphs = [
            paragraph_record(1, 'Cited (1).', part=1, chapter=1, section=5),
            paragraph_record(2, 'Cited (2).', part=1, chapter=1, section=5),
        ]
        notes = [
            {'part': 1, 'chapter': 1, 'number': 1, 'text': 'In scope.'},
            {'part': 2, 'chapter': 2, 'number': 2, 'text': 'Cited elsewhere.'},
        ]

        assigned = assign_footnote_context(notes, paragraphs, preserve_scope=True)

        self.assertEqual(assigned[1]['part'], 2)
        self.assertEqual(assigned[1]['chapter'], 2)
        self.assertEqual(assigned[1]['section'], 0)

    def test_conclusion_stays_bare_under_roman_chapter_style(self):
        # A document cited by chapter numeral (LN's "VII, 9") still doesn't
        # call its conclusion "XII." — and the web and book renderers share
        # this helper precisely so they cannot disagree about it.
        self.assertTrue(is_unnumbered_chapter(
            'Conclusion', chapter_style='roman'))
        self.assertTrue(is_unnumbered_chapter('Conclusion'))
        # AeN's closing chapter is a numbered chapter, not a bare conclusion.
        self.assertFalse(is_unnumbered_chapter(
            'Concluding Reflections', chapter_style='roman'))
        # Roman style otherwise always numbers, including an introduction.
        self.assertFalse(is_unnumbered_chapter(
            'Introduction', chapter_style='roman'))
        self.assertTrue(is_unnumbered_chapter('Anything', bare_chapters=True))


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
                issued_by='A Dicastery',
                pontificate='A Pope',
                date='2024-01-15',
                identifier='papal:sample:2024-01-15',
                rights='© 2024 Holy See',
                type='encyclical',
                subtitle='on the Sample Document',
                chapter_style='roman',
                book_toc_depth=4,
                paragraphs=[],
                footnotes=[],
            )
            data = read_toml(path)

        self.assertEqual(data['author'], 'A Pope')
        self.assertEqual(data['issued_by'], 'A Dicastery')
        self.assertEqual(data['pontificate'], 'A Pope')
        self.assertEqual(data['date'], '2024-01-15')
        self.assertEqual(data['identifier'], 'papal:sample:2024-01-15')
        self.assertEqual(data['rights'], '© 2024 Holy See')
        self.assertEqual(data['type'], 'encyclical')
        self.assertEqual(data['subtitle'], 'on the Sample Document')
        self.assertEqual(data['chapter_style'], 'roman')
        self.assertEqual(data['book_toc_depth'], 4)
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


class ChOrderLabelTests(unittest.TestCase):
    """Drawer/contents label for each (part, chapter) bucket.

    The case the user caught: a part-intro paragraph (`part=2,
    chapter=0`) used to fall through to the bare 'Part II, Ch. 0'
    fallback. That entry IS the part heading, so it should read
    'Part II: <part_title>' instead."""

    @staticmethod
    def _p(**overrides):
        base = dict(part=0, chapter=0, part_title='', chapter_title='')
        base.update(overrides)
        return base

    def test_part_intro_uses_part_title(self):
        # Part II of GeS: opener has chapter=0, part_title carries the
        # real subject. Old fallback emitted 'Part II, Ch. 0'.
        self.assertEqual(
            ch_order_label(self._p(
                part=2, chapter=0,
                part_title='Some Problems of Special Urgency')),
            'Part II: Some Problems of Special Urgency')

    def test_part_intro_without_title(self):
        # Defensive: a partially-authored TOML with part=1, no title.
        self.assertEqual(
            ch_order_label(self._p(part=1, chapter=0)),
            'Part I')

    def test_top_level_preface(self):
        self.assertEqual(
            ch_order_label(self._p(part_title='Preface')),
            'Preface')

    def test_top_level_chapter_uses_chapter_title(self):
        # LS: chapters live at the root (no part), drawer reads off the
        # chapter title directly.
        self.assertEqual(
            ch_order_label(self._p(
                chapter=3, chapter_title='The Human Roots of the Ecological Crisis')),
            'The Human Roots of the Ecological Crisis')

    def test_part_chapter_uses_chapter_title(self):
        self.assertEqual(
            ch_order_label(self._p(
                part=1, chapter=1,
                part_title='Ignored', chapter_title='The Dignity of the Human Person')),
            'The Dignity of the Human Person')

    def test_part_chapter_falls_back_when_title_missing(self):
        # An untitled chapter still gets a navigable label.
        self.assertEqual(
            ch_order_label(self._p(part=3, chapter=4)),
            'Part III, Ch. 4')


class InlineMarkupTests(unittest.TestCase):
    def test_converts_canonical_markup_and_escapes(self):
        self.assertEqual(
            inline_markup_to_html('A *title*, **claim** & 35<sup>th</sup>'),
            'A <em>title</em>, <strong>claim</strong> &amp; 35<sup>th</sup>',
        )

    def test_escaped_input_is_not_double_escaped(self):
        self.assertEqual(
            inline_markup_to_html('*a &amp; b*', escaped=True),
            '<em>a &amp; b</em>',
        )

    def test_emphasis_spans_line_breaks_with_break_tag(self):
        # Web and book editions must agree on markup that crosses a
        # poetic line break.
        self.assertEqual(
            inline_markup_to_html('*one\ntwo*', break_tag='<br>'),
            '<em>one<br>two</em>',
        )

    def test_strong_is_not_eaten_by_emphasis(self):
        self.assertEqual(
            inline_markup_to_html('**bold** and *ital*'),
            '<strong>bold</strong> and <em>ital</em>',
        )

    def test_strong_emphasis_nests_cleanly(self):
        self.assertEqual(
            inline_markup_to_html('***both***'),
            '<strong><em>both</em></strong>',
        )


class HeadingStateTests(unittest.TestCase):
    def test_chapter_clears_section_and_sub_heading(self):
        state = HeadingState()
        state.set_chapter(1, 'First')
        state.set_section(2, 'A Section')
        state.sub_heading = 'Topic'

        state.set_chapter(2, 'Second')

        self.assertEqual(state.chapter, 2)
        self.assertEqual(state.section, 0)
        self.assertEqual(state.section_title, '')
        self.assertEqual(state.sub_heading, '')

    def test_part_clears_chapter_but_section_keeps_part(self):
        state = HeadingState()
        state.set_part(1, 'Part One')
        state.set_chapter(3, 'Ch')

        state.set_part(2)
        self.assertEqual(state.chapter, 0)
        self.assertEqual(state.chapter_title, '')

        state.set_section(1, 'Sec')
        self.assertEqual(state.part, 2)

    def test_kwargs_round_trip_through_paragraph_record(self):
        state = HeadingState()
        state.set_chapter(1, 'Title', 'Subtitle')
        record = paragraph_record(7, 'Body.', **state.kwargs())

        self.assertEqual(record['chapter'], 1)
        self.assertEqual(record['chapter_subtitle'], 'Subtitle')
        self.assertEqual(record['section'], 0)

    def test_add_section_auto_numbers_within_chapter(self):
        state = HeadingState()
        state.set_chapter(2, 'Ch')
        state.add_section('First topic')
        state.add_section('Second topic')

        self.assertEqual(state.section, 2)
        self.assertEqual(state.section_title, 'Second topic')

        # A new chapter resets the running section count.
        state.set_chapter(3, 'Next')
        state.add_section('Fresh topic')
        self.assertEqual(state.section, 1)


class NumberedParagraphTests(unittest.TestCase):
    PATTERN = re.compile(r'^(\d+)\.\s+(.+)$', re.DOTALL)

    def test_matches_and_keeps_inline_markup(self):
        soup = BeautifulSoup('<p>12. The <i>earth</i> cries out.</p>',
                             'html.parser')

        self.assertEqual(
            numbered_paragraph(soup.p, self.PATTERN),
            (12, 'The *earth* cries out.'),
        )

    def test_non_numbered_paragraph_returns_none(self):
        soup = BeautifulSoup('<p>A heading</p>', 'html.parser')

        self.assertIsNone(numbered_paragraph(soup.p, self.PATTERN))

    def test_custom_text_functions_decide_the_match(self):
        soup = BeautifulSoup('<p>3.\nWrapped   line.</p>', 'html.parser')
        collapse = lambda tag: re.sub(r'\s+', ' ', clean_text(tag)).strip()

        # Default plain text keeps the Word-export line break, so the
        # pattern's `\.\s+` still matches; a collapsing dialect repairs it.
        self.assertEqual(
            numbered_paragraph(soup.p, self.PATTERN,
                               plain_text=collapse, rich_text=collapse),
            (3, 'Wrapped line.'),
        )


class HeadingTitleTests(unittest.TestCase):
    def test_all_caps_is_title_cased_preserving_ai(self):
        self.assertEqual(
            heading_title('TECHNOLOGY  AND THE FUTURE OF AI'),
            'Technology and the Future of AI',
        )

    def test_mixed_case_passes_through(self):
        self.assertEqual(
            heading_title('The res novae of our time'),
            'The res novae of our time',
        )


class EndMatterSignalTests(unittest.TestCase):
    def test_promulgation_datelines(self):
        self.assertTrue(is_promulgation('Given in Rome, at Saint Peter’s'))
        self.assertTrue(is_promulgation('Given at the Vatican, 24 May 2015'))
        self.assertFalse(is_promulgation('Givenness is a concept'))

    def test_centred_by_attribute_or_style(self):
        soup = BeautifulSoup(
            '<p align="CENTER">a</p>'
            '<p style="margin:0; text-align: center;">b</p>'
            '<p>c</p>',
            'html.parser',
        )
        a, b, c = soup.find_all('p')

        self.assertTrue(is_centred(a))
        self.assertTrue(is_centred(b))
        self.assertFalse(is_centred(c))


class BrTextTests(unittest.TestCase):
    def test_br_tags_become_line_breaks(self):
        soup = BeautifulSoup(
            '<p>PASTORAL  CONSTITUTION<br>GAUDIUM ET SPES<br>PROMULGATED</p>',
            'html.parser',
        )

        self.assertEqual(
            br_text(soup.p),
            'PASTORAL CONSTITUTION\nGAUDIUM ET SPES\nPROMULGATED',
        )


if __name__ == '__main__':
    unittest.main()
