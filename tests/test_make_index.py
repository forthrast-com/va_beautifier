import unittest

import make_index


class TileMetaTests(unittest.TestCase):
    def test_docs_with_tile_type_validate(self):
        docs = {
            'gaudium_et_spes': {
                'type': 'council_constitution',
                'kind_long': 'Pastoral Constitution',
            },
            'laudato_si': {
                'type': 'encyclical',
                'subtitle': 'on Care for Our Common Home',
            },
        }

        self.assertEqual(make_index.missing_tile_meta(docs), [])

    def test_missing_tile_type_is_reported(self):
        docs = {
            'gaudium_et_spes': {
                'type': 'council_constitution',
                'kind_long': 'Pastoral Constitution',
            },
            'not_a_document': {},
        }

        self.assertEqual(make_index.missing_tile_meta(docs), ['not_a_document'])

    def test_missing_tile_subtitle_is_reported(self):
        docs = {
            'gaudium_et_spes': {'type': 'council_constitution'},
            'laudato_si': {'type': 'encyclical'},
        }

        self.assertEqual(
            make_index.missing_tile_meta(docs),
            ['gaudium_et_spes', 'laudato_si'],
        )

    def test_tile_types_all_have_labels_and_rank(self):
        for kind_type in make_index.TILE_KIND_LABEL:
            self.assertIn(kind_type, make_index.AUTHORITY_RANK)

    def test_sort_fields_use_requested_order(self):
        self.assertEqual(
            [(key, label) for key, label, _default, _reversed in make_index.SORT_FIELDS],
            [
                ('date', 'Date'),
                ('name', 'Name'),
                ('pope', 'Pope'),
                ('class', 'Class'),
                ('size', 'Size'),
            ],
        )

    def test_default_direction_labels_for_date_and_size(self):
        labels = {
            key: (default, reversed_)
            for key, _label, default, reversed_ in make_index.SORT_FIELDS
        }
        self.assertEqual(labels['date'], ('most recent', 'oldest first'))
        self.assertEqual(labels['size'], ('longest first', 'shortest first'))


class CardFieldsTests(unittest.TestCase):
    def test_encyclical_byline_bolds_the_pope(self):
        fields = make_index._card_fields('laudato_si', {
            'name': 'Laudato si’',
            'type': 'encyclical',
            'subtitle': 'on Care for Our Common Home',
            'issued_by': 'Francis',
            'pontificate': 'Francis',
            'date': '2015-05-24',
            'hue': 140,
        })

        self.assertEqual(fields['kind_label'], 'Encyclical Letter')
        self.assertEqual(fields['subtitle'], 'on Care for Our Common Home')
        self.assertIn('<strong>Francis</strong>', fields['byline'])
        self.assertEqual(fields['date'], '24 May 2015')

    def test_unknown_slug_falls_back_to_desc_byline(self):
        fields = make_index._card_fields('not_a_document', {
            'name': 'Mystery Doc',
            'desc': 'SOME ISSUING BODY',
            'date': '',
        })

        self.assertEqual(fields['kind_label'], '')
        self.assertEqual(fields['byline'], 'Some Issuing Body')

    def test_body_word_count_uses_paragraph_text_only(self):
        fields = make_index._card_fields('not_a_document', {
            'name': 'Mystery Doc',
            'desc': 'SOME ISSUING BODY',
            'date': '',
            'paragraphs': [
                {
                    'text': (
                        "Alpha beta(1) [linked words](https://example.com) "
                        "*don't* re-roll"
                    ),
                },
            ],
            'footnotes': [{'text': 'Ignored footnote text'}],
            'appendices': [{'text': 'Ignored appendix text'}],
        })

        self.assertEqual(fields['word_count'], 6)


if __name__ == '__main__':
    unittest.main()
