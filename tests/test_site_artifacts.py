import json
import os
import re
import tomllib
import unittest
import zipfile
from html import escape

from core import is_unnumbered_chapter
from gen_doc_rules import implemented_docs
import make_index
from project import BUILD, DOWNLOADS, SITE


STRICT = os.environ.get('VA_REQUIRE_SITE_ARTIFACTS') == '1'
# Mirror core.CANONICAL_FOOTNOTE_REF: a `(N)` glued to a preceding digit is
# Psalm dual-numbering (`Ps 73(72)`), not a footnote cite.
FOOTNOTE_REF_RE = re.compile(r'(?<!\d)\((\d{1,3})\)')


def _implemented_docs():
    """Every implemented slug, from the manifest the build itself derives from.

    This used to scrape a `DOCS :=` assignment out of the Makefile. `DOCS`
    later moved into the generated `build/docs.mk`, so the scrape silently
    started returning `()` — and since every check below is a loop over it,
    the whole artefact QA quietly became a no-op that still reported OK.
    Read the same source `gen_doc_rules` writes the Makefile fragment from,
    so the list cannot go stale again, and assert it is non-empty so the
    next such break fails instead of passing vacuously.
    """
    slugs = tuple(slug for slug, _sources in implemented_docs())
    if not slugs:
        raise AssertionError('no implemented documents discovered')
    return slugs


DOCS = _implemented_docs()


def _required_paths():
    paths = [SITE / 'index.html']
    for slug in DOCS:
        paths.extend([
            BUILD / f'{slug}.toml',
            SITE / f'{slug}.html',
            DOWNLOADS / f'{slug}.epub',
            DOWNLOADS / f'{slug}-a4.pdf',
            DOWNLOADS / f'{slug}-a5.pdf',
            DOWNLOADS / f'{slug}-a6.pdf',
        ])
    return paths


def _rel(path):
    return str(path)


def _load_toml(slug):
    with (BUILD / f'{slug}.toml').open('rb') as source:
        return tomllib.load(source)


def _epub_text(slug):
    path = DOWNLOADS / f'{slug}.epub'
    with zipfile.ZipFile(path) as epub:
        names = [
            name for name in epub.namelist()
            if name.endswith(('.xhtml', '.opf'))
        ]
        return '\n'.join(
            epub.read(name).decode('utf-8', errors='replace')
            for name in names
        )


class GeneratedSiteArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        missing = [path for path in _required_paths() if not path.exists()]
        if missing:
            shown = ', '.join(_rel(path) for path in missing[:8])
            more = '' if len(missing) <= 8 else f' (+{len(missing) - 8} more)'
            message = f'generated artefacts missing: {shown}{more}'
            if STRICT:
                raise AssertionError(message)
            raise unittest.SkipTest(
                message + '; run nix develop --command make qa'
            )

    def test_index_has_expected_controls_and_repo_links(self):
        html = (SITE / 'index.html').read_text(encoding='utf-8')

        self.assertIn(
            'https://github.com/forthrast-com/va_beautifier',
            html,
        )
        self.assertNotIn('href="https://github.com/forthrast-com"', html)
        for key, label, _default, _reversed in make_index.SORT_FIELDS:
            with self.subTest(sort=key):
                self.assertIn(f'data-sort="{key}"', html)
                self.assertIn(f'>{label}</button>', html)

        for slug in DOCS:
            with self.subTest(slug=slug):
                self.assertIn(f'href="{slug}.html"', html)
                self.assertIn(f'href="downloads/{slug}.epub"', html)
                self.assertIn(f'href="downloads/{slug}-a4.pdf"', html)
                self.assertIn(f'href="downloads/{slug}-a5.pdf"', html)
                self.assertIn(f'href="downloads/{slug}-a6.pdf"', html)

    def test_makefile_docs_have_catalogue_tile_metadata(self):
        for slug in DOCS:
            with self.subTest(slug=slug):
                data = _load_toml(slug)
                self.assertIn(data.get('type'), make_index.TILE_KIND_LABEL)
                self.assertIn(data.get('type'), make_index.AUTHORITY_RANK)
                if data.get('type') == 'council_constitution':
                    self.assertTrue(data.get('kind_long'))
                else:
                    self.assertTrue(data.get('subtitle'))

    def test_no_footnote_cite_links_to_a_missing_note(self):
        """Every `#fn-…` anchor must have an element to land on.

        GeS §62 cites (16) in a chapter whose source note block stops at 15;
        the renderer minted an id for it anyway and shipped a link to
        nothing. Unresolvable cites now render as a bare numeral, so any
        surviving `#fn-` href must resolve.
        """
        href = re.compile(r'href="#(fn-[^"]+)"')
        for slug in DOCS:
            with self.subTest(doc=slug):
                html = (SITE / f'{slug}.html').read_text(encoding='utf-8')
                ids = set(re.findall(r'id="(fn-[^"]+)"', html))
                dangling = sorted({t for t in href.findall(html) if t not in ids})
                self.assertEqual(dangling, [], 'footnote links with no target')

    def test_indicator_marks_exactly_one_place_per_reading_element(self):
        """Simulate the scroll indicator's "you are here" resolution.

        `assets/scripts.js` picks the active bar with
        `paraToChIdx[readingKey(el)]` and lights a seg when
        `seg.key === key` or `first <= key <= last`. Both must resolve to
        exactly one bar and one seg for every scrollable element, or the
        rail marks two places at once (or none). Keying on paragraph
        *numbers* used to make that fragile — a document whose numbering
        restarts each chapter has overlapping ranges — so the seg ranges are
        paragraph ordinals, and this pins the property that motivated the
        change.
        """
        para_el = re.compile(
            r'<div class="paragraph" id="([^"]+)" data-ord="(\d+)"')
        appendix_el = re.compile(r'<[^>]*class="appendix"[^>]*id="([^"]+)"')
        indicator = re.compile(r'^const chapters = (\[.*?\]);$', re.M)

        for slug in DOCS:
            with self.subTest(doc=slug):
                html = (SITE / f'{slug}.html').read_text(encoding='utf-8')
                match = indicator.search(html)
                self.assertIsNotNone(match, 'no indicator JSON in reader')
                chapters = json.loads(match.group(1))

                bar_of = {}
                for index, chapter in enumerate(chapters):
                    for key in chapter['paras']:
                        self.assertNotIn(
                            str(key), bar_of,
                            f'reading key {key!r} claimed by two bars')
                        bar_of[str(key)] = index

                elements = [(m.group(1), m.group(2))
                            for m in para_el.finditer(html)]
                elements += [(m.group(1), m.group(1))
                             for m in appendix_el.finditer(html)]
                self.assertTrue(elements, 'no reading elements found')

                for element_id, key in elements:
                    bar = bar_of.get(key)
                    self.assertIsNotNone(
                        bar, f'{element_id}: key {key!r} maps to no bar')
                    lit = [
                        seg for seg in chapters[bar].get('segs', ())
                        if (seg['key'] == key if 'key' in seg
                            else seg['first'] <= int(key) <= seg['last'])
                    ]
                    self.assertEqual(
                        len(lit), 1,
                        f'{element_id}: {len(lit)} segs light up on its own '
                        f'bar {bar} — expected exactly one')

    def test_web_and_book_agree_on_title_only_chapters(self):
        """Both renderers must honour `core.is_unnumbered_chapter`.

        It exists precisely so the two surfaces cannot disagree about which
        chapters render title-only — and they disagreed anyway, because both
        callers branched on `chapter_style` *before* consulting it, so a
        roman-style document printed `XII. Conclusion` in the book against a
        bare `Conclusion` on the web. Compare each surface against the
        shared helper rather than against each other, so a failure names the
        renderer that drifted.
        """
        for slug in DOCS:
            with self.subTest(doc=slug):
                data = _load_toml(slug)
                chapter_style = data.get('chapter_style', '')
                bare_chapters = bool(data.get('layout', {}).get('bare_chapters'))

                titles = {}
                for p in data['paragraphs']:
                    if p.get('chapter') and p.get('chapter_title'):
                        titles.setdefault(p['chapter'], p['chapter_title'])
                expected = {
                    title for title in titles.values()
                    if is_unnumbered_chapter(
                        title, chapter_style=chapter_style,
                        bare_chapters=bare_chapters)
                }

                # Web: a title-only chapter carries no `data-ch-num`, which
                # is what the sticky bar renders beside the heading.
                html = (SITE / f'{slug}.html').read_text(encoding='utf-8')
                web_bare = {
                    escape(title) for title in titles.values()
                    if f'class="chapter-title">{escape(title)}<' in html
                    and f'data-ch-num="{escape(title)}"' not in html
                    and re.search(
                        r'<h\d[^>]*data-sticky(?![^>]*data-ch-num)[^>]*'
                        r'class="chapter-title">' + re.escape(escape(title)),
                        html)
                }
                self.assertEqual(
                    web_bare, {escape(t) for t in expected},
                    'reader disagrees with core.is_unnumbered_chapter')

                # Book: the `## ` heading is the bare title, with no
                # `Chapter N: ` or roman `N. ` prefix.
                markdown = (BUILD / f'{slug}.md').read_text(encoding='utf-8')
                headings = set(re.findall(r'^## (.*)$', markdown, re.M))
                book_bare = {t for t in titles.values() if t in headings}
                self.assertEqual(
                    book_bare, expected,
                    'book disagrees with core.is_unnumbered_chapter')

    def test_reader_html_has_navigation_and_no_known_markup_leaks(self):
        for slug in DOCS:
            with self.subTest(slug=slug):
                data = _load_toml(slug)
                html = (SITE / f'{slug}.html').read_text(encoding='utf-8')

                # doc-<slug> always leads the class list; layout-* flag classes
                # (from the [layout] TOML table) may follow, so don't anchor on
                # the closing quote.
                self.assertIn(f'<body class="doc-{slug}', html)
                # The doc title is the page's single h1 (a11y, 2026-07).
                # This asserted a <p> until the DOCS list was repaired and
                # the check actually started running again.
                self.assertIn(
                    f'<h1 class="doc-name">{escape(data["name"])}</h1>',
                    html,
                )
                self.assertIn('id="fn-drawer"', html)
                self.assertIn('id="drawer-toc"', html)
                self.assertIn('id="drawer-footnotes"', html)
                self.assertIn(
                    'https://github.com/forthrast-com/va_beautifier',
                    html,
                )
                self.assertNotIn('href="https://github.com/forthrast-com"', html)
                self.assertNotIn('</strong></em>', html)
                self.assertNotIn('href="/content/', html)
                self.assertNotIn('*My Venerable', html)

    def test_toml_body_refs_match_footnotes_and_no_anchor_syntax_leaks(self):
        for slug in DOCS:
            with self.subTest(slug=slug):
                data = _load_toml(slug)
                paragraphs = data.get('paragraphs', [])
                footnotes = data.get('footnotes', [])

                self.assertTrue(paragraphs)
                self.assertTrue(data.get('desc'))

                refs = {
                    int(number)
                    for paragraph in paragraphs
                    for number in FOOTNOTE_REF_RE.findall(paragraph['text'])
                }
                note_nums = {footnote['number'] for footnote in footnotes}
                self.assertEqual(refs - note_nums, set())

                for paragraph in paragraphs:
                    text = paragraph['text']
                    self.assertNotIn('%24', text)
                    self.assertNotIn('<sup><a', text)
                    self.assertNotIn('](#_ftn', text)

    def test_downloads_exist_and_have_substance(self):
        for slug in DOCS:
            for suffix in ('.epub', '-a4.pdf', '-a5.pdf', '-a6.pdf'):
                with self.subTest(slug=slug, suffix=suffix):
                    path = DOWNLOADS / f'{slug}{suffix}'
                    self.assertGreater(
                        path.stat().st_size,
                        1024,
                        f'{_rel(path)} is suspiciously small',
                    )

    def test_epub_has_no_known_link_or_markup_leaks(self):
        for slug in DOCS:
            with self.subTest(slug=slug):
                text = _epub_text(slug)
                self.assertNotIn('href="/content/', text)
                self.assertNotIn('](/content/', text)
                self.assertNotIn('</strong></em>', text)
                self.assertNotIn('*My Venerable', text)


if __name__ == '__main__':
    unittest.main()
