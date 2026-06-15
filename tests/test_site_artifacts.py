import os
import re
import tomllib
import unittest
import zipfile
from html import escape

import make_index
from project import BUILD, DOWNLOADS, ROOT, SITE


STRICT = os.environ.get('VA_REQUIRE_SITE_ARTIFACTS') == '1'
FOOTNOTE_REF_RE = re.compile(r'\((\d{1,3})\)')


def _makefile_docs():
    lines = (ROOT / 'Makefile').read_text(encoding='utf-8').splitlines()
    chunks = []
    in_docs = False
    for line in lines:
        if line.startswith('DOCS'):
            in_docs = True
            chunks.append(line.split(':=', 1)[1])
        elif in_docs and line.startswith((' ', '\t')):
            chunks.append(line)
        elif in_docs:
            break
    return tuple(' '.join(chunks).replace('\\', '').split())


DOCS = _makefile_docs()


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
    return str(path.relative_to(ROOT))


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

    def test_makefile_docs_and_card_meta_stay_in_sync(self):
        self.assertEqual(set(DOCS), set(make_index.CARD_META))

    def test_reader_html_has_navigation_and_no_known_markup_leaks(self):
        for slug in DOCS:
            with self.subTest(slug=slug):
                data = _load_toml(slug)
                html = (SITE / f'{slug}.html').read_text(encoding='utf-8')

                self.assertIn(f'<body class="doc-{slug}"', html)
                self.assertIn(
                    f'<p class="doc-name">{escape(data["name"])}</p>',
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
