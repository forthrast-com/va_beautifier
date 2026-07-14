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
import datetime
import html
import os
import re
import shutil
import subprocess
import sys
from collections import Counter, defaultdict

from core import (
    CANONICAL_FOOTNOTE_REF,
    INLINE_MARK_RE,
    INLINE_STRONG_EM_RE,
    inline_markup_to_html,
    int_to_roman,
    is_unnumbered_chapter,
    read_toml,
)
from project import BUILD, DOWNLOADS, ROOT

BUILD.mkdir(exist_ok=True)
DOWNLOADS.mkdir(parents=True, exist_ok=True)

def emit_markdown(data, slug, *, paper='a5', template_slug=None):
    # Output slug controls the .md filename; the template slug points at
    # the per-doc typst module on disk. Both default to the same value
    # unless an A4 variant is being emitted from the canonical doc.
    template_slug = template_slug or slug
    # Chapters render title-only (no "Chapter N") when the source has no chapter
    # numbering — declared per-doc in the [layout] table (see core.LAYOUT_FLAGS).
    bare_chapters = bool(data.get('layout', {}).get('bare_chapters'))
    name        = data['name']
    desc        = data.get('desc', '')
    desc_post   = data.get('desc_post', '')
    promulg     = data.get('promulgation', '')
    signature   = data.get('signature', '')
    signatories = data.get('signatories', [])
    source_url  = data.get('source_url', '')
    pdf_accent  = _pdf_accent(data.get('hue', 42))
    paragraphs  = data.get('paragraphs', [])
    footnotes   = data.get('footnotes', [])
    appendices  = data.get('appendices', [])
    chapter_style = data.get('chapter_style', '')

    fn_occurrences = Counter((f['part'], f['chapter'], f['number']) for f in footnotes)
    fn_seen = Counter()
    fn_buckets = defaultdict(list)
    for f in footnotes:
        base_key = (f['part'], f['chapter'], f['number'])
        fn_seen[base_key] += 1
        suffix = f'-{fn_seen[base_key]}' if fn_occurrences[base_key] > 1 else ''
        label = f'{f["part"]}-{f["chapter"]}-{f["number"]}{suffix}'
        fn_buckets[base_key].append((label, f))
    fn_ref_counts = Counter()
    for p in paragraphs:
        for r in CANONICAL_FOOTNOTE_REF.findall(p.get('text', '')):
            fn_ref_counts[(p.get('part', 0), p.get('chapter', 0), int(r))] += 1
    fn_ref_seen = Counter()
    used = {}  # ordered: footnote label → footnote dict

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
    # Libertinus Serif is supplied by the Nix shell on every supported host.
    # Override via VA_BOOK_FONT when another face is installed locally.
    font = os.environ.get('VA_BOOK_FONT', 'Libertinus Serif')
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
    # A4 is the printer/default edition; A5 is the reader; A6 is a compact
    # booklet with slightly smaller type to preserve a workable measure.
    fontsize = {'a4': '13pt', 'a6': '9pt'}.get(paper, '11pt')
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
    prev = {'part': None, 'part_title': None, 'part_subtitle': None,
            'chapter': None, 'section': None, 'sub': None}

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
        part_subtitle = p.get('part_subtitle', '')
        chapter       = p.get('chapter', 0)
        ch_title      = p.get('chapter_title', '')
        ch_subtitle   = p.get('chapter_subtitle', '')
        section       = p.get('section', 0)
        sec_title     = p.get('section_title', '')
        sub_heading   = p.get('sub_heading', '')
        heading_la    = p.get('heading_la', '')
        text          = p.get('text', '')
        number        = p.get('number', 0)

        # A part-0 opening with no authored title still needs a navigable
        # heading in the book — the PDF/EPUB have no JS table of contents to
        # fall back on, so unlabelled opening prose would otherwise be
        # orphaned. Generate "Preamble" (mirroring the web reader); authored
        # titles (Preface, Introduction, Preliminary Note) win.
        generated_preamble = (
            part == 0 and chapter == 0 and not part_title
            and prev['part'] is None
        )
        effective_part_title = part_title or (
            'Preamble' if generated_preamble else ''
        )
        # Fire on a part_title change too, not just a part-number change, so
        # successive part-0 prefaces both get headings (GeS "Preface" then
        # "Introductory Statement"; FeR "Blessing" then "Introduction").
        opened_part = effective_part_title and (
            part, effective_part_title, part_subtitle
        ) != (
            prev['part'], prev['part_title'], prev['part_subtitle']
        )
        if opened_part:
            if part > 0:
                level, label = '#', f'Part {int_to_roman(part)}: {effective_part_title}'
                lines += ['', '```{=typst}', '#pagebreak(weak: true)', '```', '']
            elif has_numbered_parts:
                level, label = '#', effective_part_title
            else:
                level, label = '##', effective_part_title
            lines.append('')
            lines.append(f'{level} {label}')
            lines.append('')
            if part_subtitle:
                lines.append(_markdown_body_chunk(
                    _normalise_vatican_links(part_subtitle)
                ))
                lines.append('')
            prev.update(part=part, part_title=effective_part_title,
                        part_subtitle=part_subtitle,
                        chapter=None, section=None, sub=None)

        # Chapter heading. Force a fresh page on the PDF side so chapters
        # land at the top of a recto — the EPUB writer ignores raw typst.
        if ch_title and chapter != prev['chapter']:
            unnumbered = is_unnumbered_chapter(
                ch_title, chapter_style=chapter_style,
                bare_chapters=bare_chapters,
            )
            if chapter_style == 'roman':
                label = f'{int_to_roman(chapter)}. {ch_title}'
            else:
                label = ch_title if unnumbered or chapter == 0 else f'Chapter {chapter}: {ch_title}'
            # VD's part openers carry a part epigraph plus the first section
            # heading on the same authored opener page; suppress the chapter
            # pagebreak there so the stack stays together.
            if not (template_slug == 'verbum_domini' and opened_part):
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
            candidates = fn_buckets.get(key, [])
            if candidates:
                if len(candidates) == 1:
                    label, fn = candidates[0]
                else:
                    fn_ref_seen[key] += 1
                    skipped_uncited = max(0, len(candidates) - fn_ref_counts[key])
                    position = min(skipped_uncited + fn_ref_seen[key], len(candidates))
                    label, fn = candidates[position - 1]
                used[label] = fn
                return f'[^{label}]'
            # No matching definition — leave the literal `(N)` alone so
            # the artefact reads as the Vatican source does.
            return m.group(0)

        body = _normalise_vatican_links(CANONICAL_FOOTNOTE_REF.sub(replace_ref, text))
        # Sub-paragraphs are separated by `\n\n` in the TOML; pandoc honours
        # blank-line separators. First sub-paragraph gets the bold number.
        chunks = [c.strip() for c in body.split('\n\n') if c.strip()]
        if chunks and not p.get('hide_number', False):
            chunks[0] = f'**{number}.** {chunks[0]}'
        for chunk in chunks:
            lines.append(_markdown_body_chunk(chunk))
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
            _markdown_appendix_body(
                _normalise_vatican_links(appendix['text'])
            ),
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
    for label, fn in used.items():
        # Split on \n\n so each sub-paragraph becomes a real pandoc footnote
        # paragraph. Single \n inside a sub-paragraph is treated as a soft
        # break (typst handles this naturally; pandoc wraps it).
        text = _normalise_vatican_links(fn['text'].rstrip())
        paragraphs_fn = [p.strip() for p in text.split('\n\n') if p.strip()]
        first, *rest = paragraphs_fn or ['']
        lines.append(f'[^{label}]: {first}')
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


