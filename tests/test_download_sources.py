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
            {'fratelli_tutti_en'},
        )
        self.assertEqual(
            {source.key for source in reference},
            {'francis_g7_ai_en'},
        )
        self.assertTrue({
            'antiqua_et_nova_en',
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


if __name__ == '__main__':
    unittest.main()
