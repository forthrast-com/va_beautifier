#!/usr/bin/env python3
"""Read <slug>.toml -> emit intermediates and site/downloads book artefacts.

Minimum viable book pipeline. The web edition leans on JS/CSS affordances
that don't translate; here we lean on pandoc's defaults plus typst as the
PDF engine. Footnotes ride pandoc's native `[^id]` syntax — EPUB lands
them at end-of-section, typst floats them to the bottom of the page.

Inline source emphasis and superscript/subscript content are carried through
the TOML as Pandoc-compatible markup for both book formats.
"""

import argparse
import colorsys
import html
import re
import shutil
import subprocess
import sys

from core import CANONICAL_FOOTNOTE_REF, int_to_roman, read_toml
from project import BUILD, DOWNLOADS, ROOT

BUILD.mkdir(exist_ok=True)
DOWNLOADS.mkdir(parents=True, exist_ok=True)


def emit_markdown(data, slug, *, paper='a5', template_slug=None):
    # Output slug controls the .md filename; the template slug points at
    # the per-doc typst module on disk. Both default to the same value
    # unless an A4 variant is being emitted from the canonical doc.
    template_slug = template_slug or slug
    name        = data['name']
    desc        = data.get('desc', '')
    desc_post   = data.get('desc_post', '')
    promulg     = data.get('promulgation', '')
    signature   = data.get('signature', '')
    signatories = data.get('signatories', [])
    source_url  = data.get('source_url', '')
    hero_image  = data.get('hero_image', '')
    hero_credit = data.get('hero_credit', '')
    pdf_accent  = _pdf_accent(data.get('hue', 42))
    paragraphs  = data.get('paragraphs', [])
    footnotes   = data.get('footnotes', [])
    appendices  = data.get('appendices', [])

    fn_index = {(f['part'], f['chapter'], f['number']): f for f in footnotes}
    used = {}  # ordered: (part, chapter, n) → footnote dict

    lines = []

    # YAML metadata block. Pandoc maps these to EPUB OPF dublin-core:
    # title → dc:title, author → dc:creator, date → dc:date, publisher
    # → dc:publisher, identifier → dc:identifier (we prefix urn:circulars:
    # so the identifier is globally unique under our scheme), rights →
    # dc:rights, source → dc:source, belongs-to-collection → meta.
    # dcterms:modified is auto-stamped from build time by pandoc.
    # For the PDF, the `template:` field points at our custom typst module
    # which owns book typography (page geom, headings, footnotes). Title
    # page + end matter are emitted as raw typst inline in the body —
    # the EPUB writer ignores raw typst, so EPUB falls back to pandoc's
    # standalone title page generated from the title metadata.
    # Hoefler Text is the right register for an encyclical: humanist,
    # warm, oldstyle figures, the face you find in good prayer books.
    # macOS-bundled. Override via VA_BOOK_FONT for other hosts.
    import os
    font = os.environ.get('VA_BOOK_FONT', 'Hoefler Text')
    # Typst restricts imports to the project root, so we pass `--root`
    # via `--pdf-engine-opt` in run_pandoc() and reference the template
    # as a typst-rooted path (leading `/`, relative to ROOT).
    lines += ['---', f'title: "{_yaml_q(name)}"']
    if data.get('author'):
        lines.append(f'author: "{_yaml_q(data["author"])}"')
    if data.get('date'):
        lines.append(f'date: "{data["date"]}"')
    if data.get('publisher'):
        lines.append(f'publisher: "{_yaml_q(data["publisher"])}"')
    if data.get('rights'):
        lines.append(f'rights: "{_yaml_q(data["rights"])}"')
    if data.get('identifier'):
        lines.append(f'identifier: "urn:circulars:{data["identifier"]}"')
    if data.get('collection'):
        lines.append(
            f'belongs-to-collection: "{_yaml_q(data["collection"])}"'
        )
    if source_url:
        lines.append(f'source: "{source_url}"')
    # A4 is the large-print variant: bigger type and wider margins so the
    # measure stays comfortable instead of stretching to 80+ chars at 11pt.
    fontsize = '13pt' if paper == 'a4' else '11pt'
    lines += [
        'lang: en',
        f'mainfont: "{font}"',
        f'fontsize: {fontsize}',
        f'papersize: {paper}',
        f'template: "/build/{_pdf_template_name(template_slug)}"',
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

    # Heading levels are uniform: chapters at H2 (so --epub-chapter-level=2
    # splits one spine file per chapter), sections at H3, sub-headings at
    # H4. Numbered parts (only GeS has them) take H1. Prefatory part_titles
    # (Preliminary Note, Introduction) emit at H2 when there are no numbered
    # parts so they sit alongside chapters rather than above them; otherwise
    # they stay at H1 alongside the numbered parts.
    has_numbered_parts = any(p2.get('part', 0) > 0 for p2 in paragraphs)

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

        if part_title and part != prev['part']:
            if part > 0:
                level, label = '#', f'Part {int_to_roman(part)}: {part_title}'
            elif has_numbered_parts:
                level, label = '#', part_title
            else:
                level, label = '##', part_title
            lines.append('')
            lines.append(f'{level} {label}')
            lines.append('')
            prev.update(part=part, chapter=None, section=None, sub=None)

        # Chapter heading. Force a fresh page on the PDF side so chapters
        # land at the top of a recto — the EPUB writer ignores raw typst.
        if ch_title and chapter != prev['chapter']:
            unnumbered = ch_title.strip().lower() in ('conclusion', 'preface', 'introduction')
            label = ch_title if unnumbered or chapter == 0 else f'Chapter {chapter}: {ch_title}'
            lines += ['', '```{=typst}', '#pagebreak(weak: true)', '```', '']
            lines.append(f'## {label}')
            lines.append('')
            if ch_subtitle:
                lines.append(f'*{ch_subtitle}*')
                lines.append('')
            prev.update(chapter=chapter, section=None, sub=None)

        if sec_title and section != prev['section']:
            lines.append('')
            lines.append(f'### {sec_title}')
            lines.append('')
            prev.update(section=section, sub=None)

        if sub_heading and sub_heading != prev['sub']:
            lines.append('')
            lines.append(f'#### {sub_heading}')
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

    # ── Appendices ─────────────────────────────────────────────────────
    # Appendices remain ordinary canonical text so all output formats keep
    # them. Emit at H2 so each lands as its own EPUB spine file under
    # `--epub-chapter-level=2`. Single line breaks are significant in LS's
    # closing prayers.
    for appendix in appendices:
        lines += [
            '',
            f'## {appendix["title"]}',
            '',
            _markdown_preserve_breaks(appendix['text']),
            '',
        ]

    # ── End matter ─────────────────────────────────────────────────────
    # Promulgation, signatories and signature land on their own page, centred. We
    # emit two format-gated raw blocks (one typst, one html) so each
    # output gets the styling appropriate to its medium without the
    # other writer rendering a duplicate.
    if promulg or signatories or signature:
        lines += [
            '```{=typst}',
            _end_matter_typst(promulg, signatories, signature, pdf_accent),
            '```',
            '',
        ]
        lines += [
            '```{=html}',
            _end_matter_html(promulg, signatories, signature),
            '```',
            '',
        ]

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


def _pdf_accent(hue):
    """Derive a muted, print-friendly display ink from a document hue."""
    r, g, b = colorsys.hls_to_rgb((float(hue) % 360) / 360, 0.34, 0.30)
    return f'#{round(r * 255):02x}{round(g * 255):02x}{round(b * 255):02x}'


def _pdf_template_name(slug):
    """Avoid Pandoc escaping underscores in Typst import metadata paths."""
    return f'{slug.replace("_", "-")}-book.typ'


def _markdown_preserve_breaks(text):
    """Keep canonical stanza and poetic line breaks in pandoc markdown."""
    return '\n\n'.join(
        '  \n'.join(line.rstrip() for line in stanza.splitlines())
        for stanza in text.split('\n\n')
        if stanza.strip()
    )


def _typ_str(s):
    r"""Quote a Python string for embedding in typst source. Typst strings
    are double-quoted with `\\` and `\"` escapes; everything else rides
    through unchanged."""
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'


def _typ_content(s):
    """Quote a Python string for typst content (inside `[...]` brackets).
    Backslash, code markers and brackets are meaningful inside content."""
    return (s.replace('\\', '\\\\').replace('#', '\\#')
            .replace('[', '\\[').replace(']', '\\]'))


INLINE_MARK_RE = re.compile(
    r'\*\*(.+?)\*\*|(?<!\*)\*(.+?)\*(?!\*)', re.DOTALL
)


def _typ_inline(s, *, preserve_breaks=False):
    """Convert canonical bold/italic content to raw typst content."""
    def literal(text):
        text = _typ_content(text)
        return text.replace('\n', ' \\\n    ') if preserve_breaks else text

    rendered = []
    pos = 0
    for match in INLINE_MARK_RE.finditer(s):
        rendered.append(literal(s[pos:match.start()]))
        content = literal(match.group(1) or match.group(2))
        command = 'strong' if match.group(1) is not None else 'emph'
        rendered.append(f'#{command}[{content}]')
        pos = match.end()
    rendered.append(literal(s[pos:]))
    return ''.join(rendered)


def _html_inline(s, *, preserve_breaks=False):
    """Convert canonical bold/italic content to raw EPUB HTML content."""
    rendered = html.escape(s)
    rendered = re.sub(
        r'\*\*(.+?)\*\*', r'<strong>\1</strong>', rendered, flags=re.DOTALL
    )
    rendered = re.sub(
        r'(?<!\*)\*(.+?)\*(?!\*)', r'<em>\1</em>', rendered, flags=re.DOTALL
    )
    return rendered.replace('\n', '<br />') if preserve_breaks else rendered


def _title_page_typst(name, desc, desc_post, hero_image, hero_credit, accent,
                      paper='a5'):
    """Render the title page as raw typst. The 1fr vertical fillers above
    and below the title block centre it on the page; with a hero image
    the block sits a little high to give the image room to breathe. The
    typst template paths use `/`-rooted paths (typst resolves these
    relative to the project root set via `--root`).

    `paper` scales typography by the long-edge ratio so the A4 large-print
    edition doesn't ring with empty space around an A5-scale title block."""
    scale = 1.4 if paper == 'a4' else 1.0
    title_pt   = round(28 * scale)
    label_pt   = round(10 * scale)
    hero_gap   = f'{2.5 * scale:.2f}em'
    block_gap  = f'{1.8 * scale:.2f}em'
    line_gap   = f'{1.1 * scale:.2f}em'

    parts = ['#page(numbering: none, header: none)[', '  #set align(center)', '  #v(1fr)']

    if hero_image:
        # Typst paths starting with `/` are project-root-relative — the
        # build script sets the root to ROOT, so this resolves to
        # <ROOT>/<hero_image>.
        path = '/' + hero_image.lstrip('/')
        parts.append(f'  #image({_typ_str(path)}, width: 65%)')
        if hero_credit:
            parts.append('  #v(0.4em)')
            parts.append(
                f'  #text(size: {round(8 * scale)}pt, style: "italic")'
                f'[{_typ_content(hero_credit)}]'
            )
        parts.append(f'  #v({hero_gap})')

    def stacked(block, size, tracking):
        bits = [_typ_content(ln.strip()) for ln in block.splitlines() if ln.strip()]
        if not bits:
            return
        inner = ' \\\n    '.join(bits)
        parts.append(f'  #text(size: {size}pt, tracking: {tracking})[')
        parts.append(f'    {inner}')
        parts.append('  ]')

    if desc:
        stacked(desc.upper(), label_pt, '0.08em')
        parts.append(f'  #v({block_gap})')

    parts.append(
        f'  #text(size: {title_pt}pt, style: "italic", fill: rgb("{accent}"))'
        f'[{_typ_content(name)}]'
    )
    parts.append(f'  #v({line_gap})')
    parts.append(
        f'  #line(length: 18%, stroke: (paint: rgb("{accent}"), thickness: 0.5pt))'
    )

    if desc_post:
        parts.append(f'  #v({block_gap})')
        stacked(desc_post.upper(), label_pt, '0.08em')

    # `#page()` configures page properties; the trailing `#pagebreak()`
    # ensures the TOC starts on the next physical page instead of
    # flowing into whatever space remains.
    parts += ['  #v(1fr)', ']', '#pagebreak()']
    return '\n'.join(parts)


def _write_titlepage_include(data, slug, *, paper='a5'):
    """Write a raw typst file containing the title page. Pandoc's
    `--include-before-body` inserts file contents *verbatim* into the
    output (after pandoc's own setup, before the TOC) — so this file
    must be valid typst, not markdown. A separate file per paper size
    is cheap (a kilobyte) and lets the title typography scale per page."""
    title_typst = _title_page_typst(
        data['name'],
        data.get('desc', ''),
        data.get('desc_post', ''),
        data.get('hero_image', ''),
        data.get('hero_credit', ''),
        _pdf_accent(data.get('hue', 42)),
        paper=paper,
    )
    path = BUILD / f'{slug}_titlepage_{paper}.typ'
    path.write_text(title_typst + '\n', encoding='utf-8')
    return path


def _write_pdf_template(data, slug):
    """Materialise the shared Typst template with this document's accent."""
    accent = _pdf_accent(data.get('hue', 42))
    source = (ROOT / 'templates' / 'book.typ').read_text(encoding='utf-8')
    path = BUILD / _pdf_template_name(slug)
    path.write_text(source.replace('__PDF_ACCENT__', accent), encoding='utf-8')
    return path


def _cover_typst(data):
    """Standalone typst doc for the EPUB cover.

    Compiles at A5 aspect to match the PDF reading edition — so the
    cover, the title page, and a printed copy all share proportions. At
    300 ppi this renders to roughly 1748 × 2480 px, comfortably above
    Apple Books' minimum cover spec."""
    name        = data['name']
    desc        = data.get('desc', '')
    desc_post   = data.get('desc_post', '')
    hero_image  = data.get('hero_image', '')
    hero_credit = data.get('hero_credit', '')
    accent      = _pdf_accent(data.get('hue', 42))
    author      = data.get('author', '')

    parts = [
        '#set page(paper: "a5", margin: (x: 18mm, y: 22mm))',
        '#set text(font: "Hoefler Text", size: 12pt)',
        '#set align(center)',
    ]

    parts.append('#v(1fr)')

    if hero_image:
        path = '/' + hero_image.lstrip('/')
        parts.append(f'#image({_typ_str(path)}, width: 76%)')
        if hero_credit:
            parts.append('#v(0.5em)')
            parts.append(
                f'#text(size: 8pt, style: "italic")'
                f'[{_typ_content(hero_credit)}]'
            )
        parts.append('#v(2em)')

    def stacked(block, size, tracking):
        bits = [_typ_content(ln.strip()) for ln in block.splitlines() if ln.strip()]
        if not bits:
            return
        inner = ' \\\n  '.join(bits)
        parts.append(f'#text(size: {size}, tracking: {tracking})[')
        parts.append(f'  {inner}')
        parts.append(']')

    if desc:
        stacked(desc.upper(), '11pt', '0.08em')
        parts.append('#v(1.8em)')

    parts.append(
        f'#text(size: 32pt, style: "italic", fill: rgb("{accent}"))'
        f'[{_typ_content(name)}]'
    )
    parts.append('#v(1.1em)')
    parts.append(
        f'#line(length: 20%, stroke: (paint: rgb("{accent}"), thickness: 0.6pt))'
    )

    if desc_post:
        parts.append('#v(1.8em)')
        stacked(desc_post.upper(), '11pt', '0.08em')

    parts.append('#v(1fr)')

    if author:
        parts.append(
            f'#text(size: 9pt, tracking: 0.14em, fill: rgb("#5a5147"))'
            f'[{_typ_content(author.upper())}]'
        )
        parts.append('#v(0.4em)')

    return '\n'.join(parts) + '\n'


def _write_cover(data, slug):
    """Render and compile the cover. Returns the path on success or
    None when typst is unavailable (cover is then omitted from the EPUB
    rather than failing the build). 300 ppi on A5 yields ~1748 × 2480 px,
    well above Apple Books' minimum cover dimensions."""
    if not shutil.which('typst'):
        return None
    typ_path = BUILD / f'{slug}_cover.typ'
    png_path = BUILD / f'{slug}_cover.png'
    typ_path.write_text(_cover_typst(data), encoding='utf-8')
    cmd = [
        'typst', 'compile',
        '--ppi', '300',
        '--root', str(ROOT),
        str(typ_path), str(png_path),
    ]
    subprocess.run(cmd, check=True)
    return png_path


def _promulgation_stanzas(promulg):
    """Yield each `\\n\\n`-separated stanza of a promulgation block, with
    intra-stanza linebreaks collapsed to single spaces."""
    for stanza in promulg.split('\n\n'):
        text = ' '.join(line.strip() for line in stanza.splitlines() if line.strip())
        if text:
            yield text


def _end_matter_typst(promulg, signatories, signature, accent='#756d60'):
    """Render structured end matter as a centred standalone page. Multi-
    stanza promulgations (A&N: audience block + offices block) render on
    separate lines; optional signatories occupy a two-column roster."""
    parts = [
        '#pagebreak(weak: true)',
        '#page()[',
        '  #set align(center)',
        '  #v(1fr)',
    ]
    stanzas = list(_promulgation_stanzas(promulg)) if promulg else []
    if stanzas:
        parts += [
            f'  #line(length: 35%, stroke: (paint: rgb("{accent}"), thickness: 0.5pt))',
            '  #v(1.5em)',
        ]
    for index, stanza in enumerate(stanzas):
        if index:
            parts.append('  #v(0.9em)')
        parts.append(f'  #text(size: 11pt)[{_typ_inline(stanza)}]')
    if stanzas:
        parts.append('  #v(2em)')
    if signatories:
        parts += [
            '  #grid(',
            '    columns: (1fr, 1fr),',
            '    column-gutter: 1.8em,',
            '    row-gutter: 1.3em,',
            '    align: center,',
        ]
        for signatory in signatories:
            name = _typ_content(signatory.get('name', ''))
            role = _typ_content(signatory.get('role', ''))
            parts.append(
                f'    [{name} \\ #text(size: 9pt, style: "italic")[{role}]],'
            )
        parts += ['  )', '  #v(2em)']
    if signature:
        parts.append(
            f'  #text(tracking: 0.14em)[{_typ_inline(signature, preserve_breaks=True)}]'
        )
    parts += ['  #v(1fr)', ']']
    return '\n'.join(parts)


def _end_matter_html(promulg, signatories, signature):
    """EPUB end matter: semantic colophon with optional signatory roster.

    No leading rule — on a printed page the matching typst `#line(...)`
    reads as a colophon device, but in EPUB a 35%-wide hairline before
    a centred block reads as stray punctuation between body and ending.
    Style hooks live in templates/epub.css via epub:type="colophon"."""
    parts = ['<section epub:type="colophon">']
    for stanza in _promulgation_stanzas(promulg) if promulg else ():
        parts.append(f'<p>{_html_inline(stanza)}</p>')
    if signatories:
        parts.append('<div style="margin:2em 0;">')
        for signatory in signatories:
            name = html.escape(signatory.get('name', ''))
            role = html.escape(signatory.get('role', ''))
            parts.append(
                f'<p style="margin:1em 0;">{name}<br />'
                f'<em>{role}</em></p>'
            )
        parts.append('</div>')
    if signature:
        parts.append(
            '<p style="letter-spacing:0.14em; margin-top:1.5em;">'
            f'{_html_inline(signature, preserve_breaks=True)}</p>'
        )
    parts.append('</section>')
    return '\n'.join(parts)


def run_pandoc(md_path, out_path, *extra):
    # `--toc-depth` is left to the caller so EPUB (drawer-parity, depth 4)
    # and PDF (book-convention, depth 3) can diverge.
    cmd = [
        'pandoc', str(md_path),
        '-o', str(out_path),
        '--standalone',
        '--toc',
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
    _write_pdf_template(data, args.slug)
    md_path = emit_markdown(data, args.slug)
    md_path_a4 = emit_markdown(
        data, args.slug + '_a4', paper='a4', template_slug=args.slug
    )
    titlepage_a5 = _write_titlepage_include(data, args.slug, paper='a5')
    titlepage_a4 = _write_titlepage_include(data, args.slug, paper='a4')
    cover_path = _write_cover(data, args.slug)

    if not shutil.which('pandoc'):
        sys.exit('pandoc not found on PATH — install via Home Manager or nix-shell')

    do_epub = not args.pdf_only
    do_pdf  = not args.epub_only

    if do_epub:
        # EPUB ignores raw typst blocks, so the title-page include is a
        # no-op; the EPUB picks up its title from YAML metadata instead.
        # Each H2 (chapter or appendix) gets its own spine file. Drawer-
        # parity ToC depth lets readers navigate to sub-headings.
        epub_css = ROOT / 'templates' / 'epub.css'
        epub_lua = ROOT / 'templates' / 'strip_fn_backlink.lua'
        epub_flags = [
            '--split-level=2',
            '--toc-depth=4',
            f'--css={epub_css}',
            f'--lua-filter={epub_lua}',
        ]
        if cover_path:
            epub_flags.append(f'--epub-cover-image={cover_path}')
        run_pandoc(md_path, DOWNLOADS / f'{args.slug}.epub', *epub_flags)

    if do_pdf:
        if shutil.which('typst'):
            # `--root` tells typst where the project root is, so the
            # `template:` path in the markdown (which starts with `/`)
            # resolves to <ROOT>/templates/book.typ. Two paper sizes,
            # both filename-tagged: A5 is the canonical reading edition,
            # A4 is the large-print variant (bigger type, more air).
            for md, paper, titlepage in (
                (md_path,    'a5', titlepage_a5),
                (md_path_a4, 'a4', titlepage_a4),
            ):
                run_pandoc(md, DOWNLOADS / f'{args.slug}-{paper}.pdf',
                           '--pdf-engine=typst',
                           f'--pdf-engine-opt=--root={ROOT}',
                           f'--include-before-body={titlepage}',
                           '--toc-depth=3')
        else:
            print('  ! typst not found, skipping PDF')


if __name__ == '__main__':
    main()
