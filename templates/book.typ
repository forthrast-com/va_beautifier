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
//
// `make_book.py` writes a per-document copy with `__PDF_ACCENT__` replaced
// by a restrained ink colour derived from the document's canonical hue.

#let accent = rgb("__PDF_ACCENT__")
#let accent-rule = accent.lighten(38%)

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
  font: ("Libertinus Serif",),
  fontsize: 11pt,
  sectionnumbering: none,
  pagenumbering: "1",
  cols: 1,
) = {

  // ── Page ─────────────────────────────────────────────────────────────
  let page-margin = if paper == "a6" {
    (x: 9mm, top: 17mm, bottom: 11mm)
  } else { margin }
  set page(
    paper: paper,
    margin: page-margin,
    numbering: pagenumbering,
    number-align: center + bottom,
    header-ascent: if paper == "a6" { 6mm } else { 30% },
    footer-descent: if paper == "a6" { 5mm } else { 30% },
    header: context {
      let page_no = counter(page).get().first()
      let opens = query(selector(heading)).filter(
        heading => heading.level <= 2 and heading.location().page() == page_no
      )
      if page_no > 1 and opens.len() == 0 {
        // Running head picks up the doc accent so the head and the
        // hairline under it sit in the same hue. Lightened a touch so
        // the 8pt italic stays soft against the body.
        set text(size: 8pt, style: "italic", fill: accent.lighten(15%))
        // Verso carries the current top-level region (Preface / Part);
        // recto carries the current chapter, falling back to that region.
        let parts = query(selector(heading.where(level: 1)).before(here()))
        let chapters = query(selector(heading.where(level: 2)).before(here()))
        let verso = if parts.len() > 0 { parts.last().body } else { title }
        let recto = if chapters.len() > 0 { chapters.last().body } else { verso }
        align(
          if calc.odd(page_no) { right } else { left },
          if calc.odd(page_no) { recto } else { verso },
        )
        v(0.45em)
        line(length: 100%, stroke: (paint: accent-rule, thickness: 0.35pt))
      }
    },
  )

  // ── Text & paragraphs ────────────────────────────────────────────────
  set text(font: font, size: fontsize, lang: lang)
  show link: it => text(fill: rgb("#544b3f"), it)
  // Ragged-right rather than justified — typst 0.14 still ships no
  // microtype, so K-P with only word-space to spend produces visible
  // rivers in a footnoted ~58 char measure. Bringhurst-blessed setting
  // for a devotional reader, and the loose lines vanish into the medium.
  set par(
    justify: false,
    leading: 0.72em,
    first-line-indent: 1.1em,
  )
  // Block quotations already carry an inset. A prose first-line indent inside
  // them is redundant, and makes multi-paragraph declarations visibly drift.
  show quote.where(block: true): set par(first-line-indent: 0em)

  // ── Headings ─────────────────────────────────────────────────────────
  // Heading hierarchy after the EPUB structural fix:
  //   H1 = part (numbered parts in GeS; rare elsewhere).
  //   H2 = chapter (the primary structural unit).
  //   H3 = section.
  //   H4 = sub-heading.
  // Visual tier shifts down one slot to match, so chapters keep the
  // display look that used to live at H1.
  show heading.where(level: 1): it => block(sticky: true, {
    set text(size: 1.9em, weight: "regular", style: "italic", fill: accent)
    set par(first-line-indent: 0em, justify: false)
    v(2.4em)
    align(center, it.body)
    v(1.4em)
  })
  show heading.where(level: 2): it => block(sticky: true, {
    set text(size: 1.6em, weight: "regular", style: "italic", fill: accent)
    set par(first-line-indent: 0em, justify: false)
    v(2em)
    align(center, it.body)
    v(1.2em)
  })
  show heading.where(level: 3): it => block(sticky: true, {
    set text(size: 1.15em, weight: "regular", style: "italic", fill: accent)
    set par(first-line-indent: 0em, justify: false)
    v(1.2em)
    align(center, it.body)
    v(0.6em)
  })
  show heading.where(level: 4): it => block(sticky: true, {
    set text(size: 1em, style: "italic")
    set par(first-line-indent: 0em, justify: false)
    v(0.6em)
    it.body
    v(0.2em)
  })

  // ── Footnotes ────────────────────────────────────────────────────────
  // Page-bottom notes; the separator line is shorter than the default rule
  // so it reads as a typographic accent rather than a structural divider.
  set footnote.entry(
    separator: line(length: 28%, stroke: (paint: accent-rule, thickness: 0.4pt)),
    indent: 1.2em,
    gap: 0.65em,
  )
  show footnote.entry: it => {
    set text(size: 0.82em)
    it
  }

  // ── Outline / TOC ────────────────────────────────────────────────────
  // A fixed per-level indent leaves top-level entries flush with the body
  // text edge while preserving hierarchy below them. Typst's `auto` mode
  // indents even unnumbered top-level headings to reserve prefix space.
  set outline(indent: depth => (depth - 1) * 1.2em)
  // Lift the "Contents" heading to chapter-style italic display.
  show outline: it => {
    show heading: h => {
      set text(size: 1.6em, weight: "regular", style: "italic", fill: accent)
      set par(first-line-indent: 0em, justify: false)
      v(2em)
      align(center, h.body)
      v(1.2em)
    }
    it
  }

  doc
}
