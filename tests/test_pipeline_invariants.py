"""Pipeline invariants: bug classes every document must stay clean of.

Unlike the per-document regression tests in `test_extractors.py` (which pin
facts a specific walker once got wrong), these checks are generic: they run
over every implemented document discovered from the source manifest, so a
newly dropped extractor inherits every lesson with no registration.

Each invariant is a lesson from a real defect:

- *Unconverted bracket markers* — QVH's continuation blocks skipped the
  `[N]` → `(N)` pass, so seven citations rendered as literal brackets and
  never linkified.
- *Source junk in text* — Word-export non-breaking spaces survived
  `clean_text` (280 in MH, rendering as double spacing); F&R once leaked a
  copyright footer. Canonical text carries Markdown-compatible inline
  markup and `<sup>`/`<sub>` only.
- *Parenthetical edge spaces* — modern exports put tag-boundary whitespace
  inside citations (`( Gal 5:22)`); canonical text tightens both edges.
- *Paragraph continuity / folded markers* — the SC snapshot mislabels ¶87
  as "81."; the walker's out-of-sequence guard folded it into ¶86, stray
  marker and all. A gap in visible numbering or a continuation block
  opening with a near-successor number means a paragraph got swallowed.
- *Footnote resolution* — a definition nobody cites usually means the cite
  marker was dropped, not that the note is decorative (the QVH case);
  a cite without a definition is a broken link. Checks are scope-aware:
  GeS renumbers notes per part by design.
- *Note-count parity* — "route, don't drop": LF's closing prayer once
  vanished in an ad-hoc tail loop. For footnotes the generic proxy is that
  every definition anchor in the source arrives in the TOML.
- *Metadata completeness* — the catalogue and colophon render unconditionally
  from these fields; a missing one is a blank card, not an error.
"""

import importlib
import re
import unittest

from core import CANONICAL_FOOTNOTE_REF
from gen_doc_rules import implemented_docs

# Digits-only brackets: canonical refs are `(N)`, markdown links carry text.
BRACKET_MARKER = re.compile(r'\[\d{1,3}\]')

# Anything that should have been consumed or converted upstream. Canonical
# inline markup is `*em*`, `**strong**`, `<sup>`/`<sub>`, markdown links.
SOURCE_JUNK = re.compile(
    r'_ftn|_edn|\]\(#|<a\s|</a>|<i>|</i>|<b>|</b>|<br|<p>|<p\s'
    r'|&#\d+;|&nbsp;|\xa0'
)

PAREN_EDGE_SPACE = re.compile(r'\(\s|\s\)')

# A continuation block opening `N. ` where N is a plausible neighbour of the
# host paragraph's own number. Small N (≤9) are usually authored norm lists
# (SC ¶22); a near-successor two-digit N is a swallowed paragraph.
FOLDED_MARKER = re.compile(r'\n\n(\d{1,3})\.\s')

# Footnote definition anchors across the dialects: `_ftnN` (Word footnote
# exports), `_ednN` (Word endnote exports, CiV), `fnN` (EiO). `_ftnrefN` /
# `fnrefN` body cites don't match — the digit must follow immediately.
NOTE_DEF_ANCHOR = re.compile(r'name="(?:_ftn|_edn|fn)(\d{1,3})"')

REQUIRED_METADATA = (
    'name', 'hue', 'source_url', 'issued_by', 'date', 'identifier', 'desc',
)

# Holes in the vatican.va snapshots themselves. Everywhere else a failing
# invariant means the walker dropped something and the fix is in the
# extractor; here the text is simply not on the page, so there is nothing to
# recover and nothing to repair. Recording the defect keeps the invariant
# live — a *second* gap in the same chapter still fails — instead of
# switching the check off for the document. Each entry earns its place by
# being checked against the source by hand.
#
#   libertatis_nuntius — chapter VI runs 1, 2, 3, 4, 5, **7**, 8, 9, 10.
#     The missing ¶6 is simply not in the snapshot. (Its neighbour defect,
#     the same chapter's mis-typed `[19]` marker, *is* repairable and is
#     fixed in the extractor rather than recorded here.)
KNOWN_SOURCE_DEFECTS = {
    'libertatis_nuntius': {
        # (part, chapter, number) that legitimately never appears
        'paragraph_gap': {(0, 6, 6)},
    },
}


