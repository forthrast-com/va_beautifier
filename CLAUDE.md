# va_beautifier

Web/EPUB/PDF editions of Vatican documents. *Gaudium et Spes* is the worked example, not the product — anything added should plausibly generalise to an arbitrary similarly-structured document.

## What this beats

The vatican.va edition is one long page of bare text. The points of difference:

- **Sidebar footnotes** — notes open in a drawer beside the text, not dumped at the bottom
- **TOC and navbar** — sticky chapter/section header, scroll indicator, jump-anywhere navigation
- **Multiple formats** — web now, EPUB and PDF on the roadmap
- **A few reader toggles** — light/dark, text size, maybe a serif/sans switch. iOS-Settings energy, not a config file

## Pipeline

    sources/*.html  ──(parse_ges.py)──▶  *.toml  ──(make_html.py)──▶  *.html
                                            │
                                            ├──(not yet)──▶  *.epub
                                            └──(not yet)──▶  *.pdf

The TOML is the canonical intermediate. Downstream renderers consume TOML — never re-parse the Vatican HTML.

## TOML schema

Top-level: `desc`, `promulgation` (multiline).

`[[paragraphs]]` — `number`, `part`, `part_title`, `chapter`, `chapter_title`, `section`, `section_title`, `heading_la` (Latin micro-summary, one per paragraph), `text` (multiline, `\n\n`-separated sub-paragraphs).

`[[footnotes]]` — `part`, `chapter`, `number`, `text`. Inline refs in paragraph text are literal `(N)` for 1 ≤ N ≤ 999.

`part = 0` is preface/introduction; `chapter = 0` / `section = 0` mean "none under this scope".

## Sources

Vatican.va serves these as **ISO-8859-1** (EN) and **latin-1** (LA), not UTF-8. The parser opens them with the right encoding; sniff before assuming on any new document.

## Renderer conventions

HTML output is a single self-contained file (CSS + JS inlined, no external assets). Stable IDs:

- paragraph: `para-{n}`
- footnote: `fn-{part}-{chapter}-{n}`
- section heading: `sec-{part}-{chapter}-{section}`

The web edition leans on UI affordances (sticky heading bar, scroll indicator, footnote drawer) that don't translate to EPUB/PDF — those want endnotes per section, real page breaks, no JS.

## Open work

- The parser is GeS-specific: `CHAPTER_TITLES` / `PART_TITLES` sets are hardcoded, source paths are literal `sources/gaudium_et_spes_*.html`. Generalising probably means a per-document config or a heuristic that learns part/chapter titles from document structure rather than a known set.
- `parse.py` and `make_html.py` both read their inputs by literal filename, not argv. Same generalisation point.
- **There are at least two Vatican.va templates.** GeS uses the old flat layout (24 `<p>` tags total, structure via `<b>` headings and `<center>` blocks). Laudato Si uses the modern template (381 `<p align="left">`, Bootstrap chrome, separate NOTES handling). The current parser pulls 0 paragraphs / 0 footnotes from Laudato Si — verified. Plan for at least two parser variants, or a detector + dispatch.
- CSS is a single ~180-line inline string. The reader toggles want CSS custom properties on `:root` flipped by a small JS control (and `localStorage` for persistence) — not a config system. Keep the surface small: a handful of switches a non-technical reader would expect from a well-made reading app.
- EPUB: pandoc is in Home Manager — candidate path, fed by TOML or an HTML intermediate.
- PDF: typst is in Home Manager — natural fit, would consume TOML directly.

## Environment

`shell.nix` provides Python 3.12 + beautifulsoup4. `nix-shell --run "python parse_ges.py"` etc.
