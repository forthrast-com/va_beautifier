#!/usr/bin/env python3
"""Read <slug>.toml → emit <slug>.md → pandoc → <slug>.epub + <slug>.pdf.

Minimum viable book pipeline. The web edition leans on JS/CSS affordances
that don't translate; here we lean on pandoc's defaults plus typst as the
PDF engine. Footnotes ride pandoc's native `[^id]` syntax — EPUB lands
them at end-of-section, typst floats them to the bottom of the page.

Inline source emphasis and superscript/subscript content are carried through
the TOML as Pandoc-compatible markup for both book formats.
"""

import argparse
import shutil
import subprocess
import sys

from core import CANONICAL_FOOTNOTE_REF, int_to_roman, read_toml
from project import BUILD, ROOT

BUILD.mkdir(exist_ok=True)


def emit_markdown(data, slug):
    name        = data['name']
    desc        = data.get('desc', '')
    desc_post   = data.get('desc_post', '')
    promulg     = data.get('promulgation', '')
    signature   = data.get('signature', '')
    source_url  = data.get('source_url', '')
    hero_image  = data.get('hero_image', '')
    hero_credit = data.get('hero_credit', '')
    paragraphs  = data.get('paragraphs', [])
    footnotes   = data.get('footnotes', [])

    fn_index = {(f['part'], f['chapter'], f['number']): f for f in footnotes}
    used = {}  # ordered: (part, chapter, n) → footnote dict

    lines = []

    # YAML metadata block. Pandoc reads title/lang for the EPUB OPF; the
    # `template:` field points at our custom typst module which owns book
    # typography (page geom, headings, footnotes). Title page + end matter
    # are emitted as raw typst inline in the body — the EPUB writer
    # ignores raw typst, so EPUB falls back to pandoc's standalone title
    # page generated from the title metadata.
    # Hoefler Text is the right register for an encyclical: humanist,
    # warm, oldstyle figures, the face you find in good prayer books.
    # macOS-bundled. Override via VA_BOOK_FONT for other hosts.
    import os
    font = os.environ.get('VA_BOOK_FONT', 'Hoefler Text')
    # Typst restricts imports to the project root, so we pass `--root`
    # via `--pdf-engine-opt` in run_pandoc() and reference the template
    # as a typst-rooted path (leading `/`, relative to ROOT).
    lines += ['---', f'title: "{_yaml_q(name)}"']
    if source_url:
        # `source` is the dublin-core field the EPUB OPF picks up.
        lines.append(f'source: "{source_url}"')
    lines += [
        'lang: en',
        f'mainfont: "{font}"',
        'fontsize: 11pt',
        'papersize: a5',
        'template: "/templates/book.typ"',
        '...',
        '',
    ]

    # Title page is *not* emitted into the body — pandoc's typst template
    # renders the TOC before the body, so an inline title-page block
    # would land on page 2. Instead `make_book.py` writes the title-page
    # markdown to a sibling file and passes it via `--include-before-body`,
    # which fires before the TOC. See `_write_titlepage_include()` and
    # `run_pandoc()`.
    # A pagebreak at the start of the body itself ensures the first
    # content heading lands on a fresh page rather than sharing a page
    # with the tail of the TOC.
    lines += ['```{=typst}', '#pagebreak(weak: true)', '```', '']

    # ── Body walk ──────────────────────────────────────────────────────
    prev = {'part': None, 'chapter': None, 'section': None, 'sub': None}

    for p in paragraphs:
        part          = p.get('part', 0)
        part_title    = p.get('part_title', '')
        chapter       = p.get('chapter', 0)
        ch_title      = p.get('chapter_title', '')
        ch_subtitle   = p.get('chapter_subtitle', '')
        section       = p.get('section', 0)
        sec_title     = p.get('section_title', '')
        sub_heading   = p.get('sub_heading', '')
        heading_la    = p.get('heading_la', '')
        text          = p.get('text', '')
        number        = p.get('number', 0)

        # Part heading. `part=0` is preface/intro — render as a bare title
        # (no "Part N:" prefix), matching the web edition's `.part-title`.
        if part_title and part != prev['part']:
            label = part_title if part == 0 else f'Part {int_to_roman(part)}: {part_title}'
            lines.append('')
            lines.append(f'# {label}')
            lines.append('')
            prev.update(part=part, chapter=None, section=None, sub=None)

        # Chapter heading. Force a fresh page on the PDF side so chapters
        # land at the top of a recto — the EPUB writer ignores raw typst.
        if ch_title and chapter != prev['chapter']:
            level = '##' if any(p2.get('part_title') for p2 in paragraphs) else '#'
            unnumbered = ch_title.strip().lower() in ('conclusion', 'preface', 'introduction')
            label = ch_title if unnumbered or chapter == 0 else f'Chapter {chapter}: {ch_title}'
            lines += ['', '```{=typst}', '#pagebreak(weak: true)', '```', '']
            lines.append(f'{level} {label}')
            lines.append('')
            if ch_subtitle:
                lines.append(f'*{ch_subtitle}*')
                lines.append('')
            prev.update(chapter=chapter, section=None, sub=None)

        # Section heading.
        if sec_title and section != prev['section']:
            level = '###' if any(p2.get('part_title') for p2 in paragraphs) else '##'
            lines.append('')
            lines.append(f'{level} {sec_title}')
            lines.append('')
            prev.update(section=section, sub=None)

        # Sub-heading.
        if sub_heading and sub_heading != prev['sub']:
            level = '####' if any(p2.get('part_title') for p2 in paragraphs) else '###'
            lines.append('')
            lines.append(f'{level} {sub_heading}')
            lines.append('')
            prev['sub'] = sub_heading

        # Optional Latin micro-summary (GeS) — italicised, on its own line
        # ahead of the paragraph.
        if heading_la:
            lines.append(f'*{heading_la}*')
            lines.append('')

        # Body text with footnote refs rewired to pandoc syntax.
        def replace_ref(m, _part=part, _chapter=chapter):
            n = int(m.group(1))
            key = (_part, _chapter, n)
            if key in fn_index:
                used[key] = fn_index[key]
                return f'[^{_part}-{_chapter}-{n}]'
            # No matching definition — leave the literal `(N)` alone so
            # the artefact reads as the Vatican source does.
            return m.group(0)

        body = CANONICAL_FOOTNOTE_REF.sub(replace_ref, text)
        # Sub-paragraphs are separated by `\n\n` in the TOML; pandoc honours
        # blank-line separators. First sub-paragraph gets the bold number.
        chunks = [c.strip() for c in body.split('\n\n') if c.strip()]
        if chunks and not p.get('hide_number', False):
            chunks[0] = f'**{number}.** {chunks[0]}'
        for chunk in chunks:
            lines.append(chunk)
            lines.append('')

        if p.get('break_after'):
            lines.append('***')
            lines.append('')

    # ── End matter ─────────────────────────────────────────────────────
    # Dedication + papal signature land on their own page, centred. We
    # emit two format-gated raw blocks (one typst, one html) so each
    # output gets the styling appropriate to its medium without the
    # other writer rendering a duplicate.
    if promulg or signature:
        lines += ['```{=typst}', _end_matter_typst(promulg, signature), '```', '']
        lines += ['```{=html}', _end_matter_html(promulg, signature), '```', '']

    # ── Footnote definitions ───────────────────────────────────────────
    # Emit at the bottom of the markdown. Pandoc's EPUB writer places
    # them at end-of-section; the typst writer floats them to page bottom.
    lines.append('')
    for (part, chapter, n), fn in used.items():
        # Split on \n\n so each sub-paragraph becomes a real pandoc footnote
        # paragraph. Single \n inside a sub-paragraph is treated as a soft
        # break (typst handles this naturally; pandoc wraps it).
        text = fn['text'].rstrip()
        paragraphs_fn = [p.strip() for p in text.split('\n\n') if p.strip()]
        first, *rest = paragraphs_fn or ['']
        lines.append(f'[^{part}-{chapter}-{n}]: {first}')
        for paragraph in rest:
            # Pandoc keeps a footnote alive across blank lines only when the
            # blank itself is indented; the body of the continuation needs
            # its own 4-space indent too.
            lines.append('    ')
            lines.append(f'    {paragraph}')
        lines.append('')

    md_path = BUILD / f'{slug}.md'
    md_path.write_text('\n'.join(lines), encoding='utf-8')
    return md_path


