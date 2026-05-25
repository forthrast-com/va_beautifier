# Forthrast Editions

Reader editions of Vatican documents generated from the original Vatican HTML,
with contents navigation, footnotes, bookmarks and reader preferences.

## Site

Published for `https://docs.forthrast.com/` using GitHub Pages:

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

The custom domain requires a DNS `CNAME` record from `docs.forthrast.com` to
`forthrast-com.github.io`.