def _markdown_body_chunk(text):
    """Emit one body chunk, suppressing PDF prose indents for hard-break text."""
    lines = text.splitlines()
    if lines and all(line == '>' or line.startswith('> ') for line in lines):
        # Already canonical Markdown blockquote syntax. Passing it through the
        # poetic-line wrapper would hide the structure from Pandoc.
        if lines[-1].startswith('> — '):
            # Preserve the semantic distinction for EPUB styling. Pandoc's
            # Typst writer treats the surrounding div as an ordinary block,
            # so print output retains its native quotation treatment.
            return f'::: {{.scripture-quote}}\n{text}\n:::'
        return text
    rendered = _markdown_preserve_breaks(text)
    if '\n' not in rendered:
        return rendered
    return (
        '`#block[#set par(first-line-indent: 0em); `{=typst}'
        f'{rendered}'
        '`]`{=typst}'
    )


def _markdown_appendix_body(text):
    """Render appendix stanzas without inheriting prose first-line indents."""
    return '\n\n'.join(
        _markdown_body_chunk(stanza.strip())
        for stanza in text.split('\n\n')
        if stanza.strip()
    )


def _normalise_vatican_links(text):
    """Make root-relative Vatican markdown links portable in EPUB/PDF."""
    return text.replace('](/content/', '](https://www.vatican.va/content/')


