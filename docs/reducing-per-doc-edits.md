# Reducing the per-document edit surface

Notes on cutting how many files you touch when adding a new edition. Written
after adding four Benedict XVI / JP II encyclicals, where the registry scatter
(not the extractor) was the real friction — `BARE_CHAPTER_DOCS` alone had to be
chased across `make_html`, `make_book`, *and* the CSS.

## What adding a doc costs today

| File | edits | irreducible? |
|---|---|---|
| `extract/<slug>.py` | the extractor | ✅ yes — the actual work |
| `tests/test_extractors.py` | a regression test | ✅ worth keeping |
| `download_sources.py` | 1 `Source(...)` manifest entry | mostly |
| `Makefile` | **3**: `DOCS` += slug, `FETCH_SOURCE` eval, explicit `build/<slug>.toml` rule | no |
| `make_html.py` | `LONG_DOCS`, `BARE_SECTION_DOCS`, `BARE_CHAPTER_DOCS` | no |
| `make_book.py` | `BARE_CHAPTER_DOCS` | no |
| `assets/styles.css` | the five `.doc-<slug>` gutter selector groups | no |

Everything below the line is hand-maintained membership lists that should
*derive from one source of truth*.

## Status

**#1 and #2 are done** (the `[layout]` TOML table + `layout-*` body classes).
While doing #2 the CSS turned out to hold *three* distinct slug groupings, not
one: the gutter layout (all 12 long docs), a narrow-viewport inline-numbering
fallback (5 docs), and the height-capped scroll indicator (6 docs). Each got
its own flag — `long`, `mobile_inline`, `capped_indicator` — so all three
collapsed to classes rather than leaving B/C enumerated. Canonical flag list is
`core.LAYOUT_FLAGS`.

**#3 is also done.** `gen_doc_rules.py` emits `build/docs.mk` (DOCS + fetch
rules + per-doc TOML rules) from the manifest + each extractor's dialect
import; the Makefile `include`s it and re-execs on change. Source-file deps
stay precise and fetch-on-demand survives. It uses GNU make's
remaking-makefiles idiom (make builds the include, then re-execs) — moderately
esoteric, but the only way to derive precise per-doc source deps in make.
Fixed a latent bug in passing: the old hand-written G7 fetch rule targeted a
filename the manifest no longer used.

## What to change (biggest win first)

### 1. Move layout flags onto the doc, like catalogue metadata already is — ✅ done

Catalogue metadata (`type` / `subtitle`) was already migrated out of a central
`make_index.CARD_META` dict and into the document TOML (commit `9a409c0`). Do
the same for the rendering flags `LONG_DOCS` / `BARE_SECTION_DOCS` /
`BARE_CHAPTER_DOCS`:

- the extractor returns `layout = {long, bare_sections, bare_chapters}` in its
  dict,
- `core` serialises it to TOML,
- `make_html` / `make_book` read `data['layout']` instead of testing membership
  in a hardcoded set.

→ **0 edits to `make_html` / `make_book`** when adding a doc. Cleanest,
lowest-risk, and mirrors a migration the codebase has already blessed.

### 2. Replace the per-slug CSS with shared layout classes — ✅ done

`make_html` already stamps `class="doc-<slug>"` on the body and knows the
flags. Have it also emit `layout-long` / `layout-bare-sections`. Then
`styles.css` targets `.layout-long .paragraph` **once** and the five enumerated
`.doc-<slug>` selector lists collapse. Bespoke per-doc CSS still uses
`.doc-<slug>`; a standard long doc needs **0 CSS edits**.

### 3. Derive the Makefile from the manifest — ✅ done (`gen_doc_rules.py` → `build/docs.mk`)

The three Makefile edits are all derivable. `parse.py` already discovers
extractors via `pkgutil.iter_modules(extract.__path__)`, and
`download_sources.py` already holds the source manifest. Generate `DOCS` + the
`FETCH_SOURCE` evals + a `build/<slug>.toml` rule from that single manifest (a
`$(shell …)` call or a tiny codegen step), so source deps stay precise without
hand-written rules.

→ **0 Makefile edits**. Fiddliest of the three (Make/shell plumbing), so do it
last.

## End state

Adding a doc becomes:

- **`extract/<slug>.py`** — with `layout` + catalogue metadata in its return dict
- **a regression test**
- **one `Source(...)` line** in `download_sources.py`

Down from seven files to effectively two-and-a-bit — and none of them are the
"remember to also add the slug to these four other lists" trap.

## Sequencing

#1 and #2 are the high-value, low-risk pair and dovetail with the shelved
extractor-driver refactor (`~/.claude/plans/composed-knitting-turing.md` — the
single-pass `walk_modern_body` + per-doc `recognise` callback). #3 is
independent and can land whenever.
