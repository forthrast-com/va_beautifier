# Forthrast Editions

Reader editions of Vatican documents generated from the original Vatican HTML,
with contents navigation, footnotes, bookmarks and reader preferences.

## Site

Published to `https://circulars.forthrast.com/` using GitHub Pages. The
catalogue at `/` links one reader page per document (`/<slug>.html`, e.g.
`/laudato_si.html`) plus EPUB and A4/A5/A6 PDF downloads.

## Dev shell

Everything runs inside the Nix flake's dev shell. With direnv installed,
`direnv allow` once and the shell loads on `cd`; otherwise prefix commands
with `nix develop --command`.

## Build

```sh
make               # everything: books, readers, catalogue
make books         # EPUB + PDFs for every document
make <slug>        # one reader page (site/<slug>.html)
make <slug>-books  # one document's EPUB + PDFs
make list          # the document slugs <slug> accepts
make test          # unit + extractor regression tests
make qa            # full build, then the site-artifact smoke check
make help          # this list
```

GitHub Actions rebuilds the site and publishes the finished reading and
download files.

## Sources

For a fresh checkout, fetch the Vatican HTML snapshots first:

```sh
python download_sources.py --list   # manifest + local status
python download_sources.py         # fetch what's missing
```

The downloader records both implemented and queued documents, plus reference
pages collected for later work. Existing source files are retained unless
`--force` is given; `--category queued` or `--category reference` selects a
smaller set.

## DNS

The custom domain requires a DNS `CNAME` record from `circulars.forthrast.com`
to `forthrast-com.github.io`.
