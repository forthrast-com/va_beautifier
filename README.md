# Forthrast Editions

Reader editions of Vatican documents generated from the original Vatican HTML,
with contents navigation, footnotes, bookmarks and reader preferences.

## Site

Published for `https://circulars.forthrast.com/` using GitHub Pages:

- `/gaudium_et_spes.html`
- `/laudato_si.html`
- `/magnifica_humanitas.html`

## Build

```sh
./build.sh
```

The build uses the Nix flake and renders the TOML intermediate files and flat
HTML pages, including `index.html`. GitHub Actions rebuilds the pages and
deploys only the finished static site files.

Run the unit and extractor regression tests with:

```sh
nix develop --command python -m unittest discover -s tests
```

For a fresh source collection, fetch the Vatican HTML snapshots first:

```sh
nix develop --command python download_sources.py --list
nix develop --command python download_sources.py
```

The downloader records both implemented and queued documents, plus reference
pages collected for later work. Existing source files are retained unless
`--force` is given; `--category queued` or `--category reference` selects a
smaller set.

The custom domain requires a DNS `CNAME` record from `circulars.forthrast.com` to
`forthrast-com.github.io`.
