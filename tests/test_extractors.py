import unittest

from extract import gaudium_et_spes, laudato_si, magnifica_humanitas


class ExtractorRegressionTests(unittest.TestCase):
    def test_gaudium_et_spes_retains_latin_headings(self):
        data = gaudium_et_spes.extract()

        self.assertEqual(len(data['paragraphs']), 93)
        self.assertEqual(len(data['footnotes']), 167)
        self.assertEqual(data['hue'], 42)
        self.assertTrue(any(p['heading_la'] for p in data['paragraphs']))
        self.assertTrue(any('*Rom*' in fn['text'] for fn in data['footnotes']))

    def test_laudato_si_retains_appendices_and_note_context(self):
        data = laudato_si.extract()

        self.assertEqual(len(data['paragraphs']), 246)
        self.assertEqual(len(data['footnotes']), 172)
        self.assertEqual(data['hue'], 140)
        self.assertEqual(len(data['appendices']), 2)
        self.assertTrue(any(fn['sub_heading'] for fn in data['footnotes']))
        self.assertTrue(any('*[Centesimus Annus]' in fn['text']
                            for fn in data['footnotes']))

    def test_magnifica_humanitas_retains_modern_structure(self):
        data = magnifica_humanitas.extract()

        self.assertEqual(len(data['paragraphs']), 245)
        self.assertEqual(len(data['footnotes']), 224)
        self.assertEqual(data['hue'], 230)
        self.assertTrue(any(p['chapter_subtitle'] for p in data['paragraphs']))
        self.assertTrue(any(fn['sub_heading'] for fn in data['footnotes']))
        self.assertIn('*corpus*', data['paragraphs'][2]['text'])
        self.assertTrue(any('<sup>th</sup>' in fn['text']
                            for fn in data['footnotes']))


if __name__ == '__main__':
    unittest.main()
