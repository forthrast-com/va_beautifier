import unittest

from extract import (
    antiqua_et_nova,
    caritas_in_veritate,
    deus_caritas_est,
    ecclesia_in_oceania,
    fides_et_ratio,
    fratelli_tutti,
    gaudium_et_spes,
    laudato_si,
    lumen_fidei,
    magnifica_humanitas,
    quo_vadis_humanitas,
    sacrosanctum_concilium,
    spe_salvi,
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
        # The snapshot mislabels ¶87 as "81."; the load-time repair keeps it
        # a paragraph of its own instead of folding into ¶86.
        p86, p87 = (next(p for p in data['paragraphs'] if p['number'] == n)
                    for n in (86, 87))
        self.assertTrue(p87['text'].startswith(
            'In order that the divine office may be better'))
        self.assertNotIn('divine office may be better', p86['text'])
        self.assertEqual(len(data['appendices']), 1)
        self.assertEqual(data['appendices'][0]['kind'], 'declaration')
        self.assertIn('1. The Sacred Council would not object',
                      data['appendices'][0]['text'])
        para_77 = next(p for p in data['paragraphs'] if p['number'] == 77)
        self.assertIn(
            '\n\n> If any regions are wont to use other praiseworthy customs',
            para_77['text'],
        )
        self.assertIn('retained(41).', para_77['text'])
        self.assertNotIn('> "If any regions', para_77['text'])

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
        # Continuation blocks get the same [N] → (N) pass as first blocks;
        # notes 12/27/28/41/192–194 previously stayed bracketed (uncited).
        for p in data['paragraphs']:
            self.assertNotRegex(p['text'], r'\[\d{1,3}\]')
        self.assertIn('(192)', next(
            p['text'] for p in data['paragraphs']
            if 'born of the Holy Spirit' in p['text']
        ))

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
        paragraphs = {p['number']: p for p in data['paragraphs']}
        self.assertIn(
            '\n\n> Wisdom knows all and understands all\n>\n'
            '> — *Wis* 9:11',
            paragraphs[15]['text'],
        )
        self.assertIn(
            '\n\n> Acquire wisdom, acquire understanding\n>\n'
            '> — *Prov* 4:5',
            paragraphs[20]['text'],
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
        # The closing Marian prayer trails §60 as a source blockquote; the
        # single-pass walk folds it onto §60 as canonical italic verse (the
        # earlier two-phase walk dropped it). Pin it so the tail is never
        # silently truncated or flattened again.
        para_60 = next(p for p in data['paragraphs'] if p['number'] == 60)
        self.assertIn('*Mother, help our faith!', para_60['text'])
        self.assertTrue(para_60['text'].rstrip().endswith(
            'your Son, our Lord!*'))

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
        part_two = next(p for p in data['paragraphs'] if p['number'] == 50)
        self.assertIn(
            'But to all who received him he gave power',
            part_two['part_subtitle'],
        )
        self.assertTrue(part_two['part_subtitle'].rstrip().endswith(
            '> — *Jn* 1:12'
        ))
        self.assertEqual(part_two['section'], 1)
        self.assertEqual(part_two['section_title'], 'The Church receives the word')
        para_49 = next(p for p in data['paragraphs'] if p['number'] == 49)
        self.assertNotIn('The Church receives the word', para_49['text'])
        para_37 = next(p for p in data['paragraphs'] if p['number'] == 37)
        self.assertIn('\n\n> *Littera gesta docet', para_37['text'])
        self.assertIn('anagogy about our destiny.(122)', para_37['text'])
        self.assertNotIn('> “*Littera', para_37['text'])
        # Trailing unnumbered Conclusion chapter under the last part.
        self.assertEqual(data['paragraphs'][-1]['chapter_title'], 'Conclusion')
        self.assertEqual(data['paragraphs'][-1]['part'], 3)

    @needs_sources(deus_caritas_est.EN_SRC)
    def test_deus_caritas_est_joins_split_part_title(self):
        data = deus_caritas_est.extract()

        self.assertEqual(len(data['paragraphs']), 42)
        self.assertEqual(len(data['footnotes']), 36)
        self.assertEqual(data['hue'], 354)
        self.assertEqual(data['pontificate'], 'Benedict XVI')
        self.assertEqual(data['signature'], '**BENEDICTUS PP. XVI**')
        # INTRODUCTION opens an authored part-0 group.
        self.assertEqual(data['paragraphs'][0]['part'], 0)
        self.assertEqual(data['paragraphs'][0]['part_title'], 'Introduction')
        # Part II spreads "CARITAS" onto its own centred line ahead of the
        # descriptive title; the fragments join with a colon, and the quoted
        # title noun keeps its capital despite title_case's quote handling.
        part_titles = dict(
            (p['part'], p['part_title']) for p in data['paragraphs'] if p['part']
        )
        self.assertEqual(
            part_titles[1],
            'The Unity of Love in Creation and in Salvation History',
        )
        self.assertEqual(
            part_titles[2],
            'Caritas: The Practice of Love by the Church as a '
            '“Community of Love”',
        )
        # Within each part the italic topical headers are bare chapters (the
        # document's H2-level divisions), opening Part II's run and resetting
        # per part. Conclusion is the trailing bare chapter.
        chapters = [(p['part'], p['chapter'], p['chapter_title'])
                    for p in data['paragraphs'] if p['chapter']]
        self.assertIn((1, 1, 'A problem of language'), chapters)
        self.assertIn((2, 2, 'Charity as a responsibility of the Church'),
                      chapters)
        self.assertEqual(data['paragraphs'][-1]['chapter_title'], 'Conclusion')
        for p in data['paragraphs']:
            self.assertNotIn('](#', p['text'])
        # The closing Marian prayer trails §42 as a source <blockquote>; like
        # Lumen Fidei it folds onto the paragraph as canonical italic verse.
        para_42 = next(p for p in data['paragraphs'] if p['number'] == 42)
        self.assertIn('*Holy Mary, Mother of God,', para_42['text'])
        self.assertTrue(para_42['text'].rstrip().endswith('thirsting world.*'))

    @needs_sources(spe_salvi.EN_SRC)
    def test_spe_salvi_maps_bold_headers_and_roman_subsections(self):
        data = spe_salvi.extract()

        self.assertEqual(len(data['paragraphs']), 50)
        self.assertEqual(len(data['footnotes']), 40)
        self.assertEqual(data['hue'], 150)
        self.assertEqual(data['pontificate'], 'Benedict XVI')
        self.assertEqual(data['signature'], '**BENEDICTUS PP. XVI**')
        # Introduction opens the part-0 group.
        self.assertEqual(data['paragraphs'][0]['part'], 0)
        self.assertEqual(data['paragraphs'][0]['part_title'], 'Introduction')
        # The bold topical headers are the document's primary divisions, so
        # they drive the (bare) chapter tier — eight of them, opening with
        # "Faith is Hope".
        chapters = sorted({(p['chapter'], p['chapter_title'])
                           for p in data['paragraphs'] if p['chapter']})
        self.assertEqual(len(chapters), 8)
        self.assertEqual(chapters[0], (1, 'Faith is Hope'))
        self.assertEqual(chapters[-1], (8, 'Mary, Star of Hope'))
        # The "Settings" chapter's centred-bold Roman subsections become its
        # sections, kept verbatim (numeral and all). No deeper sub-heading
        # tier is used.
        sections = [p['section_title'] for p in data['paragraphs']
                    if p['section']]
        self.assertIn('I. Prayer as a school of hope', sections)
        self.assertIn('III. Judgement as a setting for learning and '
                      'practising hope', sections)
        self.assertFalse(any(p['sub_heading'] for p in data['paragraphs']))
        for p in data['paragraphs']:
            self.assertNotIn('](#', p['text'])

    @needs_sources(caritas_in_veritate.EN_SRC)
    def test_caritas_in_veritate_canonicalises_endnote_scheme(self):
        data = caritas_in_veritate.extract()

        self.assertEqual(len(data['paragraphs']), 79)
        self.assertEqual(len(data['footnotes']), 159)
        self.assertEqual(data['hue'], 28)
        self.assertEqual(data['pontificate'], 'Benedict XVI')
        self.assertEqual(data['signature'], '**BENEDICTUS PP. XVI**')
        # Six word-marked chapters plus a trailing unnumbered Conclusion; the
        # part-0 "Introduction" label must not bleed onto the chapters.
        self.assertEqual(
            next(p['chapter_title'] for p in data['paragraphs']
                 if p['chapter'] == 1),
            'The Message of Populorum Progressio',
        )
        # Chapter 4's <br/>-stacked list heading gets its commas repaired.
        self.assertEqual(
            next(p['chapter_title'] for p in data['paragraphs']
                 if p['chapter'] == 4),
            'The Development of People, Rights and Duties, the Environment',
        )
        self.assertEqual(data['paragraphs'][-1]['chapter_title'], 'Conclusion')
        self.assertTrue(all(
            p['part_title'] == '' for p in data['paragraphs'] if p['chapter']
        ))
        # The Word *endnote* export (`_edn` anchors) must fully canonicalise:
        # no markdown-link tails or anchor names leak into body or notes.
        for note in (1, 17, 159):
            self.assertTrue(any(f['number'] == note for f in data['footnotes']))
        for p in data['paragraphs']:
            self.assertNotIn('](#', p['text'])
            self.assertNotIn('_edn', p['text'])

    @needs_sources(fratelli_tutti.EN_SRC)
    def test_fratelli_tutti_repairs_broken_note_markers(self):
        data = fratelli_tutti.extract()

        self.assertEqual(len(data['paragraphs']), 287)
        self.assertEqual(len(data['footnotes']), 288)
        self.assertEqual(data['pontificate'], 'Francis')
        self.assertEqual(data['signature'], 'Franciscus')
        self.assertIn('Given in Assisi', data['promulgation'])
        # Non-bold centred chapter titles; all-caps anchor headings become
        # bare sections, with italic headings as their finer sub-heading tier.
        self.assertEqual(
            next(p['chapter_title'] for p in data['paragraphs']
                 if p['chapter'] == 1),
            'Dark Clouds Over a Closed World',
        )
        paragraphs = {p['number']: p for p in data['paragraphs']}
        self.assertEqual(paragraphs[3]['section_title'], 'Without Borders')
        self.assertEqual(paragraphs[10]['section_title'], 'Shattered Dreams')
        self.assertEqual(paragraphs[13]['section_title'], 'Shattered Dreams')
        self.assertEqual(paragraphs[13]['sub_heading'],
                         'The end of historical consciousness')
        self.assertEqual(paragraphs[15]['section_title'],
                         'Lacking a Plan for Everyone')
        self.assertNotIn('SHATTERED DREAMS', paragraphs[9]['text'])
        # Long source quotations become semantic blockquotes. Scripture cites
        # stay attached as citation lines; redundant outer quote marks go.
        self.assertIn('\n\n> Just then a lawyer stood up',
                      paragraphs[56]['text'])
        self.assertIn('\n>\n> — *Lk* 10:25–37', paragraphs[56]['text'])
        self.assertNotIn('> “Just then', paragraphs[56]['text'])
        self.assertIn('\n\n> You shall not wrong or oppress a stranger',
                      paragraphs[61]['text'])
        self.assertIn('\n>\n> — *Ex* 22:21', paragraphs[61]['text'])
        self.assertIn('\n>\n> — Lev 19:33–34', paragraphs[61]['text'])
        self.assertIn('\n\n> In the name of God,', paragraphs[285]['text'])
        self.assertIn('\n>\n> In the name of innocent human life',
                      paragraphs[285]['text'])
        self.assertNotIn('> “In the name', paragraphs[285]['text'])
        self.assertIn('method and standard.(285)', paragraphs[285]['text'])
        # Francis's long self-citations remain authored prose, not detached
        # source blocks masquerading as scripture or external testimony.
        self.assertFalse(paragraphs[227]['text'].startswith('> '))
        self.assertFalse(paragraphs[268]['text'].startswith('> '))
        # Two titled prayers arrive as appendices (the LS-shaped tail).
        self.assertEqual(
            [a['title'] for a in data['appendices']],
            ['A Prayer to the Creator', 'An Ecumenical Christian Prayer'],
        )
        # Source note defects: 86/112/185 lose their opening bracket,
        # 98's marker is glued to its text, and 119's definition shares
        # note 118's <p>. All five must arrive, unglued.
        notes = {n['number']: n['text'] for n in data['footnotes']}
        for n in (86, 98, 112, 185):
            self.assertIn(n, notes)
        self.assertTrue(
            notes[119].startswith('*[Document on Human Fraternity'))
        self.assertNotIn('Document on Human Fraternity', notes[118])

    @needs_sources(ecclesia_in_oceania.EN_SRC)
    def test_ecclesia_in_oceania_recovers_italic_wrapped_note(self):
        data = ecclesia_in_oceania.extract()

        self.assertEqual(len(data['paragraphs']), 53)
        self.assertEqual(len(data['footnotes']), 178)
        self.assertEqual(data['hue'], 212)
        self.assertEqual(data['pontificate'], 'John Paul II')
        self.assertEqual(data['signature'], '**JOANNES PAULUS PP. II**')
        # Four Roman chapters parsed to arabic + trailing Conclusion.
        self.assertEqual(
            next(p['chapter_title'] for p in data['paragraphs']
                 if p['chapter'] == 1),
            'Jesus Christ and the Peoples of Oceania',
        )
        self.assertEqual(data['paragraphs'][-1]['chapter_title'], 'Conclusion')
        # Note 21's leading `(21)` is wrapped in the same <i> the source opens
        # for "Propositio"; keying off the marker recovers it rather than
        # dropping it (177 of 178 before the fix).
        self.assertEqual(len({f['number'] for f in data['footnotes']}), 178)
        note_21 = next(f for f in data['footnotes'] if f['number'] == 21)
        self.assertEqual(note_21['text'], 'Cf. Propositio 44.')
        # Italic-only headers are a sub-heading tier (previously folded into
        # prose and lost).
        subs = {p['sub_heading'] for p in data['paragraphs'] if p['sub_heading']}
        self.assertIn('The Permanent Diaconate', subs)
        self.assertIn('Mary our Mother', subs)
        # The titled closing prayer is lifted into its own prayer appendix,
        # not mashed into the conclusion's last paragraph.
        prayers = [a for a in data['appendices'] if a.get('kind') == 'prayer']
        self.assertEqual(len(prayers), 1)
        self.assertEqual(prayers[0]['title'], 'Prayer')
        self.assertTrue(prayers[0]['text'].startswith('O Mary, Help of Christians,'))
        self.assertIn('Bright Star of the Sea', prayers[0]['text'])
        # The prayer verse lives only in the appendix, not folded into prose.
        self.assertFalse(any('Bright Star of the Sea' in p['text']
                             for p in data['paragraphs']))
        # Split `fn`/`fnref` cite anchors must collapse to canonical `(N)`,
        # leaving no markdown-link tails in the body.
        for p in data['paragraphs']:
            self.assertNotIn('](#', p['text'])
        paragraphs = {p['number']: p for p in data['paragraphs']}
        expected_scripture = {
            2: '*Mt* 4:18–20',
            9: '*Mt* 4:21–22',
            17: '*Lk* 5:1–3',
            35: '*Lk* 5:4–7',
        }
        for number, citation in expected_scripture.items():
            self.assertIn(f'> — {citation}', paragraphs[number]['text'])
            self.assertNotRegex(paragraphs[number]['text'], r'> [“"]')


if __name__ == '__main__':
    unittest.main()