def _typ_str(s):
    r"""Quote a Python string for embedding in typst source. Typst strings
    are double-quoted with `\\` and `\"` escapes; everything else rides
    through unchanged."""
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'


# Everything typst treats as live markup in content mode: escapes (\),
# code (#), refs/labels (@, <>), emphasis (* _), maths ($), verse breaks
# (~), raw (`), comments (//), and content brackets ([ ]). Quotes are left
# alone — smart-quote substitution is wanted.
_TYP_CONTENT_SPECIALS = re.compile(r'[\\#\[\]*_$@~`<>/]')


def _typ_content(s):
    """Quote a Python string for typst content (inside `[...]` brackets)."""
    return _TYP_CONTENT_SPECIALS.sub(lambda m: '\\' + m.group(0), s)


def _typ_inline(s, *, preserve_breaks=False):
    """Convert canonical bold/italic content to raw typst content."""
    def literal(text):
        text = _typ_content(text)
        return text.replace('\n', ' \\\n    ') if preserve_breaks else text

    rendered = []
    pos = 0
    inline_re = re.compile(
        rf'{INLINE_STRONG_EM_RE.pattern}|{INLINE_MARK_RE.pattern}', re.DOTALL
    )
    for match in inline_re.finditer(s):
        rendered.append(literal(s[pos:match.start()]))
        if match.group(1) is not None:
            content = literal(match.group(1))
            rendered.append(f'#strong[#emph[{content}]]')
        else:
            content = literal(match.group(2) or match.group(3))
            command = 'strong' if match.group(2) is not None else 'emph'
            rendered.append(f'#{command}[{content}]')
        pos = match.end()
    rendered.append(literal(s[pos:]))
    return ''.join(rendered)


def _html_inline(s, *, preserve_breaks=False):
    """Convert canonical inline content to raw EPUB HTML content."""
    return inline_markup_to_html(s, break_tag='<br />' if preserve_breaks else '')


_PAPER_SCALE = {'a4': 1.4, 'a5': 1.0, 'a6': 0.86}


