import unittest

from extract import (
    antiqua_et_nova,
    fides_et_ratio,
    gaudium_et_spes,
    laudato_si,
    lumen_fidei,
    magnifica_humanitas,
    quo_vadis_humanitas,
    sacrosanctum_concilium,
    verbum_domini,
)


def needs_sources(*paths):
    """Skip when a source snapshot is absent. `sources/` is gitignored, so a
    fresh clone has none until `download_sources.py` runs — these regression
    tests should skip loudly there, not error."""
    missing = [p.name for p in paths if not p.exists()]
    return unittest.skipIf(
        missing,
        f'source snapshot(s) missing: {", ".join(missing)} — '
        f'run download_sources.py',
    )


class ExtractorRegressionTests(unittest.TestCase):
    @needs_sources(gaudium_et_spes.EN_SRC, gaudium_et_spes.LT_SRC)
    def test_gaudium_et_spes_retains_latin_headings(self):
        data = gaudium_et_spes.extract()

        self.assertEqual(len(data['paragraphs']), 93)
        self.assertEqual(len(data['footnotes']), 167)
        self.assertEqual(data['hue'], 42)
        self.assertEqual(data['issued_by'], 'Second Vatican Council')
        self.assertEqual(data['pontificate'], 'Paul VI')
        self.assertEqual(data['desc_post'], '')
        self.assertIn('Promulgated by His Holiness, Pope Paul VI',
                      data['promulgation'])
        self.assertTrue(any(p['heading_la'] for p in data['paragraphs']))
        self.assertTrue(any('*Rom*' in fn['text'] for fn in data['footnotes']))

    @needs_sources(sacrosanctum_concilium.EN_SRC)
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

    @needs_sources(laudato_si.EN_SRC)
    def test_laudato_si_retains_appendices_and_note_context(self):
        data = laudato_si.extract()

        self.assertEqual(len(data['paragraphs']), 246)
        self.assertEqual(len(data['footnotes']), 172)
        self.assertEqual(data['hue'], 140)
        self.assertEqual(data['issued_by'], 'Francis')
        self.assertEqual(data['pontificate'], 'Francis')
        self.assertEqual(len(data['appendices']), 2)
        self.assertTrue(all(app['kind'] == 'prayer' for app in data['appendices']))
        self.assertTrue(any(fn['sub_heading'] for fn in data['footnotes']))
        self.assertTrue(any('*[Centesimus Annus]' in fn['text']
                            for fn in data['footnotes']))

    @needs_sources(magnifica_humanitas.EN_SRC)
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
        self.assertEqual(conclusion[229]['section_title'], 'Conclusion')
        self.assertEqual(conclusion[230]['sub_heading'],
                         'The Word became flesh')
        self.assertEqual(conclusion[243]['sub_heading'],
                         'The song of hope: the Magnificat')

    @needs_sources(antiqua_et_nova.EN_SRC)
    def test_antiqua_et_nova_extracts_curia_divisions_and_end_matter(self):
        data = antiqua_et_nova.extract()

        self.assertEqual(len(data['paragraphs']), 117)
        self.assertEqual(len(data['footnotes']), 215)
        self.assertEqual(data['chapter_style'], 'roman')
        self.assertEqual(data['book_toc_depth'], 4)
        self.assertIn('Dicastery for the Doctrine of the Faith',
                      data['issued_by'])
        self.assertEqual(data['pontificate'], 'Francis')
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

    @needs_sources(quo_vadis_humanitas.EN_SRC)
    def test_quo_vadis_extracts_preliminary_note_and_first_footnote(self):
        data = quo_vadis_humanitas.extract()

        self.assertEqual(len(data['paragraphs']), 167)
        self.assertEqual(len(data['footnotes']), 200)
        self.assertEqual(data['issued_by'],
                         'International Theological Commission')
        self.assertEqual(data['pontificate'], 'Leo XIV')
        self.assertTrue(data['paragraphs'][0]['hide_number'])
        self.assertEqual(data['paragraphs'][0]['part_title'], 'Preliminary Note')
        self.assertEqual(data['footnotes'][0]['number'], 1)
        self.assertIn('*[Dignitas infinita]', data['footnotes'][0]['text'])
        self.assertEqual(
            next(p['section_title'] for p in data['paragraphs']
                 if p['section_title']),
            '1. The method of the document on the sixtieth anniversary of '
            'Gaudium et spes',
        )
        self.assertEqual(data['paragraphs'][-1]['chapter_title'], 'Conclusion')

    @needs_sources(fides_et_ratio.EN_SRC)
    def test_fides_et_ratio_canonicalises_legacy_footnote_scheme(self):
        data = fides_et_ratio.extract()

        self.assertEqual(len(data['paragraphs']), 110)
        self.assertEqual(len(data['footnotes']), 132)
        self.assertEqual(data['hue'], 8)
        self.assertEqual(data['pontificate'], 'John Paul II')
        self.assertEqual(data['signature'], '**JOHN PAUL II**')
        # Roman-numbered chapters are kept on the arabic path so the trailing
        # unnumbered Conclusion renders without a "Chapter N" prefix.
        self.assertNotEqual(data.get('chapter_style'), 'roman')
        self.assertEqual(data['paragraphs'][-1]['chapter_title'], 'Conclusion')
        # The apostolic-blessing greeting and the "two wings" epigraph open
        # the document as hidden-number prefatory prose.
        self.assertEqual(sum(p.get('hide_number', False)
                             for p in data['paragraphs']), 2)
        self.assertTrue(data['paragraphs'][0]['hide_number'])
        # The bespoke `$N`/`<sup>` footnote scheme must fully canonicalise:
        # no anchor names, superscript wrappers, or markdown-link tails leak.
        for note in (1, 10, 46, 132):
            self.assertTrue(any(f['number'] == note for f in data['footnotes']))
        for p in data['paragraphs']:
            self.assertNotIn('%24', p['text'])
            self.assertNotIn('<sup>', p['text'])
            self.assertNotIn('](#', p['text'])
        note_132 = next(f for f in data['footnotes'] if f['number'] == 132)
        self.assertNotIn('\n', note_132['text'])
        self.assertIn('“*He noera tes pisteos trapeza*”:', note_132['text'])
        note_28 = next(f for f in data['footnotes'] if f['number'] == 28)
        self.assertIn("“'What is man", note_28['text'])
        self.assertNotIn("“ 'What is man", note_28['text'])
        self.assertNotIn(
            'Copyright © Dicastery for Communication',
            data['paragraphs'][-1]['text'],
        )

    @needs_sources(lumen_fidei.EN_SRC)
    def test_lumen_fidei_unwraps_absolute_footnote_anchors(self):
        data = lumen_fidei.extract()

        self.assertEqual(len(data['paragraphs']), 60)
        self.assertEqual(len(data['footnotes']), 50)
        self.assertEqual(data['hue'], 48)
        self.assertEqual(data['pontificate'], 'Francis')
        self.assertEqual(data['signature'], '**FRANCISCUS**')
        # Scriptural chapter titles title-case but keep the lower-case "cf.".
        self.assertEqual(data['paragraphs'][0]['chapter'], 0)
        self.assertTrue(any(
            p['chapter_title'] == 'We Have Believed in Love (cf. 1 Jn 4:16)'
            for p in data['paragraphs']
        ))
        # Bold topical headers become auto-numbered sections.
        self.assertEqual(
            next(p['section_title'] for p in data['paragraphs']
                 if p['section_title']),
            'An illusory light?',
        )
        # Absolute-href footnote anchors must not survive as markdown links.
        for p in data['paragraphs']:
            self.assertNotIn('](#_ftn', p['text'])
        # The closing Marian prayer trails §60 unnumbered; the single-pass walk
        # folds it onto §60 in verse form (the earlier two-phase walk dropped
        # it). Pin it so the tail is never silently truncated again.
        para_60 = next(p for p in data['paragraphs'] if p['number'] == 60)
        self.assertIn('Mother, help our faith!', para_60['text'])
        self.assertTrue(para_60['text'].rstrip().endswith(
            'your Son, our Lord!'))

    @needs_sources(verbum_domini.EN_SRC)
    def test_verbum_domini_recovers_parts_and_loose_first_paragraph(self):
        data = verbum_domini.extract()

        self.assertEqual(len(data['paragraphs']), 124)
        self.assertEqual(len(data['footnotes']), 382)
        self.assertEqual(data['hue'], 200)
        self.assertEqual(data['pontificate'], 'Benedict XVI')
        self.assertEqual(data['signature'], '**BENEDICT XVI**')
        # §1 is loose inline text after the INTRODUCTION heading; recovered.
        first = data['paragraphs'][0]
        self.assertEqual(first['number'], 1)
        self.assertEqual(first['part'], 0)
        self.assertIn('abides for ever', first['text'])
        # Three parts with their Latin titles.
        self.assertEqual(
            [(p, t) for p, t in dict(
                (q['part'], q['part_title']) for q in data['paragraphs']
            ).items() if p],
            [(1, 'Verbum Dei'), (2, 'Verbum in Ecclesia'), (3, 'Verbum Mundo')],
        )
        # Trailing unnumbered Conclusion chapter under the last part.
        self.assertEqual(data['paragraphs'][-1]['chapter_title'], 'Conclusion')
        self.assertEqual(data['paragraphs'][-1]['part'], 3)


if __name__ == '__main__':
    unittest.main()