def _yaml_q(s):
    """Minimal YAML quoting for the title string."""
    return s.replace('\\', '\\\\').replace('"', '\\"')


def _typ_str(s):
    r"""Quote a Python string for embedding in typst source. Typst strings
    are double-quoted with `\\` and `\"` escapes; everything else rides
    through unchanged."""
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'


def _typ_content(s):
    """Quote a Python string for typst content (inside `[...]` brackets).
    Backslash and bracket are the meaningful escapes inside content."""
    return s.replace('\\', '\\\\').replace('[', '\\[').replace(']', '\\]')


def _title_page_typst(name, desc, desc_post, hero_image, hero_credit):
    """Render the title page as raw typst. The 1fr vertical fillers above
    and below the title block centre it on the page; with a hero image
    the block sits a little high to give the image room to breathe. The
    typst template paths use `/`-rooted paths (typst resolves these
    relative to the project root set via `--root`)."""
    parts = ['#page(numbering: none, header: none)[', '  #set align(center)', '  #v(1fr)']

    if hero_image:
        # Typst paths starting with `/` are project-root-relative — the
        # build script sets the root to ROOT, so this resolves to
        # <ROOT>/<hero_image>.
        path = '/' + hero_image.lstrip('/')
        parts.append(f'  #image({_typ_str(path)}, width: 65%)')
        if hero_credit:
            parts.append('  #v(0.4em)')
            parts.append(f'  #text(size: 8pt, style: "italic")[{_typ_content(hero_credit)}]')
        parts.append('  #v(2.5em)')

    def stacked(block, size, tracking):
        bits = [_typ_content(ln.strip()) for ln in block.splitlines() if ln.strip()]
        if not bits:
            return
        inner = ' \\\n    '.join(bits)
        parts.append(f'  #text(size: {size}, tracking: {tracking})[')
        parts.append(f'    {inner}')
        parts.append('  ]')

    if desc:
        stacked(desc.upper(), '10pt', '0.08em')
        parts.append('  #v(1.8em)')

    parts.append(f'  #text(size: 28pt, style: "italic")[{_typ_content(name)}]')
    parts.append('  #v(1.1em)')
    parts.append('  #line(length: 18%, stroke: 0.5pt)')

    if desc_post:
        parts.append('  #v(1.8em)')
        stacked(desc_post.upper(), '10pt', '0.08em')

    # `#page()` configures page properties; the trailing `#pagebreak()`
    # ensures the TOC starts on the next physical page instead of
    # flowing into whatever space remains.
    parts += ['  #v(1fr)', ']', '#pagebreak()']
    return '\n'.join(parts)