def _title_page_layout(data, paper='a5'):
    """Return the raw typst lines for the title page body — desc /
    title / ornament / desc_post stack, with the author lifted to the
    page footer by a second #v(1fr).

    Callers wrap with `#page(...)[...]` for inline include or `#set page()`
    for a standalone doc (the EPUB cover compile). Typography scales by
    paper long-edge ratio so the layout reads the same at A4 / A5 / A6."""
    name        = data['name']
    desc        = data.get('desc', '')
    desc_post   = data.get('desc_post', '')
    author      = data.get('author', '')
    accent      = _pdf_accent(data.get('hue', 42))

    scale = _PAPER_SCALE.get(paper, 1.0)
    title_pt       = round(28 * scale)
    label_pt       = round(10 * scale)
    author_pt      = round(9 * scale)
    block_gap      = f'{1.8 * scale:.2f}em'
    ornament_above = f'{0.5 * scale:.2f}em'
    ornament_pt    = round(24 * scale)
    ornament_track = '0.825em'

    out = ['#set align(center)', '#v(1fr)']

    def stacked(block, size, tracking):
        bits = [_typ_content(ln.strip()) for ln in block.splitlines() if ln.strip()]
        if not bits:
            return
        inner = ' \\\n  '.join(bits)
        out.append(f'#text(size: {size}pt, tracking: {tracking})[')
        out.append(f'  {inner}')
        out.append(']')

    if desc:
        stacked(desc.upper(), label_pt, '0.08em')
        out.append(f'#v({block_gap})')

    out.append(
        f'#text(size: {title_pt}pt, style: "italic", fill: rgb("{accent}"))'
        f'[{_typ_content(name)}]'
    )
    out.append(f'#v({ornament_above})')
    out.append(
        f'#text(size: {ornament_pt}pt, tracking: {ornament_track},'
        f' fill: rgb("{accent}"))[· · ·]'
    )

    if desc_post:
        out.append(f'#v({block_gap})')
        stacked(desc_post.upper(), label_pt, '0.08em')

    out.append('#v(1fr)')
    if author and data.get('show_title_author', True):
        # Extractor decides: encyclicals set False because the pope is
        # already named in `desc` ("ENCYCLICAL LETTER OF HIS HOLINESS
        # POPE X"); committee docs leave the default so their primary
        # signers surface at the foot in the document accent.
        is_long = len(author) > 60
        track = '0.08em' if is_long else '0.14em'
        pt = round((7 if is_long else 8.5) * scale)
        out.append('#box(width: 84%)[')
        out.append('  #set par(justify: false, leading: 0.85em)')
        out.append('  #set align(center)')
        out.append(
            f'  #text(size: {pt}pt, tracking: {track},'
            f' fill: rgb("{accent}"))[{_typ_content(author.upper())}]'
        )
        out.append(']')

    return out


def _title_page_typst(data, paper='a5'):
    """Inline title page wrapped in #page()[...] for --include-before-body."""
    lines = _title_page_layout(data, paper=paper)
    indented = '\n'.join('  ' + line for line in lines)
    return (
        '#page(numbering: none, header: none)[\n'
        + indented + '\n'
        + ']\n#pagebreak()'
    )


