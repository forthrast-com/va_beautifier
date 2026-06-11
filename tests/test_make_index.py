import unittest

import make_index


class CardMetaTests(unittest.TestCase):
    def test_every_known_slug_validates(self):
        self.assertEqual(make_index.missing_card_meta(list(make_index.CARD_META)), [])

    def test_unknown_slug_is_reported(self):
        slugs = ['gaudium_et_spes', 'not_a_document']
        self.assertEqual(make_index.missing_card_meta(slugs), ['not_a_document'])

    def test_card_meta_types_all_have_labels_and_rank(self):
        for slug, meta in make_index.CARD_META.items():
            self.assertIn(meta['type'], make_index.TILE_KIND_LABEL, slug)
            self.assertIn(meta['type'], make_index.AUTHORITY_RANK, slug)


class CardFieldsTests(unittest.TestCase):
    def test_encyclical_byline_bolds_the_pope(self):
        fields = make_index._card_fields('laudato_si', {
            'name': 'Laudato si’',
            'issued_by': 'Francis',
            'pontificate': 'Francis',
            'date': '2015-05-24',
            'hue': 140,
        })

        self.assertEqual(fields['kind_label'], 'Encyclical Letter')
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


if __name__ == '__main__':
    unittest.main()
