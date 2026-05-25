// templates/book.typ — pandoc-typst `conf` for va_beautifier book editions.
//
// Wired in via the markdown YAML frontmatter:
//
//     template: "templates/book.typ"
//
// Pandoc's default typst template imports `conf` from this file and calls
// it once with the body. Title page + end matter live in the markdown body
// as raw typst blocks (so `make_book.py` can build them from the TOML) —
// this file owns the typographic frame: page geometry, font defaults,
// heading shows, footnote entries, TOC styling.

#let conf(
  doc,
  title: none,
  subtitle: none,
  authors: (),
  keywords: (),
  date: none,
  lang: "en",
  region: none,
  abstract: none,
  margin: (x: 2.2cm, y: 2.4cm),
  paper: "a5",
  font: ("Hoefler Text",),
  fontsize: 11pt,
  sectionnumbering: none,
  pagenumbering: "1",
  cols: 1,
) = {

  // ── Page ─────────────────────────────────────────────────────────────
  set page(
    paper: paper,
    margin: margin,
    numbering: pagenumbering,
    number-align: center + bottom,
  )

  // ── Text & paragraphs ────────────────────────────────────────────────
  set text(font: font, size: fontsize, lang: lang)
  // First-line indent on body paragraphs is the canonical book look;
  // typst already suppresses the indent on the first paragraph of a
  // section, which is what we want here.
  set par(
    justify: true,
    leading: 0.72em,
    first-line-indent: 1.1em,
  )

  // ── Headings ─────────────────────────────────────────────────────────
  // H1: chapter title — large italic display, centred.
  show heading.where(level: 1): it => {
    set text(size: 1.6em, weight: "regular", style: "italic")
    set par(first-line-indent: 0em, justify: false)
    v(2em)
    align(center, it.body)
    v(1.2em)
  }
  // H2: section heading — medium italic, centred.
  show heading.where(level: 2): it => {
    set text(size: 1.15em, weight: "regular", style: "italic")
    set par(first-line-indent: 0em, justify: false)
    v(1.2em)
    align(center, it.body)
    v(0.6em)
  }
  // H3: subsection — bold, left-aligned, tighter.
  show heading.where(level: 3): it => {
    set text(size: 1em, weight: "bold")
    set par(first-line-indent: 0em, justify: false)
    v(0.8em)
    it.body
    v(0.3em)
  }
  // H4: italic sub-heading — slight emphasis only.
  show heading.where(level: 4): it => {
    set text(size: 1em, style: "italic")
    set par(first-line-indent: 0em, justify: false)
    v(0.6em)
    it.body
    v(0.2em)
  }

  // ── Footnotes ────────────────────────────────────────────────────────
  // Page-bottom notes; the separator line is shorter than the default rule
  // so it reads as a typographic accent rather than a structural divider.
  set footnote.entry(
    separator: line(length: 28%, stroke: 0.4pt),
    indent: 1.2em,
    gap: 0.65em,
  )
  show footnote.entry: it => {
    set text(size: 0.82em)
    it
  }

  // ── Outline / TOC ────────────────────────────────────────────────────
  // Lift the "Contents" heading to chapter-style italic display.
  show outline: it => {
    show heading: h => {
      set text(size: 1.6em, weight: "regular", style: "italic")
      set par(first-line-indent: 0em, justify: false)
      v(2em)
      align(center, h.body)
      v(1.2em)
    }
    it
  }

  doc
}