def _copyright_page_typst(data, paper='a5'):
    """Colophon page following the title: an editorial note, document
    metadata, and edition metadata in one consistent top-down layout."""
    name        = data['name']
    source_url  = data.get('source_url', '')
    issued_by   = data.get('issued_by', data.get('author', ''))
    pontificate = data.get('pontificate', '')
    identifier  = data.get('identifier', '')
    iso_date    = data.get('date', '')
    accent      = _pdf_accent(data.get('hue', 42))
    compact     = paper == 'a6'
    title_pt    = 12 if compact else 15
    label_pt    = 5.5 if compact else 6.5
    value_pt    = 7 if compact else 8.5
    blurb_pt    = 7.5 if compact else 9.5
    page_width  = '100%'
    label_width = '25%' if compact else '27%'
    section_gap = '1.1em' if compact else '1.5em'
    row_gap     = '0.5em' if compact else '0.7em'

    circulars_url = 'https://circulars.forthrast.com'
    repo_url      = 'https://github.com/forthrast-com/va_beautifier'

    def display(url):
        url = url.removeprefix('https://').removeprefix('http://')
        url = url.removeprefix('www.')
        if compact:
            if 'github.com/' in url:
                return 'github.com/forthrast-com'
        # The vatican.va paths run to 70+ chars; collapse the middle so
        # the URL fits a single grid row alongside the tracked label.
        # The hyperlink still points at the full URL — only the visible
        # label is truncated.
        if len(url) > 52:
            host, _, path = url.partition('/')
            last = path.rsplit('/', 1)[-1] if path else ''
            if last and len(host) + len(last) + 6 < len(url):
                url = f'{host}/…/{last}'
        return url

    promulgated_label = ''
    if iso_date:
        try:
            d = datetime.date.fromisoformat(iso_date)
            promulgated_label = f'{d.day} {d.strftime("%B")} {d.year}'
        except ValueError:
            promulgated_label = iso_date

    def label_cell(text):
        return (
            f'    text(size: {value_pt}pt, weight: "semibold", '
            f'fill: rgb("#3a342b"))[{text.title()}],'
        )

    def value_cell(content_typst):
        return (
            f'    text(size: {value_pt}pt, fill: rgb("#3a342b"))[{content_typst}],'
        )

    def text_value(text):
        return value_cell(_typ_content(text))

    def link_value(url):
        return value_cell(
            f'#link("{url}")[{_typ_content(display(url))}]'
        )

    document_cells = [label_cell('TITLE'), text_value(name)]
    if issued_by:
        document_cells += [label_cell('ISSUED BY'), text_value(issued_by)]
    if pontificate and pontificate != issued_by:
        document_cells += [label_cell('PONTIFICATE'), text_value(pontificate)]
    if promulgated_label:
        document_cells += [label_cell('PROMULGATED'), text_value(promulgated_label)]
    if source_url:
        document_cells += [label_cell('ORIGINAL'), link_value(source_url)]

    format_names = {
        'a4': 'A4 printer PDF',
        'a5': 'A5 reader PDF',
        'a6': 'A6 booklet PDF',
    }
    edition_cells = [label_cell('FORMAT'), text_value(format_names[paper])]
    if identifier:
        urn_display = f'urn:circulars:{identifier}'
        edition_cells += [label_cell('IDENTIFIER'), text_value(urn_display)]
    edition_cells += [label_cell('PROJECT'), link_value(circulars_url)]
    edition_cells += [label_cell('SOURCE CODE'), link_value(repo_url)]

    def grid_block(cells):
        return [
            '  #grid(',
            f'    columns: ({label_width}, 1fr),',
            '    column-gutter: 1.1em,',
            f'    row-gutter: {row_gap},',
            '    align: (left + top, left + top),',
            *cells,
            '  )',
        ]

    def section_heading(label):
        return [
            f'  #text(size: {label_pt}pt, weight: "semibold", '
            f'tracking: 0.22em, fill: rgb("{accent}"))[{label}]',
            '  #v(0.25em)',
            f'  #line(length: 100%, stroke: (paint: rgb("{accent}"), thickness: 0.45pt))',
            '  #v(0.45em)',
        ]

    blurb = (
        f'This edition preserves the wording of the Vatican’s HTML text of '
        f'#emph[{_typ_content(name)}] while rebuilding its structure for '
        'reading. The Circulars adds clearer navigation, keeps notes and '
        'links close at hand, and typesets the document for print.'
    )

    out = [
        '#page(numbering: none, header: none)[',
        '  #set align(left)',
        '  #v(8%)',
        f'  #box(width: {page_width})[',
        f'    #text(size: {title_pt}pt, style: "italic", fill: rgb("{accent}"))'
        '[About this edition]',
        '    #v(0.8em)',
        '    #set par(justify: false, leading: 0.82em, first-line-indent: 0pt)',
        f'    #text(size: {blurb_pt}pt, fill: rgb("#3a342b"))[{blurb}]',
        '  ]',
        f'  #place(bottom + left, float: false)[#box(width: {page_width})[',
        f'    #v({section_gap})',
        *['    ' + line for line in section_heading('DOCUMENT')],
        *['    ' + line for line in grid_block(document_cells)],
        f'    #v({section_gap})',
        *['    ' + line for line in section_heading('EDITION')],
        *['    ' + line for line in grid_block(edition_cells)],
        '  ]]',
        ']',
        '#pagebreak()',
    ]
    return '\n'.join(out)


