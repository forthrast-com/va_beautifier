import unittest

from extract import (
    antiqua_et_nova,
    gaudium_et_spes,
    laudato_si,
    magnifica_humanitas,
    quo_vadis_humanitas,
    sacrosanctum_concilium,
)


class ExtractorRegressionTests(unittest.TestCase):
    def test_gaudium_et_spes_retains_latin_headings(self):
        data = gaudium_et_spes.extract()

        self.assertEqual(len(data['paragraphs']), 93)
        self.assertEqual(len(data['footnotes']), 167)
        self.assertEqual(data['hue'], 42)
        self.assertEqual(data['desc_post'], '')
        self.assertIn('Promulgated by His Holiness, Pope Paul VI',
                      data['promulgation'])
        self.assertTrue(any(p['heading_la'] for p in data['paragraphs']))
        self.assertTrue(any('*Rom*' in fn['text'] for fn in data['footnotes']))

    def test_sacrosanctum_concilium_treats_promulgation_as_end_matter(self):
        data = sacrosanctum_concilium.extract()

        self.assertEqual(data['desc_post'], '')
        self.assertIn('Solemnly Promulgated by His Holiness Pope Paul VI',
                      data['promulgation'])
        self.assertEqual(data['paragraphs'][-1]['number'], 130)
        self.assertTrue(data['paragraphs'][-1]['break_after'])
        self.assertEqual(len(data['appendices']), 1)
        self.assertEqual(data['appendices'][0]['kind'], 'declaration')
        self.assertIn('1. The Sacred Council would not object',
                      data['appendices'][0]['text'])

    def test_laudato_si_retains_appendices_and_note_context(self):
        data = laudato_si.extract()

        self.assertEqual(len(data['paragraphs']), 246)
        self.assertEqual(len(data['footnotes']), 172)
        self.assertEqual(data['hue'], 140)
        self.assertEqual(len(data['appendices']), 2)
        self.assertTrue(all(app['kind'] == 'prayer' for app in data['appendices']))
        self.assertTrue(any(fn['sub_heading'] for fn in data['footnotes']))
        self.assertTrue(any('*[Centesimus Annus]' in fn['text']
                            for fn in data['footnotes']))

    def test_magnifica_humanitas_retains_modern_structure(self):
        data = magnifica_humanitas.extract()

        self.assertEqual(len(data['paragraphs']), 245)
        self.assertEqual(len(data['footnotes']), 224)
        self.assertEqual(data['hue'], 230)
        self.assertEqual(data['paragraphs'][0]['section'], 0)
        self.assertEqual(data['paragraphs'][0]['section_title'], '')
        self.assertTrue(any(p['chapter_subtitle'] for p in data['paragraphs']))
        self.assertTrue(any(fn['sub_heading'] for fn in data['footnotes']))
        self.assertIn('*corpus*', data['paragraphs'][2]['text'])
        self.assertTrue(any('<sup>th</sup>' in fn['text']
                            for fn in data['footnotes']))
        conclusion = {p['number']: p for p in data['paragraphs'][228:]}
        self.assertEqual(conclusion[229]['chapter'], 5)
        self.assertEqual(conclusion[229]['section_title'], 'CONCLUSION')
        self.assertEqual(conclusion[230]['sub_heading'],
                         'The Word became flesh')
        self.assertEqual(conclusion[243]['sub_heading'],
                         'The song of hope: the Magnificat')

    def test_antiqua_et_nova_extracts_curia_divisions_and_end_matter(self):
        data = antiqua_et_nova.extract()

        self.assertEqual(len(data['paragraphs']), 117)
        self.assertEqual(len(data['footnotes']), 215)
        self.assertEqual(data['chapter_style'], 'roman')
        self.assertEqual(data['book_toc_depth'], 4)
        self.assertEqual(data['paragraphs'][0]['chapter_title'], 'Introduction')
        self.assertEqual(
            data['paragraphs'][-1]['chapter_title'], 'Concluding Reflections'
        )
        self.assertIn('Given in Rome', data['promulgation'])
        self.assertIn('*The Supreme Pontiff', data['promulgation'])
        self.assertEqual(data['signature'],
                         '*Ex audientia die 14 ianuarii 2025\nFranciscus*')
        self.assertEqual(len(data['signatories']), 4)
        self.assertEqual(data['signatories'][0]['role'], 'Prefect')
        self.assertEqual(data['signatories'][-1]['name'],
                         'Most Rev. Paul Tighe')
        self.assertIn('*Catechism of the Catholic Church*',
                      data['footnotes'][0]['text'])
        self.assertNotIn('\n', data['paragraphs'][0]['text'])

    def test_quo_vadis_extracts_preliminary_note_and_first_footnote(self):
        data = quo_vadis_humanitas.extract()

        self.assertEqual(len(data['paragraphs']), 167)
        self.assertEqual(len(data['footnotes']), 200)
        self.assertTrue(data['paragraphs'][0]['hide_number'])
        self.assertEqual(data['paragraphs'][0]['part_title'], 'Preliminary Note')
        self.assertEqual(data['footnotes'][0]['number'], 1)
        self.assertIn('*[Dignitas infinita]', data['footnotes'][0]['text'])
        self.assertEqual(data['paragraphs'][-1]['chapter_title'], 'Conclusion')


if __name__ == '__main__':
    unittest.main()
