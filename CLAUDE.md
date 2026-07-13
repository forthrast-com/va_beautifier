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
  by date, name, pope, class, or body-text word count

## Pipeline

    download_sources.py ──▶ sources/*.html ──(parse.py <slug>)──▶ build/<slug>.toml ──(make_html.py <slug>)──▶ site/<slug>.html
                                                │
                                                ├──(make_index.py)────────────▶  site/index.html
                                                │
                                                ├──(make_book.py <slug>)─────▶  site/downloads/<slug>.epub
                                                └──(make_book.py <slug>)─────▶  site/downloads/<slug>-{a4,a5,a6}.pdf

The TOML is the canonical intermediate. Downstream renderers consume TOML — never re-parse the Vatican HTML.

## Architecture

- `parse.py` — thin CLI. `argparse` with `choices` discovered via `pkgutil.iter_modules(extract.__path__)`; underscore-prefixed modules are dialect helpers and are filtered out. Loads `extract.<slug>`, calls its `extract()`, writes `<slug>.toml` via `core.write_toml`.
- `download_sources.py` — manifest-driven source fetcher. Lists or downloads implemented, queued, and reference-only Vatican pages into `sources/`; existing snapshots are preserved unless `--force` is passed.
- `core.py` — shared text/structure helpers, canonical paragraph and footnote
  constructors/context assignment, TOML loading and serialisation. The
  serialiser is the contract for document metadata, structure, appendices,
  signatories, and book-specific options. Canonical inline markup
  (`*em*`, `**strong**`, `<sup>`/`<sub>`) is converted once here
  (`inline_markup_to_html`, `INLINE_MARK_RE`); renderers must consume these
  rather than re-rolling their own regexes. Dialect-agnostic walker
  mechanics also live here: `HeadingState` (cascading heading resets),
  `numbered_paragraph` (the plain-then-rich double match), `heading_title`,
  `is_centred`, and `is_promulgation`.
- `extract/_curia.py`, `extract/_modern.py`, `extract/_oldflat.py` —
  per-dialect helper modules beside the extractors that use them
  (underscore-prefixed so `parse.py` discovery skips them). Curia:
  whitespace repair + anchor-delimited footnote extraction. Modern:
  `<main>` loading, the encyclical front-matter split, `CHAPTER ONE`
  markers. Old-flat: ISO-8859-1 load + `NOTES</b>` body/notes split,
  front-matter location.
- `project.py` — shared repository paths used by CLI and renderer entrypoints.
- `extract/<slug>.py` — per-document extractor. Each exposes `extract() -> dict`. Add a new document by dropping a new module here; no registry edit needed.
- `make_html.py <slug>` — reads `<slug>.toml`, writes a self-contained
  `site/<slug>.html` with CSS and JS inlined. It builds the sticky heading,
  scroll indicator, drawer contents/footnotes/bookmarks, appendices, and end
  matter. Body gets `class="doc-<slug>"` for scoped overrides.
- `make_index.py` — renders the catalogue cards and download controls from
  TOML. Client-side filtering, grouping, and sort preference persistence are
  inlined into `site/index.html`. Add tile metadata (`type`, plus `subtitle` or
  `kind_long`) in the document TOML/extractor for a fully authored card.
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
  catalogue; `make books` stops after EPUB/PDF; `make <slug>` builds one reader
  and `make <slug>-books` one document's EPUB/PDFs (generated aliases; `make
  list` prints the slugs, `make help` the target summary, `make test` runs the
  suite). `DOCS`, the per-source fetch rules, and the per-document TOML
  rules (with precise source + dialect-helper deps) are **generated** into
  `build/docs.mk` by `gen_doc_rules.py` from the `download_sources.py` manifest
  and each extractor's dialect import; the Makefile `include`s it and `make`
  re-execs after regenerating when the manifest or any extractor changes. So
  adding a doc needs no Makefile edit — drop the extractor (with `layout` +
  catalogue metadata in its return dict), add its `Source(...)` manifest
  entries, and write a regression test.
- `gen_doc_rules.py` — emits `build/docs.mk` (see above). Run by the Makefile;
  `python3 gen_doc_rules.py` alone prints the fragment to stdout.

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

An optional `[layout]` table carries per-document rendering flags
(`long`, `bare_sections`, `bare_chapters`, `mobile_inline`,
`capped_indicator`; canonical order in `core.LAYOUT_FLAGS`). Only truthy
flags are serialised; a doc with none (GeS) omits the table. See Renderer
conventions for what each flag drives.

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

GeS is served as **ISO-8859-1** (EN) and **latin-1** (LA), not UTF-8. LS, the modern encyclicals/exhortations (*Fides et Ratio*, *Lumen Fidei*, *Verbum Domini*), and the Curia Word-export pages are UTF-8. Sniff before assuming on any new document.

The ITC export has its first footnote anchor outside the paragraph wrapper
used by the remaining notes. `extract/_curia.py`'s `anchored_footnotes()`
therefore splits the note block at named `_ftnN` anchors instead of
assuming one note per paragraph.

Run `nix develop --command python download_sources.py --list` to see the
source manifest and local status; omit `--list` to fetch missing sources.
`--category queued` selects pending extractor inputs, while
`--category reference` selects captured contextual documents.

## Template variation

Three templates encountered so far:

- **Old flat** (GeS) — 24 `<p>` tags total, structure carried by `<b>` headings inside `<center>` blocks. Latin source provides a per-paragraph micro-summary keyed by §N. Footnotes in a separate `NOTES`-marked block.
- **Modern Bootstrap** (LS, MH, *Fides et Ratio*, *Lumen Fidei*, *Verbum
  Domini*, *Fratelli Tutti*, plus the Benedict XVI / JP II encyclicals
  *Deus Caritas Est*, *Spe Salvi*, *Caritas in Veritate*, and the
  exhortation *Ecclesia in Oceania*) — `<p>` tags wrapped in `<main>`. The base case (LS): chapter
  delimiter is a centred `CHAPTER ONE` followed by a centred `<b>` title;
  section is a `<p>` whose only child is a `<b>` matching `^[IVX]+\.`;
  sub-heading is a `<p>` whose only child is an `<i>`. The `align` attribute
  is unreliable (set on the first heading of chapter 1, blank thereafter);
  use child-shape tests. The modern dialect has drifted a lot across years,
  so expect per-document variation within it:
  - *Footnote refs.* Three spellings seen. LS uses bare `[N]`. LF gives every
    footnote anchor an **absolute** cross-document href, so
    `_modern.strip_footnote_anchors` unwraps the `<a name="_ftn…">` to its
    `[N]` text before the canonical `[N]` → `(N)` pass. VD uses the
    fragment `#_ftn` form `clean_text` already short-circuits, but is
    unwrapped too for uniformity. *Fides et Ratio* (a 1998 export) uses
    neither: body cites are `<sup><a name="-X">N</a></sup>` (the name suffix
    is a base-36-ish label, **not** the number — the number is the anchor
    text), and definitions are loose inline blocks after an `<hr>`, each
    `<font><b><a name="$N">N</a></b></font> text` split on the definition
    anchors (the `$` arrives percent-encoded as `%24`). *Caritas in Veritate*
    is a Word **endnote** export: same `[N]`-marker scheme but spelt
    `_edn{N}` / `_ednref{N}`, so `_modern.RE_FOOTNOTE_ANCHOR` matches both
    `ftn` and `edn` and `strip_footnote_anchors` handles it unchanged. Its
    chapter 4 heading stacks a three-item list on `<br/>` lines with no
    punctuation; the extractor repairs the joined title's commas via a
    keyed `CHAPTER_TITLE_REPAIRS` map (a generic comma-join would wreck
    ordinary wrapped titles like chapter 6's).
    *Ecclesia in Oceania* (2001) is different again: body cites are
    `<sup><a name="fnref{N}">(</a><a href="#fn{N}">N</a>)</sup>` — the
    parentheses are literal and the marker is split across two anchors (one
    `name`, one `href`); both halves are unwrapped so the cite collapses to a
    canonical `(N)`. Its definitions sit in a trailing `NOTES` block, each a
    `<p>` opening `(N) …`; note 21 wraps its leading `(21)` in the same `<i>`
    it opens for the next word, so the extractor lifts emphasis off the
    marker before parsing.
  - *Parts without chapters / bare chapters.* *Deus Caritas Est* has only
    `PART I` / `PART II` (Part II's title spreads `CARITAS` onto its own
    centred line, joined with a colon) and, within each part, italic-only
    topical headers that map to **bare chapters** (auto-numbered, no
    `Chapter N` prefix) so they read as H2 entries in the book TOCs. *Spe
    Salvi* has no `CHAPTER` markers at all — its all-bold topical headers are
    the primary divisions and likewise become bare chapters, with the
    centred-bold Roman `I./II./III.` subsections becoming its sections. Bare
    chapters render title-only via the `bare_chapters` layout flag (see
    Renderer conventions), the same path as the trailing `Conclusion`. DCE's and *Ecclesia in
    Oceania*'s closing prayers: DCE's is an untitled `<blockquote>` folded
    onto the last paragraph as italic verse (LF-style); EiO's carries an
    explicit italic `Prayer` heading and is lifted into a `kind="prayer"`
    appendix. EiO also exposes a finer italic-only sub-heading tier
    (`only_child_is(p, 'i')`, e.g. "The Permanent Diaconate"); guard that
    branch with `not is_promulgation` since the dateline is also a lone
    italic `<p>`.
  - *Psalm dual-numbering.* DCE/SS body text cites psalms as `Ps 73(72):25`
    (Hebrew vs Septuagint). `core.CANONICAL_FOOTNOTE_REF` carries a
    `(?<!\d)` lookbehind so a `(N)` glued to a preceding digit is not
    linkified as a footnote; the `test_site_artifacts` ref-check mirrors it.
  - *Unnumbered headings.* LF/VD/FeR have no Roman section tier; their bold
    topical headers become auto-numbered sections (à la MH) and the doc sets
    the `bare_sections` layout flag so the section renders as its bare title. Opening headings vary: FeR keeps its source "Blessing" and
    "Introduction" headings, and VD its "Introduction", as authored part-0
    titles; LF has no opening heading and so picks up the generated
    **Preamble** (see Renderer conventions). `CONCLUSION`
    is a trailing chapter titled `Conclusion`, which the non-roman
    `is_unnumbered` path renders without a `Chapter N` prefix — so **don't** set
    `chapter_style = "roman"` just because the source numbers chapters with
    Roman numerals (FeR parses `CHAPTER IV - TITLE` to an arabic number to
    keep that path; roman style would force a numeral onto the conclusion and
    would also relabel AeN's `I. Introduction`).
  - *Parts.* VD nests part (centred `PART ONE` + all-caps title + a dropped
    scriptural epigraph) › chapter (centred mixed-case) › section (bold).
  - *Loose body text.* VD's §1 is inline content trailing the `INTRODUCTION`
    heading outside any `<p>`, so `find_all('p')` misses it; it is recovered
    from the heading's inline next-siblings. A bracketing table of contents
    (titled `INDEX` at each end) is skipped by walking from the centred
    `INTRODUCTION` to the first footnote definition.
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

Doc-scoped CSS lives under `.doc-<slug>` selectors. Long structured documents share gutter-style paragraph numbers, soft-anchor positioning, and a height-capped scroll indicator. GeS keeps the original inline `5. *Latin heading* body` layout via the default rules + `.para-num::after { content: '.' }`.

**Layout flags (the `[layout]` TOML table).** Per-document rendering choices that used to live as hand-maintained slug sets scattered across `make_html`, `make_book`, and `styles.css` are now declared once per document. The extractor returns a `layout` dict; `core.write_toml` serialises it to a `[layout]` table (canonical flag order in `core.LAYOUT_FLAGS`); the renderers read `data['layout']` and `make_html` also stamps each truthy flag as a `layout-<flag>` body class (underscores → hyphens). `styles.css` targets those classes once instead of enumerating slugs. The flags:
  - `long` — gutter paragraph numbers + section-level sticky bar (`.layout-long`); replaced `make_html.LONG_DOCS`.
  - `bare_sections` — named topical sections, no `Section N:` prefix; replaced `make_html.BARE_SECTION_DOCS`.
  - `bare_chapters` — title-only chapters, no `Chapter N:` prefix, for sources with no chapter numbering (SS, DCE); replaced `make_html`/`make_book.BARE_CHAPTER_DOCS`. Drawer contents and no-JS TOC labels follow the same bare rendering via `make_html.chapter_group_label`, which also strips the prefix from a trailing `Conclusion` chapter to match the body's `is_unnumbered` path.
  - `mobile_inline` — narrow-viewport fallback to inline `5.` numbering (`.layout-mobile-inline`; LS/MH/AeN/QVH/SC).
  - `capped_indicator` — height-capped, chapter-segmented scroll indicator (`.layout-capped-indicator`; the above plus VD).

Genuinely bespoke per-doc CSS still uses `.doc-<slug>` (AeN's gutter chapter numeral, MH/QVH's third heading tier). Adding a standard long doc now needs **no** edit to `make_html`, `make_book`, or `styles.css` — only the `layout` dict in its extractor.

**Generated "Preamble" heading.** Opening prose at `part = 0`, `chapter = 0` with no authored `part_title` is unlabelled in the TOML; the renderer supplies a "Preamble" heading rather than leaving the region anchorless. It is a *generated display label*, not stored data, so it differs by surface: the **web body suppresses it** (anchor-only — the modern encyclicals don't want a redundant on-page heading) but keeps it in the contents drawer, scroll indicator, and no-JS TOC; the **PDF/EPUB render it visibly** (`make_book.py`), because those have no live navigation to fall back on. An authored `part_title` (GeS "Preface", SC "Introduction", QVH "Preliminary Note") always wins and shows on every surface; a part-0 group that opens straight into a chapter (AeN's roman `I. Introduction`) stays anchor-only under "Introduction".

JS publishes the sticky-bar's measured height to `--bar-h` so other layout (indicator centring, soft-anchor maths) can read it from CSS or JS.

Parted documents (VD, DCE, GeS) get part rows in the drawer contents tree
and no-JS TOC (`part_nav` → `.part-group` / `.ntoc-part`), mirroring the
body's Part I/II headings; the tracked-caps treatment is one CSS rule
shared with the in-text `h1.part-num` eyebrow.

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
- **More documents** — a reference capture recorded by
  `download_sources.py` for a possible future edition is
  `francis_g7_ai_en.html`. *Fratelli Tutti* is implemented: LS-shaped
  two-phase walk (same titled-prayer tail), but chapter titles are centred
  *non-bold* and the italic-only topical headers are its sole intra-chapter
  tier, promoted to auto-numbered bare sections. Its note stream carries
  three source defects — notes 86/112/185 lose their opening bracket to an
  empty anchor, note 98's marker is glued to its text, and note 119's
  definition shares note 118's `<p>` (split on the exact-successor
  `[N+1]` marker) — all repaired in the extractor and pinned by a
  regression test. The pipeline-invariant parity check is what caught all
  five.
- **Parallel build — verified.** A cold `make -j8` matches a cold serial
  build (byte-identical md/typ/toml intermediates, identical artefact
  inventory, site-artifact QA green in both modes; 42s → 12s locally,
  2026-07). CI uses `make -j8`; locally keep `-j` an explicit invocation
  flag rather than baking `MAKEFLAGS += -j` in, so single-doc incremental
  builds stay legible and stderr isn't interleaved.
## Extractor boundaries (implemented 2026-06)

The shared surface has two tiers. Dialect-agnostic walker mechanics live
in `core.py`: `HeadingState` (cascading part → chapter → section →
sub-heading resets, the historical extractor bug class), `numbered_paragraph`
(the plain-then-rich double match every walker previously hand-rolled),
`heading_title`, `is_centred`, `is_promulgation`. Dialect mechanics live
beside the extractors as underscore modules — `extract/_curia.py`
(anchored footnotes, Word-export text repair), `extract/_modern.py`
(`<main>` loading, the encyclical front-matter chain, `CHAPTER ONE`
markers), `extract/_oldflat.py` (ISO-8859-1 load, `NOTES</b>` split,
front-matter location). `parse.py` discovery filters underscore names so
they are never offered as documents.

Extractors keep facts (metadata, title lines) and quirks (SC's appendix
mode, split `CHAPTER VI`, and load-time repair of the snapshot's "81."
mis-numbering of ¶87; LS's two-phase body/tail split; QVH's
hidden-numbered preliminary note). There is deliberately still no
config-driven generic walker: the dialects diverge exactly where a
framework would need escape hatches, and the drop-a-file extractor
contract is the part of the design that works.

Shared mechanics keep growing as patterns prove out: `HeadingState.add_section`
(the auto-numbered bold-section idiom in LF/MH/FeR/VD) and
`_modern.is_signature_trailer` (the centred name line after the
promulgation). The modern dialect also converges on a single end-matter
shape — walk the body span up to `first_note_idx` (the first
`name="_ftnN"` definition anchor), then `extract_footnotes` the tail —
used by MH, VD, and now LF. **LS keeps the two-phase split** because its
tail interleaves *titled* prayer appendices with the footnotes, which the
single slice can't separate.

The single-pass shape is preferred for a reason beyond brevity: it captures
the whole body span and routes every paragraph, so nothing in the tail can
be *silently dropped*. LF's old walk was a half-copy of LS's two-phase that
forgot the closing Marian prayer (untitled, trailing §60) — the prayer fell
through the phase-2 loop and vanished. The lesson is **route, don't drop**:
an ad-hoc tail loop that only recognises footnote/promulgation/signature
discards anything else without a peep. Treat an unclassified non-empty `<p>`
in the body span as a bug, not a no-op; a regression test pins the recovered
prayer (`tests/test_extractors.py`).

One caution from the refactor:

- `is_centred` accepts either `align="center"` or a `text-align:center`
  inline style; before the refactor LS/QVH tested only the attribute and
  MH only the style. This is a deliberate (slight) widening — if a doc
  misclassifies a paragraph, look here first.

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
installed in the ambient shell. A tracked `.envrc` (`use flake`) loads the
shell via direnv/nix-direnv; without direnv, prefix commands with
`nix develop --command`. Build everything:
`nix develop --command make`. Build one book:
`nix develop --command python make_book.py laudato_si`.

Run tests: `nix develop --command python -m unittest discover -s tests`
(or `make test`). `tests/test_pipeline_invariants.py` is the generic tier:
bug-class invariants (unconverted `[N]` markers, source junk in text,
numbering continuity, folded-paragraph markers, scope-aware footnote
resolution, source-vs-TOML note parity, emphasis balance, catalogue
metadata) swept over every implemented document discovered from the
manifest — a new extractor inherits every lesson with no registration.
Pin document-specific facts in `test_extractors.py`; encode a new *class*
of defect as another invariant there instead.

`tools/audit_structure.py [slug …]` prints the human-side complement: each
built TOML as a part › chapter › section tree with paragraph ranges — the
view to eyeball when writing a new extractor.

`shell.nix` is kept only as a legacy fallback.