def _write_titlepage_include(data, slug, *, paper='a5'):
    """Write the include-before-body file: title page followed by a
    copyright/colophon page. Pandoc inserts file contents verbatim into
    the output (after pandoc's own setup, before the TOC) so this must
    be valid typst, not markdown. Separate file per paper size."""
    title = _title_page_typst(data, paper=paper)
    colophon = _copyright_page_typst(data, paper=paper)
    path = BUILD / f'{slug}_titlepage_{paper}.typ'
    path.write_text(f'{title}\n{colophon}\n', encoding='utf-8')
    return path


def _write_pdf_template(data, slug):
    """Materialise the shared Typst template with this document's accent."""
    accent = _pdf_accent(data.get('hue', 42))
    source = (ROOT / 'templates' / 'book.typ').read_text(encoding='utf-8')
    path = BUILD / _pdf_template_name(slug)
    path.write_text(source.replace('__PDF_ACCENT__', accent), encoding='utf-8')
    return path


def _cover_typst(data):
    """Standalone typst doc for the EPUB cover: an A6 version of the PDF
    title page, with the same layout scaled by linear ratio. Compiled at
    300 ppi yields ~1240 × 1748 px — well above Apple Books' minimum."""
    lines = _title_page_layout(data, paper='a6')
    body = '\n'.join(lines)
    font = os.environ.get('VA_BOOK_FONT', 'Libertinus Serif')
    return (
        '#set page(paper: "a6", margin: 12mm)\n'
        f'#set text(font: "{font}", size: 11pt)\n'
        + body + '\n'
    )


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
    """End matter slotted at the bottom of the last body page via
    typst's `#place(bottom + center, float: true)` — if there is room
    under the body's final paragraph the dedication lands there; if
    not, typst floats it to the next page's foot. No forced page break
    and no page wrapper, so the running head stays consistent with the
    body's last chapter."""
    parts = [
        '#place(bottom + center, float: true, scope: "parent",'
        ' clearance: 2em)[',
        '  #set align(center)',
    ]
    stanzas = list(_promulgation_stanzas(promulg)) if promulg else []
    if stanzas:
        parts += [
            f'  #line(length: 35%, stroke: (paint: rgb("{accent}"), thickness: 0.5pt))',
            '  #v(1.2em)',
        ]
    for index, stanza in enumerate(stanzas):
        if index:
            parts.append('  #v(0.9em)')
        parts.append(f'  #text(size: 11pt)[{_typ_inline(stanza)}]')
    if stanzas:
        parts.append('  #v(1.6em)')
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
        parts += ['  )', '  #v(1.6em)']
    if signature:
        parts.append(
            f'  #text(tracking: 0.14em)[{_typ_inline(signature, preserve_breaks=True)}]'
        )
    parts += [']']
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
    pdf_toc_depth = data.get('book_toc_depth', 3)

    print(f'[{args.slug}] markdown')
    _write_pdf_template(data, args.slug)
    md_path = emit_markdown(data, args.slug)
    md_path_a6 = emit_markdown(
        data, args.slug + '_a6', paper='a6', template_slug=args.slug
    )
    md_path_a4 = emit_markdown(
        data, args.slug + '_a4', paper='a4', template_slug=args.slug
    )
    titlepage_a5 = _write_titlepage_include(data, args.slug, paper='a5')
    titlepage_a6 = _write_titlepage_include(data, args.slug, paper='a6')
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
            # resolves to <ROOT>/templates/book.typ. All paper sizes are
            # filename-tagged: A4 printer/default, A5 reader, A6 booklet.
            for md, paper, titlepage in (
                (md_path_a4, 'a4', titlepage_a4),
                (md_path,    'a5', titlepage_a5),
                (md_path_a6, 'a6', titlepage_a6),
            ):
                run_pandoc(md, DOWNLOADS / f'{args.slug}-{paper}.pdf',
                           '--pdf-engine=typst',
                           f'--pdf-engine-opt=--root={ROOT}',
                           f'--include-before-body={titlepage}',
                           f'--toc-depth={pdf_toc_depth}')
        else:
            print('  ! typst not found, skipping PDF')


if __name__ == '__main__':
    main()
