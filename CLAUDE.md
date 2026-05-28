# va_beautifier

Web/EPUB/PDF editions of Vatican documents. Currently rides on *Gaudium et Spes* (old flat template) and *Laudato Si'* (modern Bootstrap template); anything added should plausibly generalise to an arbitrary similarly-structured document.

## What this beats

The vatican.va edition is one long page of bare text. The points of difference:

- **Sidebar footnotes** — notes open in a drawer beside the text, not dumped at the bottom
- **Contents and navbar** — sticky chapter/section header, scroll indicator, bookmarks and jump-anywhere navigation
- **Multiple formats** — web now, EPUB and PDF on the roadmap
- **Reader toggles** — light/dark + text size, gear-icon popover top-right, persisted in `localStorage`. Driven by CSS custom properties on `:root` (write `data-theme` / `data-size` attrs, the variants override the defaults).

## Pipeline

    download_sources.py ──▶ sources/*.html ──(parse.py <slug>)──▶ <slug>.toml ──(make_html.py <slug>)──▶ <slug>.html
                                                │
                                                ├──(make_index.py)────────────▶  index.html
                                                │
                                                ├──(make_book.py <slug>)─────▶  <slug>.epub
                                                └──(make_book.py <slug>)─────▶  <slug>.pdf

The TOML is the canonical intermediate. Downstream renderers consume TOML — never re-parse the Vatican HTML.

## Architecture

- `parse.py` — thin CLI. `argparse` with `choices` discovered via `pkgutil.iter_modules(extract.__path__)`. Loads `extract.<slug>`, calls its `extract()`, writes `<slug>.toml` via `core.write_toml`.
- `download_sources.py` — manifest-driven source fetcher. Lists or downloads implemented, queued, and reference-only Vatican pages into `sources/`; existing snapshots are preserved unless `--force` is passed.
- `core.py` — shared text/structure helpers, canonical paragraph and footnote constructors/context assignment, TOML loading and serialisation. The serialiser is the contract: each extractor returns a dict with `name`, `desc`, `promulgation`, `paragraphs[]`, `footnotes[]`.
- `project.py` — shared repository paths used by CLI and renderer entrypoints.
- `extract/<slug>.py` — per-document extractor. Each exposes `extract() -> dict`. Add a new document by dropping a new module here; no registry edit needed.
- `make_html.py <slug>` — reads `<slug>.toml`, writes `<slug>.html`. Single self-contained file (CSS + JS inlined). Doc-name comes from the TOML's `name`. Body gets `class="doc-<slug>"` so per-doc CSS overrides can scope to that document only.
- `make_book.py <slug>` — reads `<slug>.toml`, emits `build/<slug>.md` + `build/<slug>_titlepage.typ` (the title page as raw typst, fed to pandoc via `--include-before-body` so it lands before the TOC). Then runs pandoc twice: once to `<slug>.epub` and once to `<slug>.pdf` (via `--pdf-engine=typst --pdf-engine-opt=--root=<ROOT>`). Body font is Hoefler Text by default; override with `VA_BOOK_FONT=…`. Page breaks and the end matter ride as raw typst blocks, which the EPUB writer ignores.
- `templates/book.typ` — pandoc-typst `conf` module imported via YAML `template:` metadata. Owns page geometry (A5, 11pt), font defaults, heading shows for chapter/section/subsection, footnote entry styling, and the centred italic "Contents" header on the TOC page. Does *not* render the title — that's the include-before-body's job.
- `assets/styles.css`, `assets/scripts.js` — read by `make_html.py` and inlined into the output. The JS has two placeholders, `__INDICATOR_JSON__` and `__DOC_NAME__`, substituted at render time. Edit these files directly; the output is still self-contained.
- `Makefile` — dependency-tracked build. `make` builds all HTML + index; `make books` also builds EPUB/PDF (requires pandoc + typst). Add a doc → drop extractor → add slug to `DOCS` and add an explicit TOML target with its source deps.

## TOML schema

Top-level: `name`, `hue` (web accent colour in HSL degrees), `source_url`, `desc`, `promulgation` (multiline).

`[[paragraphs]]` — `number`, `part`, `part_title`, `chapter`, `chapter_title`, `chapter_subtitle`, `section`, `section_title`, `sub_heading`, `heading_la`, `break_after`, `text` (multiline, `\n\n`-separated sub-paragraphs). Authored inline formatting in `text` and footnote `text` is canonical Markdown-compatible content: `*italics*`, `**bold**`, `<sup>…</sup>`, and `<sub>…</sub>`.

- `sub_heading` is per-paragraph and optional (defaults to ''); LS uses it for topical headers within sections, GeS doesn't have any.
- `heading_la` is a Latin micro-summary; GeS has one per paragraph, LS has none.
- `break_after` marks a structural separator following a paragraph; LS uses it for the rule before its closing prayers.

`[[footnotes]]` — `part`, `chapter`, `section`, `sub_heading`, `number`, `text`. Heading ownership is assigned from the note's first citation at the lowest available level. Inline refs in paragraph text are canonical `(N)` for 1 ≤ N ≤ 999. Extractors normalise alternative source formats (LS's `[N]`) to this canonical form before emitting TOML.

`part = 0` is preface/introduction; `chapter = 0` / `section = 0` mean "none under this scope".

## Sources

GeS is served as **ISO-8859-1** (EN) and **latin-1** (LA), not UTF-8. LS is UTF-8. Sniff before assuming on any new document.

Run `nix develop --command python download_sources.py --list` to see the
source manifest and local status; omit `--list` to fetch missing sources.
`--category queued` selects pending extractor inputs, while
`--category reference` selects captured contextual documents.

## Template variation

Two templates encountered so far:

- **Old flat** (GeS) — 24 `<p>` tags total, structure carried by `<b>` headings inside `<center>` blocks. Latin source provides a per-paragraph micro-summary keyed by §N. Footnotes in a separate `NOTES`-marked block.
- **Modern Bootstrap** (LS) — 788 `<p>` tags wrapped in `<main>`. Chapter delimiter is a centred `CHAPTER ONE` followed by a centred `<b>` title. Section is a `<p>` whose only child is a `<b>` matching `^[IVX]+\.`. Sub-heading is a `<p>` whose only child is an `<i>`. The `align` attribute is unreliable (set on the first heading of chapter 1, blank thereafter); use child-shape tests.

Each new document is likely to be its own dialect of one of these. Drop a new file in `extract/`, look at the source's tag-shape signals, and write the walker. Don't assume what worked for GeS will work for LS or vice versa.

## Renderer conventions

HTML output is a single self-contained file (CSS + JS inlined, no external assets). Stable IDs:

- paragraph: `para-{n}`
- footnote: `fn-{part}-{chapter}-{n}`
- section heading: `sec-{part}-{chapter}-{section}`

Doc-scoped CSS lives under `.doc-<slug>` selectors. Example: LS's gutter-style paragraph numbers, the soft-anchor JS positioning, and the height-capped scroll indicator are all gated on `.doc-laudato_si`. GeS keeps the original inline `5. *Latin heading* body` layout via the default rules + `.para-num::after { content: '.' }`.

JS publishes the sticky-bar's measured height to `--bar-h` so other layout (indicator centring, soft-anchor maths) can read it from CSS or JS.

The web edition leans on UI affordances (sticky heading bar, scroll indicator, footnote drawer) that don't translate to EPUB/PDF — those want endnotes per section, real page breaks, no JS.

The flat GitHub Pages site is deployed through `.github/workflows/pages.yml`;
`CNAME` sets `circulars.forthrast.com`, and only finished HTML files plus Pages
metadata are published.

## Open work

- **Title page (PDF) — done.** `templates/book.typ` owns book
  typography (page geom, heading shows, footnote entries). The title
  page is written to `build/<slug>_titlepage.typ` and fed in via
  pandoc's `--include-before-body` so it lands before the TOC.
  Display-italic doc name (centred, vertically balanced), tracked-caps
  preamble and subtitle, no page number on the title page. End matter
  (dedication + signature) renders on its own page via a raw-typst
  block at the end of the body, with a parallel raw-HTML colophon
  block so EPUB gets the same content.
- **Book polish (other)** —
    - *MH TOC orphans:* the introduction's section headings (Introduction,
      The res novae of our time, Two biblical images, &c.) sit indented
      under nothing because the body H1 is `.unlisted`. Either promote
      "Introduction" to chapter-level for MH or have the renderer suppress
      the indent when there's no listed parent.
    - *Multi-paragraph footnotes:* the few notes in LS that span two
      paragraphs render as one block — pandoc's continuation-indent
      handling needs a closer look.
    - *Auto-build hygiene:* `make` is now dependency-tracked so unchanged
      docs are skipped, but `make clean && make` still re-emits everything.
      Consider hashing inputs to skip truly unchanged docs even after a clean.
- **More documents** — `sources/Fratelli tutti_en.html` and
  `sources/Sacrosanctum Concilium_{en,la}.html` are sitting un-extracted.
  Sacrosanctum is the old-flat template (GeS-shaped); Fratelli tutti is
  likely the modern Bootstrap dialect (LS-shaped).
  Reference captures recorded by `download_sources.py` for possible future
  editions are `antiqua_et_nova_en.html`, `quo_vadis_humanitas_en.html`, and
  `francis_g7_ai_en.html`.

## JS-free drawer (not implemented — approach notes)

The drawer, tabs, and footnote refs can all work without JavaScript using
only CSS + native HTML. Tested and reverted — the embedded-browser context
that prompted it turned out to disable JS globally (Claude iOS app), and
the extra HTML complexity wasn't worth the marginal improvement elsewhere.

If revisiting:

- **Drawer toggle** — replace `<button id="fn-tab">` with
  `<input type="checkbox" id="drawer-cb" hidden>` +
  `<label for="drawer-cb" id="fn-tab">`. CSS: `body:has(#drawer-cb:checked)
  #fn-drawer { transform: translateX(0); }`. JS intercepts the label click
  with `e.preventDefault()` and sets `drawerCb.checked` manually so both
  paths stay in sync.

- **Tab strip** — add three hidden radio inputs (`name="drawer-view"`,
  ids `view-toc` / `view-footnotes` / `view-bookmarks`, first `checked`).
  Tab buttons become `<label for="view-X">`. CSS:
  `body:has(#view-X:checked) #drawer-X { display: block; }` for visibility,
  `body:has(#view-X:checked) .drawer-view-tab[for="view-X"]` for active
  styling. JS sets `radio.checked` instead of toggling `.active` and
  `panel.hidden`.

- **Footnote refs** — the `<sup>` links already point to `#fn-{p}-{ch}-{n}`
  IDs on `.fn-item` elements inside the drawer.
  `body:has(#fn-drawer .fn-item:target) #fn-drawer { transform: translateX(0); }`
  opens the drawer; a parallel rule forces `#drawer-footnotes` visible.
  Limitation: clicking close (unchecking the drawer checkbox) won't hide the
  drawer while a `:target` is still active — a reset anchor inside the close
  button (`href="#"` or a top-of-page anchor) would fix this.

## Environment

`flake.nix` provides Python 3.12 + beautifulsoup4 + GNU make. Build everything: `nix develop --command make`. Build one doc: `nix develop --command sh -c "python parse.py laudato_si && python make_html.py laudato_si"`.

Run tests: `nix develop --command python -m unittest discover -s tests`.

`shell.nix` is kept only as a legacy fallback.
