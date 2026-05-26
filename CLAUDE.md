# va_beautifier

Web/EPUB/PDF editions of Vatican documents. The implemented documents now cover old-flat, modern Bootstrap, and Curia Word-export source templates; anything added should plausibly generalise to an arbitrary similarly-structured document.

## What this beats

The vatican.va edition is one long page of bare text. The points of difference:

- **Sidebar footnotes** — notes open in a drawer beside the text, not dumped at the bottom
- **Contents and navbar** — sticky chapter/section header, scroll indicator, bookmarks and jump-anywhere navigation
- **Multiple formats** — web reading edition plus downloadable EPUB and PDF books
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
- `curia.py` — shared parsing helpers for Word-export Curia pages, including whitespace repair and anchor-delimited footnote extraction.
- `project.py` — shared repository paths used by CLI and renderer entrypoints.
- `extract/<slug>.py` — per-document extractor. Each exposes `extract() -> dict`. Add a new document by dropping a new module here; no registry edit needed.
- `make_html.py <slug>` — reads `<slug>.toml`, writes `<slug>.html`. Single self-contained file (CSS + JS inlined). Doc-name comes from the TOML's `name`. Body gets `class="doc-<slug>"` so per-doc CSS overrides can scope to that document only.
- `make_book.py <slug>` — reads `<slug>.toml`, emits `build/<slug>.md` + `build/<slug>_titlepage.typ` (the title page as raw typst, fed to pandoc via `--include-before-body` so it lands before the TOC). Then runs pandoc twice: once to `<slug>.epub` and once to `<slug>.pdf` (via `--pdf-engine=typst --pdf-engine-opt=--root=<ROOT>`). Body font is Hoefler Text by default; override with `VA_BOOK_FONT=…`. Page breaks and the end matter ride as raw typst blocks, which the EPUB writer ignores.
- `templates/book.typ` — pandoc-typst `conf` module imported via YAML `template:` metadata. Owns page geometry (A5, 11pt), font defaults, heading shows for chapter/section/subsection, footnote entry styling, and the centred italic "Contents" header on the TOC page. Does *not* render the title — that's the include-before-body's job.
- `assets/styles.css`, `assets/scripts.js` — read by `make_html.py` and inlined into the output. The JS has two placeholders, `__INDICATOR_JSON__` and `__DOC_NAME__`, substituted at render time. Edit these files directly; the output is still self-contained.
- `Makefile` — the build entrypoint. `make` (default `all`) builds books + every site HTML + the landing page; `make books` stops after EPUB/PDF; `make site/<slug>.html` builds a single edition. The landing page depends on the EPUBs so its download labels carry current file sizes. Each new doc gets its own explicit TOML target so source-file dependencies stay precise. Add a doc → drop extractor → add slug to `DOCS` and add a `build/<slug>.toml` rule.

## TOML schema

Top-level: `name`, `hue` (web accent colour in HSL degrees), `source_url`, `desc`, `promulgation` (multiline).

`[[paragraphs]]` — `number`, `part`, `part_title`, `chapter`, `chapter_title`, `chapter_subtitle`, `section`, `section_title`, `sub_heading`, `heading_la`, `break_after`, `text` (multiline, `\n\n`-separated sub-paragraphs). Authored inline formatting in `text` and footnote `text` is canonical Markdown-compatible content: `*italics*`, `**bold**`, `<sup>…</sup>`, and `<sub>…</sub>`.

- `sub_heading` is per-paragraph and optional (defaults to ''); LS uses it for topical headers within sections, GeS doesn't have any.
- `heading_la` is a Latin micro-summary; GeS has one per paragraph, LS has none.
- `break_after` marks a structural separator following a paragraph; LS uses it for the rule before its closing prayers.
- `hide_number` suppresses a displayed paragraph number for unnumbered prefatory prose; the ITC preliminary note uses it.

`[[footnotes]]` — `part`, `chapter`, `section`, `sub_heading`, `number`, `text`. Heading ownership is assigned from the note's first citation at the lowest available level. Inline refs in paragraph text are canonical `(N)` for 1 ≤ N ≤ 999. Extractors normalise alternative source formats (LS's `[N]`) to this canonical form before emitting TOML.

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
- **Curia Word export** (*Antiqua et nova*, *Quo vadis, humanitas?*) — content is a stream of styled `<p>` tags with named anchors for footnotes. Major divisions and subsection titles are recovered from centred/bold/italic paragraph shapes; use anchor boundaries for footnotes because wrapper structure is inconsistent.

Each new document is likely to be its own dialect of one of these. Drop a new file in `extract/`, look at the source's tag-shape signals, and write the walker. Don't assume what worked for GeS will work for LS or vice versa.

## Renderer conventions

HTML output is a single self-contained file (CSS + JS inlined, no external assets). Stable IDs:

- paragraph: `para-{n}`
- footnote: `fn-{part}-{chapter}-{n}`
- section heading: `sec-{part}-{chapter}-{section}`

Doc-scoped CSS lives under `.doc-<slug>` selectors. Long structured documents share gutter-style paragraph numbers, soft-anchor positioning, and a height-capped scroll indicator under their document selectors. GeS keeps the original inline `5. *Latin heading* body` layout via the default rules + `.para-num::after { content: '.' }`.

JS publishes the sticky-bar's measured height to `--bar-h` so other layout (indicator centring, soft-anchor maths) can read it from CSS or JS.

The web edition leans on UI affordances (sticky heading bar, scroll indicator, footnote drawer) that don't translate to EPUB/PDF — those want endnotes per section, real page breaks, no JS.

The flat GitHub Pages site is deployed through `.github/workflows/pages.yml`;
`CNAME` sets `circulars.forthrast.com`. Finished HTML and book downloads are
published, while intermediate Markdown/TOML stays in `build/` only.

## Open work

- **Title page (PDF) — done.** `templates/book.typ` owns book
  typography (page geom, heading shows, footnote entries). The title
  page is written to `build/<slug>_titlepage.typ` and fed in via
  pandoc's `--include-before-body` so it lands before the TOC.
  Display-italic doc name (centred, vertically balanced), tracked-caps
  preamble and subtitle, no page number on the title page. End matter
  (dedication + signature) renders on its own page via a raw-typst
  block at the end of the body, with a parallel raw-HTML colophon
  block so EPUB gets the same content. Image slot is wired through
  the `hero_image` + `hero_credit` TOML fields — degrades cleanly
  when unset.
- **Hero / decorative images** — title-page slot is wired
  (`hero_image` floats above the title block at 65% width with the
  `hero_credit` line in italic underneath). To drop an image in: save
  to e.g. `assets/heros/<slug>.jpg`, then set `hero_image` and
  `hero_credit` in the extractor (`extract/<slug>.py`'s `extract()`
  return dict). Typst paths are project-root-relative because
  `make_book.py` passes `--root=<ROOT>` to the engine — so the value
  in the TOML can be a plain relative path like `assets/heros/foo.jpg`.
  Likely sources: Wikimedia Commons, US Library of Congress PPOC,
  Rijksstudio.

  Per-doc shortlist (pick later — capture now):

  *Magnifica Humanitas* — early-modern automaton, slightly surreal:
    - **Vaucanson's duck** (1739) — the canonical Enlightenment-era
      automaton. Famous side-elevation engraving from the 1738 pamphlet.
      Surreal, recognisable, hits the "what is the human, what is the
      machine" register cleanly.
    - **da Vinci's mechanical knight** (c. 1495, Codex Atlanticus) —
      Renaissance sketches. Weightier, foundational; reads "this concern
      is older than you think."
    - **Salomon Schweigger automaton engraving** (17th c.) — orientalist
      printmaking. More obscure; harder to find a clean high-res scan.

  *Gaudium et Spes* — Vatican II:
    - **Council fathers in St Peter's** — wide assembly shot during a
      session. Reads instantly as Vatican II to anyone who recognises
      the setting.
    - **Lothar Wolleh portrait** (1960s) — graphic, tighter portraiture
      from Wolleh's session series. Licence varies per print; confirm
      PD-eligibility per image.
    - **Opening-procession crowd shot** (Oct 1962) — bishops streaming
      into St Peter's Square. More dynamic; sets the scene rather than
      the chamber.

  *Laudato Si'* — fever-dream sun-and-birds plate:
    - **Mughal solar miniature** (16-17th c.) — Indian miniature with
      solar disc and animals arrayed around it. Closest to the
      encyclical's cosmic-fraternity register.
    - **William Blake bird study** — Romantic-era, visionary, slightly
      mystical. Less ecological, more apocalyptic-pastoral.
    - **Mughal nature plate (non-solar)** — same school, tree-and-birds
      composition rather than the sun. Calmer, easier to crop tall.
- **Book polish (other)** —
    - *MH TOC orphans:* the introduction's section headings (Introduction,
      The res novae of our time, Two biblical images, &c.) sit indented
      under nothing because the body H1 is `.unlisted`. Either promote
      "Introduction" to chapter-level for MH or have the renderer suppress
      the indent when there's no listed parent.
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

## Environment

`flake.nix` provides Python 3.12 + beautifulsoup4, GNU make, pandoc, and
typst. Use the Nix shell for project commands; do not rely on tools
installed in the ambient shell. Build everything:
`nix develop --command make`. Build one book:
`nix develop --command python make_book.py laudato_si`.

Run tests: `nix develop --command python -m unittest discover -s tests`.

`shell.nix` is kept only as a legacy fallback.
