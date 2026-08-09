import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import download_sources


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return b'<html>source</html>'


class ManifestTests(unittest.TestCase):
    def test_categories_include_queued_and_remaining_reference_sources(self):
        queued = download_sources.selected_sources([], 'queued')
        reference = download_sources.selected_sources([], 'reference')
        implemented = download_sources.selected_sources([], 'implemented')

        self.assertEqual(
            {source.key for source in queued},
            set(),
        )
        self.assertEqual(
            {source.key for source in reference},
            {'francis_g7_ai_en'},
        )
        self.assertTrue({
            'antiqua_et_nova_en',
            'fratelli_tutti_en',
            'quo_vadis_humanitas_en',
            'sacrosanctum_concilium_en',
            'sacrosanctum_concilium_lt',
        }.issubset({source.key for source in implemented}))

    def test_explicit_keys_preserve_requested_order(self):
        sources = download_sources.selected_sources(
            ['magnifica_humanitas_en', 'gaudium_et_spes_en'], None
        )

        self.assertEqual(
            [source.key for source in sources],
            ['magnifica_humanitas_en', 'gaudium_et_spes_en'],
        )


class DownloadTests(unittest.TestCase):
    def test_download_writes_atomically_and_skips_existing_file(self):
        source = download_sources.Source(
            'sample', 'sample.html', 'https://example.test/sample',
            'reference', 'Sample',
        )
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / source.filename
            with patch.object(download_sources, 'SOURCES', Path(directory)):
                with patch.object(
                    download_sources, 'urlopen', return_value=FakeResponse()
                ) as urlopen:
                    with redirect_stdout(io.StringIO()):
                        download_sources.download(source)
                        download_sources.download(source)

            self.assertEqual(target.read_bytes(), b'<html>source</html>')
            self.assertFalse(target.with_suffix('.html.part').exists())
            urlopen.assert_called_once()

    def test_dry_run_neither_writes_nor_opens_url(self):
        source = download_sources.Source(
            'sample', 'sample.html', 'https://example.test/sample',
            'reference', 'Sample',
        )
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(download_sources, 'SOURCES', Path(directory)):
                with patch.object(download_sources, 'urlopen') as urlopen:
                    with redirect_stdout(io.StringIO()):
                        download_sources.download(source, dry_run=True)

            self.assertFalse((Path(directory) / source.filename).exists())
            urlopen.assert_not_called()


class SnapshotPinTests(unittest.TestCase):
    def test_every_implemented_source_is_pinned(self):
        unpinned = [
            source.key
            for source in download_sources.selected_sources([], 'implemented')
            if not source.sha256
        ]
        self.assertEqual(
            unpinned, [],
            'implemented sources must pin the snapshot their extractor was '
            'written against — run `download_sources.py --hashes`')

    def test_stale_pinned_file_is_refetched_rather_than_skipped(self):
        """CI restores `sources/` through a prefix restore-key, so after a
        pin is updated the cache holds the previous snapshot. Skipping on
        mere existence would wedge the build on a stale file it could just
        re-fetch — the pin, not the filename, identifies the snapshot."""
        import hashlib
        body = b'<html>fresh</html>'
        source = download_sources.Source(
            'sample', 'sample.html', 'https://example.test/sample',
            'implemented', 'Sample',
            sha256=hashlib.sha256(body).hexdigest(),
        )
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / source.filename
            target.write_bytes(b'<html>stale cache</html>')
            with patch.object(download_sources, 'SOURCES', Path(directory)):
                response = FakeResponse()
                response.read = lambda: body
                with patch.object(download_sources, 'urlopen',
                                  return_value=response) as urlopen:
                    with redirect_stdout(io.StringIO()):
                        download_sources.download(source)
                    urlopen.assert_called_once()
                self.assertEqual(target.read_bytes(), body)
                self.assertIsNone(download_sources.drift(source))

                # And a file that already matches is left alone.
                with patch.object(download_sources, 'urlopen') as urlopen:
                    with redirect_stdout(io.StringIO()):
                        download_sources.download(source)
                    urlopen.assert_not_called()

    def test_local_snapshots_match_their_pins(self):
        """A refreshed page changes what every walker and `core.repair` sees.

        `sources/` is gitignored, so drift otherwise shows up as an
        inexplicable extractor regression somewhere downstream. Absent
        snapshots skip — a fresh clone has none.
        """
        checked = 0
        for source in download_sources.selected_sources([], 'implemented'):
            if not (download_sources.SOURCES / source.filename).exists():
                continue
            checked += 1
            with self.subTest(source=source.key):
                actual = download_sources.drift(source)
                self.assertIsNone(
                    actual,
                    f'{source.filename} no longer matches its pin '
                    f'(expected {source.sha256}, got {actual}). Re-check the '
                    f'extractor and its repairs against the new page before '
                    f'updating the pin.')
        if not checked:
            self.skipTest('no snapshots present — run download_sources.py')


if __name__ == '__main__':
    unittest.main()