def _write_titlepage_include(data, slug):
    """Write a raw typst file containing the title page. Pandoc's
    `--include-before-body` inserts file contents *verbatim* into the
    output (after pandoc's own setup, before the TOC) — so this file
    must be valid typst, not markdown."""
    title_typst = _title_page_typst(
        data['name'],
        data.get('desc', ''),
        data.get('desc_post', ''),
        data.get('hero_image', ''),
        data.get('hero_credit', ''),
    )
    path = BUILD / f'{slug}_titlepage.typ'
    path.write_text(title_typst + '\n', encoding='utf-8')
    return path


def _promulgation_stanzas(promulg):
    """Yield each `\\n\\n`-separated stanza of a promulgation block, with
    intra-stanza linebreaks collapsed to single spaces."""
    for stanza in promulg.split('\n\n'):
        text = ' '.join(line.strip() for line in stanza.splitlines() if line.strip())
        if text:
            yield text


def _end_matter_typst(promulg, signature):
    """Render dedication + signature as a centred standalone page. Multi-
    stanza promulgations (A&N: audience block + offices block) render on
    separate lines so the source's logical paragraph break carries through
    to the PDF."""
    parts = [
        '#pagebreak(weak: true)',
        '#page()[',
        '  #set align(center)',
        '  #v(1fr)',
    ]
    stanzas = list(_promulgation_stanzas(promulg)) if promulg else []
    for index, stanza in enumerate(stanzas):
        if index:
            parts.append('  #v(0.9em)')
        parts.append(f'  #text(style: "italic", size: 11pt)[{_typ_content(stanza)}]')
    if stanzas:
        parts.append('  #v(2em)')
    if signature:
        parts.append(f'  #text(weight: "bold", tracking: 0.14em)[{_typ_content(signature)}]')
    parts += ['  #v(1fr)', ']']
    return '\n'.join(parts)


def _end_matter_html(promulg, signature):
    """EPUB end matter — semantic colophon section with centred styles."""
    import html
    parts = ['<section epub:type="colophon" style="text-align:center; margin-top:4em;">']
    for stanza in _promulgation_stanzas(promulg) if promulg else ():
        parts.append(f'<p style="font-style:italic;">{html.escape(stanza)}</p>')
    if signature:
        parts.append(f'<p style="font-weight:bold; letter-spacing:0.14em; margin-top:1.5em;">{html.escape(signature)}</p>')
    parts.append('</section>')
    return '\n'.join(parts)


def run_pandoc(md_path, out_path, *extra):
    cmd = [
        'pandoc', str(md_path),
        '-o', str(out_path),
        '--standalone',
        '--toc',
        '--toc-depth=2',
        '-f', 'markdown+smart',
        *extra,
    ]
    print(f'  → {out_path.name}', flush=True)
    subprocess.run(cmd, check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('slug')
    ap.add_argument('--epub-only', action='store_true')
    ap.add_argument('--pdf-only', action='store_true')
    args = ap.parse_args()

    toml_path = BUILD / f'{args.slug}.toml'
    if not toml_path.exists():
        sys.exit(f'no TOML for {args.slug}; run parse.py first')

    data = read_toml(toml_path)

    print(f'[{args.slug}] markdown')
    md_path = emit_markdown(data, args.slug)
    titlepage_path = _write_titlepage_include(data, args.slug)

    if not shutil.which('pandoc'):
        sys.exit('pandoc not found on PATH — install via Home Manager or nix-shell')

    do_epub = not args.pdf_only
    do_pdf  = not args.epub_only

    if do_epub:
        # EPUB ignores raw typst blocks, so the title-page include is a
        # no-op; the EPUB picks up its title from YAML metadata instead.
        run_pandoc(md_path, BUILD / f'{args.slug}.epub')

    if do_pdf:
        if shutil.which('typst'):
            # `--root` tells typst where the project root is, so the
            # `template:` path in the markdown (which starts with `/`)
            # resolves to <ROOT>/templates/book.typ.
            run_pandoc(md_path, BUILD / f'{args.slug}.pdf',
                       '--pdf-engine=typst',
                       f'--pdf-engine-opt=--root={ROOT}',
                       f'--include-before-body={titlepage_path}')
        else:
            print('  ! typst not found, skipping PDF')


if __name__ == '__main__':
    main()
