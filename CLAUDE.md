# va_beautifier

Web/EPUB/PDF editions of Vatican documents. The implemented documents now cover old-flat, modern Bootstrap, and Curia Word-export source templates; anything added should plausibly generalise to an arbitrary similarly-structured document.

## What this beats

The vatican.va edition is one long page of bare text. The points of difference:

- **Reader drawer** — contents, contextual footnotes, and bookmarks share a
  three-tab drawer beside the text rather than being dumped at the bottom
- **Navigation** — sticky chapter/section header, scroll indicator,
  bookmarks, and jump-anywhere navigation
- **Multiple formats** — web reader, EPUB, and A4 printer / A5 reader / A6
  booklet PDFs
- **Reader controls** — home, edition information, reader preferences, and
  drawer controls live top-right. Theme, text size, font, and bookmarks persist
  in `localStorage`; CSS custom properties and `data-theme` / `data-size` /
  `data-font` attributes drive the variants.
- **Browsable catalogue** — the landing page filters documents and sorts them
  by promulgation, pontificate, authority, or title

## Pipeline

    download_sources.py ──▶ sources/*.html ──(parse.py <slug>)──▶ build/<slug>.toml ──(make_html.py <slug>)──▶ site/<slug>.html
                                                │
                                                ├──(make_index.py)────────────▶  site/index.html
                                                │
                                                ├──(make_book.py <slug>)─────▶  site/downloads/<slug>.epub
                                                └──(make_book.py <slug>)─────▶  site/downloads/<slug>-{a4,a5,a6}.pdf

The TOML is the canonical intermediate. Downstream renderers consume TOML — never re-parse the Vatican HTML.

## Architecture

- `parse.py` — thin CLI. `argparse` with `choices` discovered via `pkgutil.iter_modules(extract.__path__)`. Loads `extract.<slug>`, calls its `extract()`, writes `<slug>.toml` via `core.write_toml`.
- `download_sources.py` — manifest-driven source fetcher. Lists or downloads implemented, queued, and reference-only Vatican pages into `sources/`; existing snapshots are preserved unless `--force` is passed.
- `core.py` — shared text/structure helpers, canonical paragraph and footnote
  constructors/context assignment, TOML loading and serialisation. The
  serialiser is the contract for document metadata, structure, appendices,
  signatories, and book-specific options. Canonical inline markup
  (`*em*`, `**strong**`, `<sup>`/`<sub>`) is converted once here
  (`inline_markup_to_html`, `INLINE_MARK_RE`); renderers must consume these
  rather than re-rolling their own regexes.
- `curia.py` — shared parsing helpers for Word-export Curia pages, including whitespace repair and anchor-delimited footnote extraction.
- `project.py` — shared repository paths used by CLI and renderer entrypoints.
- `extract/<slug>.py` — per-document extractor. Each exposes `extract() -> dict`. Add a new document by dropping a new module here; no registry edit needed.
- `make_html.py <slug>` — reads `<slug>.toml`, writes a self-contained
  `site/<slug>.html` with CSS and JS inlined. It builds the sticky heading,
  scroll indicator, drawer contents/footnotes/bookmarks, appendices, and end
  matter. Body gets `class="doc-<slug>"` for scoped overrides.
- `make_index.py` — renders the catalogue cards and download controls from
  TOML plus `CARD_META`. Client-side filtering, grouping, and sort preference
  persistence are inlined into `site/index.html`. Adding a document currently
  requires a `CARD_META` entry for a fully authored tile.
- `make_book.py <slug>` — emits intermediate Markdown and per-paper title-page
  Typst includes, then writes one EPUB plus A4, A5, and A6 PDFs under
  `site/downloads/`. Appendices enter both tables of contents; page breaks and
  PDF end matter use raw Typst, with parallel raw HTML for EPUB. Libertinus
  Serif is the reproducible default book face; override it with
  `VA_BOOK_FONT=…` when another font is installed locally.
- `templates/book.typ` — source pandoc-typst `conf` module materialised to
  `build/<hyphenated-slug>-book.typ` with a muted document-hue accent. Owns
  paper geometry, running heads, heading shows, footnote styling, and TOC
  heading. Title pages and colophons come from the include-before-body files.
- `assets/styles.css`, `assets/scripts.js` — read by `make_html.py` and inlined into the output. The JS has two placeholders, `__INDICATOR_JSON__` and `__DOC_NAME__`, substituted at render time. Edit these files directly; the output is still self-contained.
- `Makefile` — the build entrypoint. `make` builds books, every reader, and the
  catalogue; `make books` stops after EPUB/PDF; `make site/<slug>.html` builds
  one reader. Each new document gets an explicit TOML rule so source
  dependencies stay precise. Add a doc → drop extractor → add slug to `DOCS`,
  add its TOML rule, and add catalogue metadata.

## TOML schema

Top-level: `name`, `hue`, `source_url`, `author`, `issued_by`, `pontificate`,
`date`, `identifier`,
`rights`, `publisher`, `collection`, `desc`, optional `desc_post`,
`chapter_style`, `book_toc_depth`, `promulgation`, `signature`, `hero_image`,
and `hero_credit`. `chapter_style = "roman"` changes structural chapter
labels; `book_toc_depth` defaults to 3. Promulgation and signature use
canonical inline formatting; line breaks in `signature` are significant.
`author` is EPUB creator/signatory metadata; `issued_by` is the institutional
or personal voice shown in the catalogue and colophon. The colophon adds
`pontificate` only when it differs from `issued_by`.

`[[paragraphs]]` — `number`, `part`, `part_title`, `chapter`, `chapter_title`, `chapter_subtitle`, `section`, `section_title`, `sub_heading`, `heading_la`, `break_after`, `text` (multiline, `\n\n`-separated sub-paragraphs). Authored inline formatting in `text` and footnote `text` is canonical Markdown-compatible content: `*italics*`, `**bold**`, `<sup>…</sup>`, and `<sub>…</sub>`.

- `sub_heading` is per-paragraph and optional (defaults to ''); LS uses it for topical headers within sections, GeS doesn't have any.
- `heading_la` is a Latin micro-summary; GeS has one per paragraph, LS has none.
- `break_after` marks a structural separator following a paragraph; LS and SC use it for rules before appendix transitions.
- `hide_number` suppresses a displayed paragraph number for unnumbered prefatory prose; the ITC preliminary note uses it.

`[[footnotes]]` — `part`, `chapter`, `section`, `sub_heading`, `number`, `text`. Heading ownership is assigned from the note's first citation at the lowest available level. Inline refs in paragraph text are canonical `(N)` for 1 ≤ N ≤ 999. Extractors normalise alternative source formats (LS's `[N]`) to this canonical form before emitting TOML.

`[[appendices]]` — `title`, optional `kind` (currently `prayer` or `declaration`), `text`. Appendices are top-level reading regions: they appear at the root of the web contents/minimap and in book tables of contents.

`[[signatories]]` — `name`, `role`. Signatories render as a structured end-matter roster before the final signature.

`part = 0` is preface/introduction; `chapter = 0` / `section = 0` mean "none under this scope".

## Sources

GeS is served as **ISO-8859-1** (EN) and **latin-1** (LA), not UTF-8. LS and the Curia Word-export pages are UTF-8. Sniff before assuming on any new document.

The ITC export has its first footnote anchor outside the paragraph wrapper
used by the remaining notes. `curia.anchored_footnotes()` therefore splits
the note block at named `_ftnN` anchors instead of assuming one note per
paragraph.

Run `nix develop --command python download_sources.py --list` to see the
source manifest and local status; omit `--list` to fetch missing sources.
`--category queued` selects pending extractor inputs, while
`--category reference` selects captured contextual documents.

## Template variation

Three templates encountered so far:

- **Old flat** (GeS) — 24 `<p>` tags total, structure carried by `<b>` headings inside `<center>` blocks. Latin source provides a per-paragraph micro-summary keyed by §N. Footnotes in a separate `NOTES`-marked block.
- **Modern Bootstrap** (LS) — 788 `<p>` tags wrapped in `<main>`. Chapter delimiter is a centred `CHAPTER ONE` followed by a centred `<b>` title. Section is a `<p>` whose only child is a `<b>` matching `^[IVX]+\.`. Sub-heading is a `<p>` whose only child is an `<i>`. The `align` attribute is unreliable (set on the first heading of chapter 1, blank thereafter); use child-shape tests.
- **Curia Word export** (*Antiqua et nova*, *Quo vadis, humanitas?*) —
  content is a stream of styled `<p>` tags with named anchors for footnotes.
  Major divisions and subsection titles are recovered from
  centred/bold/italic paragraph shapes; use anchor boundaries for footnotes
  because wrapper structure is inconsistent. Structural heading labels must
  remain plain text even when the source wraps part of a heading in a link.

Each new document is likely to be its own dialect of one of these. Drop a new file in `extract/`, look at the source's tag-shape signals, and write the walker. Don't assume what worked for GeS will work for LS or vice versa.

## Renderer conventions

HTML output is a single self-contained file (CSS + JS inlined, no external assets). Stable IDs:

- paragraph: `para-{n}`
- footnote: `fn-{part}-{chapter}-{n}`
- chapter/root region: generated `ch-{n}`
- section heading: `sec-{part}-{chapter}-{section}`
- sub-heading: generated `sub-{n}`
- appendix: `appendix-{n}`

Doc-scoped CSS lives under `.doc-<slug>` selectors. Long structured documents share gutter-style paragraph numbers, soft-anchor positioning, and a height-capped scroll indicator under their document selectors. GeS keeps the original inline `5. *Latin heading* body` layout via the default rules + `.para-num::after { content: '.' }`.

JS publishes the sticky-bar's measured height to `--bar-h` so other layout (indicator centring, soft-anchor maths) can read it from CSS or JS.

The drawer opens from the top-right control or an inline footnote reference.
Opening from a reference synchronises the control state and selects the note.
On touch only, tapping document text closes the drawer; mouse clicks do not.
The drawer grows to 75vw on mobile, and selected notes settle higher in its
viewport than on desktop.

The web edition leans on UI affordances (sticky heading bar, scroll indicator,
drawer, bookmarks) that don't translate to EPUB/PDF — those want endnotes per
section, real page breaks, and no JS.

The flat GitHub Pages site is deployed through `.github/workflows/pages.yml`;
`CNAME` sets `circulars.forthrast.com`. Finished HTML and book downloads are
published, while intermediate Markdown/TOML stays in `build/` only.

## Open work

- **Title page (PDF) — done.** `templates/book.typ` owns book
  typography (page geom, heading shows, footnote entries). The title
  page is written to `build/<slug>_titlepage_<paper>.typ` and fed in via
  pandoc's `--include-before-body` so it lands before the TOC.
  Display-italic doc name (centred, vertically balanced), tracked-caps
  preamble and subtitle, no page number on the title page. End matter
  (promulgation + optional signatories + signature) renders on its own page via a raw-typst
  block at the end of the body, with a parallel raw-HTML colophon
  block so EPUB gets the same content.
- **Book polish (other)** —
    - *Multi-paragraph footnotes:* the few notes in LS that span two
      paragraphs render as one block — pandoc's continuation-indent
      handling needs a closer look.
    - *Auto-build hygiene:* the Makefile already keeps things minimal via
      per-target dependencies, but a few historical TOMLs commit-bounce
      because their generated formatting drifted; rerun `make clean && make`
      and recommit any genuine churn.
- **More documents** — `sources/Fratelli tutti_en.html` is sitting
  un-extracted (likely the modern Bootstrap dialect, LS-shaped). A
  reference capture recorded by `download_sources.py` for a possible
  future edition is `francis_g7_ai_en.html`.
- **Audit follow-ups (2026-06)** —
    - *CI test step:* `pages.yml` deploys without running the suite. Add
      `nix develop --command python -m unittest discover -s tests` after
      the source fetch — sources are present at that point, so the
      extractor regression tests run too (locally they skip when
      `sources/` is absent).
    - *make_book coverage:* only end-matter/accent helpers are tested;
      no test renders a small TOML through `emit_markdown` the way
      `tests/test_make_html.py` golden-tests the web renderer.
    - *CARD_META → TOML:* `make_index.py` now warns on a missing entry,
      but the better end state is moving tile metadata (`type`,
      `subtitle`/`kind_long`) into the document TOML so adding a doc
      touches one place.
    - *EPUB title strip:* `templates/strip_fn_backlink.lua` removes the
      synthetic title H1 by text match; safe today because `make_book.py`
      never emits a doc-name H1 (noted in the filter) — revisit if that
      changes.

## Extractor boundaries (not implemented — refactor approach notes)

The right unit of sharing is the *dialect*, not a generic walker.
`curia.py` is the model: a dialect module owns loading, text repair, and
footnote mechanics, while the per-document extractor owns facts (metadata,
title lines) and quirks (SC's split `CHAPTER VI`, QVH's hidden-numbered
preliminary note). Two dialect modules are missing:

- `oldflat.py` (GeS, SC) — iso-8859-1 load, `NOTES</b>` body/notes split,
  front-matter split around the display title, `<center>`/all-bold
  heading-shape walking (`_joined_bolds`).
- `modern.py` (LS, MH, Fratelli tutti when implemented) — utf-8 +
  `<main>` load, the front-matter pipeline (`br_lines` →
  `split_around_title` → `encyclical_split`), `CHAPTER ONE`
  pending-title handling, `only_child_is` shape tests.

Mechanisms duplicated nearly verbatim across walkers, worth lifting to
`core` regardless of dialect grouping:

- the plain-then-rich double match on numbered paragraphs
  (`RE_PARA.match(clean_text(p))`, then again with
  `preserve_formatting=True` for the recorded text) — five copies;
- the heading-state dict with cascading resets (set chapter → clear
  section/sub-heading) — five hand-rolled copies; reset bugs live here;
- `heading_title` (all-caps → title case preserving "AI") — duplicated
  between `curia.py` and MH's `_title`;
- `Given in/at …` promulgation + centred-signature trailer detection
  (LS, MH, AeN each carry a variant).

Do **not** build a config-driven generic walker: the dialects diverge
exactly where a framework would need escape hatches (SC's appendix mode,
LS's two-phase body/tail split, QVH's part-title modes), and the
drop-a-file extractor contract is the part of the design that works.
Refactor opportunistically — the natural forcing function is implementing
Fratelli tutti against a new `modern.py`, moving LS and MH onto it in the
same change. Validate by regenerating `build/*.toml` and requiring
byte-identical output, plus the extractor regression tests.

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

`flake.nix` provides Python 3.12 + beautifulsoup4, GNU make, pandoc, and
typst. Use the Nix shell for project commands; do not rely on tools
installed in the ambient shell. Build everything:
`nix develop --command make`. Build one book:
`nix develop --command python make_book.py laudato_si`.

Run tests: `nix develop --command python -m unittest discover -s tests`.

`shell.nix` is kept only as a legacy fallback.