def _load_all():
    """slug → extracted dict, or None where the source snapshot is absent
    (`sources/` is gitignored; a fresh clone skips rather than errors)."""
    docs = {}
    for slug, _sources in implemented_docs():
        module = importlib.import_module(f'extract.{slug}')
        try:
            docs[slug] = module.extract()
        except FileNotFoundError:
            docs[slug] = None
    return docs


def text_fields(data):
    for p in data['paragraphs']:
        yield f'§{p["number"]}', p['text']
    for n in data['footnotes']:
        yield f'fn {n["number"]}', n['text']
    for i, a in enumerate(data.get('appendices', ()), 1):
        yield f'appendix {i}', a['text']
    for key in ('promulgation', 'signature', 'desc', 'desc_post'):
        if data.get(key):
            yield key, data[key]


class PipelineInvariantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.docs = _load_all()

    def for_each_doc(self, check):
        ran = 0
        for slug, data in self.docs.items():
            if data is None:
                continue
            ran += 1
            with self.subTest(doc=slug):
                check(slug, data)
        if not ran:
            self.skipTest('no source snapshots present — run download_sources.py')

    def test_no_unconverted_bracket_markers(self):
        def check(slug, data):
            for where, text in text_fields(data):
                m = BRACKET_MARKER.search(text)
                self.assertIsNone(
                    m, f'{where}: unconverted marker '
                    f'{m and text[max(0, m.start() - 40):m.end() + 10]!r}')
        self.for_each_doc(check)

    def test_no_source_junk_in_text(self):
        def check(slug, data):
            for where, text in text_fields(data):
                m = SOURCE_JUNK.search(text)
                self.assertIsNone(
                    m, f'{where}: source junk {m and m.group(0)!r} in '
                    f'{m and text[max(0, m.start() - 40):m.end() + 30]!r}')
        self.for_each_doc(check)

    def test_no_parenthetical_edge_spaces(self):
        def check(slug, data):
            for where, text in text_fields(data):
                m = PAREN_EDGE_SPACE.search(text)
                self.assertIsNone(
                    m, f'{where}: whitespace inside parenthesis near '
                    f'{m and text[max(0, m.start() - 30):m.end() + 30]!r}')
        self.for_each_doc(check)

    def test_visible_paragraph_numbering_is_continuous(self):
        def check(slug, data):
            gaps = KNOWN_SOURCE_DEFECTS.get(slug, {}).get('paragraph_gap', set())
            visible = [p for p in data['paragraphs'] if not p.get('hide_number')]
            self.assertTrue(visible, 'no visible paragraphs')

            def run_is_continuous(nums, where, part=0, chapter=0):
                self.assertEqual(
                    nums[0], 1, f'{where}: first visible paragraph is not §1')
                for prev, cur in zip(nums, nums[1:]):
                    expected = prev + 1
                    while (part, chapter, expected) in gaps:
                        expected += 1  # documented hole in the source
                    self.assertEqual(
                        cur, expected,
                        f'{where}: paragraph numbering jumps §{prev} → §{cur}')

            if data.get('layout', {}).get('chapter_numbering'):
                # Numbers are chapter-scoped, so continuity is too: each
                # chapter must open at §1 and run unbroken to its own end.
                runs = {}
                for p in visible:
                    runs.setdefault((p['part'], p['chapter']), []).append(
                        p['number'])
                for (part, chapter), nums in runs.items():
                    run_is_continuous(
                        nums, f'part {part} chapter {chapter}', part, chapter)
            else:
                run_is_continuous([p['number'] for p in visible], 'document')
        self.for_each_doc(check)

    def test_no_folded_paragraph_markers_in_continuations(self):
        def check(slug, data):
            max_num = max(p['number'] for p in data['paragraphs'])
            for p in data['paragraphs']:
                for m in FOLDED_MARKER.finditer(p['text']):
                    n = int(m.group(1))
                    self.assertFalse(
                        n > 9 and abs(n - p['number']) <= 3
                        and n <= max_num + 3,
                        f'§{p["number"]}: continuation opens with '
                        f'{p["text"][m.start():m.start() + 60]!r} — '
                        f'a swallowed paragraph?')
        self.for_each_doc(check)

    def test_no_note_is_cited_from_two_paragraphs(self):
        """In a globally-numbered document, a note number used twice is a
        mistyped marker rather than a reused citation.

        Measured across the corpus: of the fourteen documents that number
        notes globally, exactly one had a repeat, and it was a defect (MH's
        §82 carried a stray anchorless `<sup>[10]</sup>` nested inside the
        superscript holding the real `[110]`). LN's `[19]`-for-`[20]` was
        the same shape. The paired signature — one number cited twice while
        another note is uncited — is all but diagnostic.

        The check applies only where note numbers identify a note on their
        own. GeS renumbers per chapter (167 notes across 34 numbers) and so
        cites a given number from many paragraphs by design; scoping the key
        to its chapter would make the check vacuous for every other
        document, since a mistyped marker usually lands in a *different*
        chapter from the number's rightful cite — which is precisely how MH
        hid. So GeS opts out on a property read from its own data, not a
        slug list, and keeps the coverage of the scope-aware resolution
        invariant below.
        """
        def check(slug, data):
            notes = data['footnotes']
            if len({n['number'] for n in notes}) != len(notes):
                self.skipTest('notes are renumbered per scope, not global')
            citers = {}
            for p in data['paragraphs']:
                for n in set(CANONICAL_FOOTNOTE_REF.findall(p['text'])):
                    citers.setdefault(int(n), []).append(p)
            for number, paragraphs in sorted(citers.items()):
                if len(paragraphs) < 2:
                    continue
                context = []
                for p in paragraphs:
                    i = p['text'].find(f'({number})')
                    context.append(
                        f'§{p["number"]} '
                        f'{p["text"][max(0, i - 60):i + 5]!r}')
                self.fail(
                    f'note {number} is cited from '
                    f'{len(paragraphs)} paragraphs — a mistyped marker? '
                    + ' … '.join(context))
        self.for_each_doc(check)

    def test_footnote_cites_and_definitions_resolve(self):
        def check(slug, data):
            cited_by_part = {}
            for p in data['paragraphs']:
                for n in CANONICAL_FOOTNOTE_REF.findall(p['text']):
                    cited_by_part.setdefault(p['part'], set()).add(int(n))
            all_cited = set().union(*cited_by_part.values()) \
                if cited_by_part else set()
            defined = {n['number'] for n in data['footnotes']}
            self.assertEqual(
                all_cited - defined, set(),
                'cites with no definition (broken links)')
            uncited_ok = KNOWN_SOURCE_DEFECTS.get(slug, {}).get(
                'uncited_note', set())
            for note in data['footnotes']:
                part_cites = cited_by_part.get(note['part'], set())
                self.assertTrue(
                    note['number'] in part_cites
                    or note['number'] in all_cited
                    or note['number'] in uncited_ok,
                    f'fn {note["number"]} (part {note["part"]}) is never '
                    f'cited — dropped cite marker?')
        self.for_each_doc(check)

    def test_source_note_definitions_all_arrive(self):
        def check(slug, data):
            module = importlib.import_module(f'extract.{slug}')
            src = getattr(module, 'EN_SRC', None)
            if src is None or not src.exists():
                return
            anchors = {
                int(n) for n in
                NOTE_DEF_ANCHOR.findall(src.read_bytes().decode('latin-1'))
            }
            if not anchors:
                return  # dialect without definition anchors (old flat, FeR)
            toml_notes = {(n['part'], n['chapter'], n['number'])
                          for n in data['footnotes']}
            self.assertEqual(
                len(toml_notes), len(anchors),
                f'source has {len(anchors)} note anchors, '
                f'TOML has {len(toml_notes)} footnotes')
        self.for_each_doc(check)

    def test_emphasis_markers_are_balanced(self):
        def check(slug, data):
            for where, text in text_fields(data):
                self.assertEqual(
                    text.count('*') % 2, 0,
                    f'{where}: odd asterisk count breaks emphasis pairing')
        self.for_each_doc(check)

    def test_no_empty_reading_regions(self):
        def check(slug, data):
            for p in data['paragraphs']:
                self.assertTrue(p['text'].strip(), f'§{p["number"]}: empty text')
            for i, a in enumerate(data.get('appendices', ()), 1):
                self.assertTrue(a['title'].strip(), f'appendix {i}: no title')
                self.assertTrue(a['text'].strip(), f'appendix {i}: empty text')
        self.for_each_doc(check)

    def test_catalogue_metadata_is_complete(self):
        def check(slug, data):
            for key in REQUIRED_METADATA:
                self.assertTrue(data.get(key), f'missing metadata: {key}')
            self.assertRegex(data['date'], r'^\d{4}-\d{2}-\d{2}$')
        self.for_each_doc(check)


if __name__ == '__main__':
    unittest.main()
