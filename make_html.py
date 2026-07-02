import argparse
import json
import re
from collections import Counter, defaultdict
from html import escape

from core import (
    CANONICAL_FOOTNOTE_REF,
    LAYOUT_FLAGS,
    ch_order_label,
    inline_markup_to_html,
    int_to_roman,
    read_toml,
    title_case,
)
from project import ASSETS, BUILD, SITE

CSS         = (ASSETS / 'styles.css').read_text()
JS_TEMPLATE = (ASSETS / 'scripts.js').read_text()

# External hyperlinks come through clean_text as `[text](href)` markdown.
# `[^)\s]+` for the href so a stray `)` in surrounding prose can't extend
# the match — vatican.va URLs are paren-free.
INLINE_LINK_RE = re.compile(r'\[([^\]]+)\]\(([^)\s]+)\)')
# A markdown link target with an explicit scheme other than http(s) —
# javascript:, data:, … — is never linkified; scheme-less (relative or
# fragment) targets pass.
HREF_SCHEME_RE = re.compile(r'^([a-zA-Z][a-zA-Z0-9+.\-]*):')

# Retain cleanup for legacy TOML files emitted before inline source markup
# became canonical. Use [ \t] (not \s) so poetic line breaks survive.
TIGHTEN = [
    (re.compile(r'(\w)[ \t]+([.,;:!?])'),        r'\1\2'),    # "Ibid ." → "Ibid."
    (re.compile(r'(\d)[ \t]+(st|nd|rd|th)\b'),  r'\1\2'),    # "35 th"  → "35th"
]
def tighten(text):
    for pat, sub in TIGHTEN:
        text = pat.sub(sub, text)
    return text

ap = argparse.ArgumentParser(description='Render a TOML intermediate to a single-file HTML edition.')
ap.add_argument('doc', help='Doc slug (looks for {slug}.toml, writes {slug}.html)')
args = ap.parse_args()

data = read_toml(BUILD / f'{args.doc}.toml')

paragraphs   = data['paragraphs']
footnotes    = data.get('footnotes', [])
appendices   = data.get('appendices', [])
doc_name     = data.get('name', args.doc)
doc_source   = data.get('source_url', '')
doc_desc      = data.get('desc', '')
doc_desc_post = data.get('desc_post', '')
doc_promulg   = data.get('promulgation', '')
doc_signature = data.get('signature', '')
doc_signatories = data.get('signatories', [])
chapter_style = data.get('chapter_style', '')

# Per-document rendering flags, declared in the extractor and serialised to the
# [layout] TOML table (see core.LAYOUT_FLAGS). These replace the slug
# membership sets (LONG_DOCS / BARE_SECTION_DOCS / BARE_CHAPTER_DOCS) that used
# to live here — adding a doc no longer means editing this file.
layout        = data.get('layout', {})
IS_LONG       = bool(layout.get('long'))         # gutter layout + section-level sticky bar
BARE_SECTIONS = bool(layout.get('bare_sections'))  # named sections, no "Section N:" prefix
BARE_CHAPTERS = bool(layout.get('bare_chapters'))  # title-only chapters, no "Chapter N:" prefix
# Every truthy flag also becomes a `layout-<flag>` body class (underscores →
# hyphens) so styles.css targets the class once instead of enumerating slugs.
layout_classes = ''.join(
    f' layout-{flag.replace("_", "-")}'
    for flag in LAYOUT_FLAGS if layout.get(flag)
)

# Default = warm gold for legacy TOML files without explicit document colour.
doc_hue = data.get('hue', 42)

# ── helpers ──────────────────────────────────────────────────────────────────

def e(s): return escape(s)

def chapter_num_label(chapter):
    return f'{int_to_roman(chapter)}.' if chapter_style == 'roman' else f'Chapter {chapter}'

def chapter_full_label(chapter, title):
    number = chapter_num_label(chapter)
    separator = ' ' if chapter_style == 'roman' else ': '
    return f'{number}{separator}{title}' if title else number

def chapter_group_label(part, chapter, title):
    """Drawer/TOC label for a chapter group, matching the body rendering:
    bare-chapter docs and trailing conclusions show the bare title
    (the body's is_unnumbered suppression), everything else keeps the
    "Chapter N: " prefix."""
    if part == 0 and chapter == 0:
        return title or 'Preamble'
    is_unnumbered = title and chapter_style != 'roman' and (
        BARE_CHAPTERS or title.strip().lower() == 'conclusion'
    )
    if is_unnumbered:
        return title
    if part == 0:
        return chapter_full_label(chapter, title)
    return title or f'Part {int_to_roman(part)}, Chapter {chapter}'

def footnote_key(part, chapter, number, occurrence=0):
    base = f'{part}-{chapter}-{number}'
    return base if not occurrence else f'{base}-{occurrence}'

def linkify_footnotes(text, part, chapter, footnote_ref_ids=None):
    """Replace (N) inline refs with linked superscripts."""
    ref_ids = iter(footnote_ref_ids or [])

    def replace(m):
        n = m.group(1)
        target = next(ref_ids, f'fn-{part}-{chapter}-{n}')
        return f'<sup><a href="#{target}">{n}</a></sup>'
    return CANONICAL_FOOTNOTE_REF.sub(replace, text)

def linkify_anchors(text):
    """Convert `[text](href)` markdown back to anchor tags.

    Run BEFORE linkify_footnotes so the URL's parens get consumed before the
    footnote regex sees them and mistakes (e.g.) `(2021)` for a fn ref."""
    def replace(m):
        body, href = m.group(1), m.group(2)
        scheme = HREF_SCHEME_RE.match(href)
        if scheme and scheme.group(1).lower() not in ('http', 'https'):
            return body
        if href.startswith('/content/'):
            href = 'https://www.vatican.va' + href
        return f'<a href="{href}" class="ext-link" target="_blank" rel="noopener">{body}</a>'
    return INLINE_LINK_RE.sub(replace, text)

def format_inline(text):
    """Render the restricted Markdown-compatible markup emitted by `core`.

    Input arrives already escaped (para_html escapes each line before
    linkifying), hence `escaped=True`."""
    return inline_markup_to_html(text, escaped=True)

def structure_inline_html(text):
    """Render canonical inline markup for headings with authored line breaks."""
    return inline_markup_to_html(e(text), escaped=True, break_tag='<br>')

def para_html(text, part=None, chapter=None, footnote_ref_ids=None):
    """Convert paragraph text to <p> tags.

    `\\n\\n` separates sub-paragraphs (each becomes its own <p>).
    `\\n` within a sub-paragraph is a poetic line break and becomes <br>
    (the LS canticle + closing prayers use this).
    """
    text = tighten(text)
    out = []
    footnote_ref_ids = iter(footnote_ref_ids or [])
    for sub in [p.strip() for p in text.split('\n\n') if p.strip()]:
        rendered = e(sub)
        rendered = linkify_anchors(rendered)
        if part is not None:
            rendered = linkify_footnotes(
                rendered, part, chapter, footnote_ref_ids,
            )
        rendered = inline_markup_to_html(
            rendered, escaped=True, break_tag='<br>',
        )
        out.append('<p>' + rendered + '</p>')
    return '\n'.join(out)

def end_matter_inline_html(text):
    """Render canonical inline markup while preserving authored line breaks."""
    return inline_markup_to_html(text, break_tag='<br>')

# ── build sections ────────────────────────────────────────────────────────────

def _desc_line(ln):
    """Render a single front-matter line: title-case the all-caps source,
    preserving Roman numerals (POPE LEO XIV, POPE PAUL VI) via the
    title_case helper. `small_words=True` because each visual line is a
    fragment of a longer subtitle phrase — a line that *starts* with
    "of the Holy Father" should keep the leading "of" lowercase.
    Wrap in inline-block so the centred line still reflows as one unit
    at narrow widths."""
    return f'<span style="display:inline-block">{e(title_case(ln, small_words=True))}</span>'


def _desc_block(text, cls, *, break_before_on=False, stacked=False):
    """Render `text` (one source line per output span) as a centred desc
    paragraph. With `break_before_on`, insert a hard line break before any
    line starting with "ON " — the modern encyclicals' subtitles open
    with "ON CARE FOR…" / "ON SAFEGUARDING…", and the user wants those
    visually separated from the preceding "OF THE HOLY FATHER / NAME"
    stanza regardless of viewport width. With `stacked=True`, every
    source line gets its own row — for documents whose front matter lists
    distinct institutions (Antiqua et nova names two dicasteries) rather
    than a fragmented title phrase."""
    pieces = []
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        if (stacked or break_before_on and ln.upper().startswith('ON ')) and pieces:
            pieces.append('<br>')
        pieces.append(_desc_line(ln))
    if not pieces:
        return ''
    out = ''
    for piece in pieces:
        if piece == '<br>':
            out += '<br>'
        elif out and not out.endswith('<br>'):
            out += ' ' + piece
        else:
            out += piece
    return f'<p class="{cls}">{out}</p>'

# The Vatican sources place the document title *between* lines of the
# front-matter block: e.g. MH has "ENCYCLICAL LETTER" above the title and
# "OF HIS HOLINESS … IN THE TIME OF AI" below; GeS has "PASTORAL
# CONSTITUTION …" above the title and "PROMULGATED BY … DECEMBER 7, 1965"
# below. Each extractor pre-splits these into desc (above) + desc_post
# (below); the renderer just stacks them around the name.
title_block = ''
if doc_desc or doc_name or doc_desc_post:
    is_modern = IS_LONG
    # Documents whose pre-title `desc` lists distinct issuing bodies
    # (Antiqua et nova — two co-signing dicasteries) want each line on
    # its own row instead of flowed as a single title phrase.
    stack_desc_pre = args.doc in {'antiqua_et_nova'}
    title_block = (
        '<div class="doc-title">'
        + _desc_block(doc_desc, 'doc-desc doc-desc-pre',
                      stacked=stack_desc_pre)
        + f'<p class="doc-name">{e(doc_name)}</p>'
        + _desc_block(doc_desc_post, 'doc-desc doc-desc-post',
                      break_before_on=is_modern)
        + '</div>'
    )

# Dedication, signatories and signature belong at the END in the sources
# (after the body, just before the footnote block), not in the front matter
# where the dedication used to live. Multi-stanza promulgations (A&N
# carries one stanza for the papal audience and another for the offices
# of issuance) are split on `\n\n` so each renders on its own line.
end_matter_html = ''
if doc_promulg or doc_signatories or doc_signature:
    parts = ['<div class="doc-end-matter">']
    if doc_promulg:
        parts.append('<hr class="document-break">')
        stanzas = [s.strip() for s in doc_promulg.split('\n\n') if s.strip()]
        for stanza in stanzas:
            parts.append(
                f'<p class="doc-promulg">{end_matter_inline_html(stanza)}</p>'
            )
    if doc_signatories:
        parts.append('<div class="doc-signatories">')
        for signatory in doc_signatories:
            parts.append(
                '<div class="doc-signatory">'
                f'<span class="doc-signatory-name">{e(signatory.get("name", ""))}</span>'
                f'<span class="doc-signatory-role">{e(signatory.get("role", ""))}</span>'
                '</div>'
            )
        parts.append('</div>')
    if doc_signature:
        parts.append(
            f'<p class="doc-signature">{end_matter_inline_html(doc_signature)}</p>'
        )
    parts.append('</div>')
    end_matter_html = ''.join(parts)

html_parts = []

def h(tag, cls, text):
    return f'<{tag} class="{cls}">{e(text)}</{tag}>'

def rich_h(tag, cls, text):
    return f'<{tag} class="{cls}">{structure_inline_html(text)}</{tag}>'

seen_part        = object()
seen_chapter     = object()
seen_section     = object()
seen_sub_heading = object()

sections_for_drawer = []  # list of {id, label, chapter_label}
subs_for_drawer    = []   # list of {id, label, part, chapter, section, first_para}
para_to_sub_id     = {}   # para id → sub id ('' if no sub-heading)
_cur_sub_id        = ''   # tracks the currently active sub-heading as we walk
_cur_sub_text      = ''   # the running sub-heading text (LS); GeS computes per-para

# chapters collected for the scroll indicator: list of {id, label}
indicator_chapters = []
_ch_counter = 0

def next_cid():
    global _ch_counter
    cid = f'ch-{_ch_counter}'
    _ch_counter += 1
    return cid

# para id → indicator chapter id (for ch_paras)
para_ch_id: dict[str, str] = {}

para_id_by_index: dict[int, str] = {}
para_number_counts = Counter(p['number'] for p in paragraphs)
para_number_seen = Counter()
visible_para_seen = Counter()
for idx, p in enumerate(paragraphs):
    number = p['number']
    para_number_seen[number] += 1
    if para_number_counts[number] == 1:
        para_id = f'para-{number}'
    elif not p.get('hide_number', False) and visible_para_seen[number] == 0:
        para_id = f'para-{number}'
        visible_para_seen[number] += 1
    else:
        para_id = f'para-{number}-{para_number_seen[number]}'
    para_id_by_index[idx] = para_id

fn_occurrences = Counter((fn['part'], fn['chapter'], fn['number']) for fn in footnotes)
fn_seen = Counter()
fn_render_key_by_object: dict[int, tuple[int, int, int, int]] = {}
fn_keys_by_context_number: dict[tuple[int, int, int], list[tuple[int, int, int, int]]] = defaultdict(list)
for fn in footnotes:
    context_key = (fn['part'], fn['chapter'], fn['number'])
    fn_seen[context_key] += 1
    occurrence = fn_seen[context_key] if fn_occurrences[context_key] > 1 else 0
    key = (fn['part'], fn['chapter'], fn['number'], occurrence)
    fn_render_key_by_object[id(fn)] = key
    fn_keys_by_context_number[context_key].append(key)

footnote_ref_ids_by_index: dict[int, list[str]] = defaultdict(list)
fn_para: dict[tuple[int, int, int, int], str] = {}
fn_ref_counts = Counter()
for p in paragraphs:
    for r in CANONICAL_FOOTNOTE_REF.findall(p['text']):
        fn_ref_counts[(p['part'], p['chapter'], int(r))] += 1
fn_ref_seen = Counter()
for idx, p in enumerate(paragraphs):
    refs = CANONICAL_FOOTNOTE_REF.findall(p['text'])
    for r in refs:
        context_key = (p['part'], p['chapter'], int(r))
        candidates = fn_keys_by_context_number.get(context_key, [])
        if candidates:
            if len(candidates) == 1:
                key = candidates[0]
            else:
                fn_ref_seen[context_key] += 1
                skipped_uncited = max(0, len(candidates) - fn_ref_counts[context_key])
                position = min(skipped_uncited + fn_ref_seen[context_key], len(candidates))
                key = candidates[position - 1]
        else:
            key = (p['part'], p['chapter'], int(r), 0)
        footnote_ref_ids_by_index[idx].append('fn-' + footnote_key(*key))
        fn_para.setdefault(key, para_id_by_index[idx])

part_nav: dict[int, tuple[str, str]] = {}  # part → (cid, title) for drawer/no-JS TOC rows
for idx, p in enumerate(paragraphs):
    part    = (p['part'], p['part_title'], p.get('part_subtitle', ''))
    chapter = (p['chapter'], p['chapter_title'], p.get('chapter_subtitle', ''))
    section = (p['section'], p['section_title'])

    # An empty part_title following a labelled intro within the same part
    # number isn't a new part — it's the body of a part-less document
    # continuing past its named introduction. Only count it as a change
    # when the part number flips or a fresh non-empty title appears.
    if isinstance(seen_part, tuple):
        same_part = (
            seen_part[0] == p['part']
            and (not p['part_title'] or seen_part[1] == p['part_title'])
        )
    else:
        same_part = False
    if not same_part:
        cid = next_cid()
        if p['part'] == 0:
            # Preface/introduction group. An authored part_title (GeS
            # "Preface", SC "Introduction", QVH "Preliminary Note") renders as
            # a visible body heading. Opening prose at chapter 0 with no
            # authored title gets a *generated* "Preamble" label that is
            # suppressed in the body but kept for navigation: it labels the
            # contents drawer, the scroll indicator, and the no-JS TOC, and
            # shows visibly in the PDF/EPUB (which have no live TOC to lean
            # on). A part-0 group that runs straight into a chapter — AeN's
            # roman "I. Introduction" — stays anchor-only under "Introduction".
            authored_title = p['part_title']
            is_preamble = not authored_title and p['chapter'] == 0
            label = authored_title or ('Preamble' if is_preamble else 'Introduction')
            indicator_chapters.append({'id': cid, 'label': label, 'spacer': False, 'part': 0})
            if authored_title:
                html_parts.append(h('h1', 'part-title', authored_title).replace('<h1 ', f'<h1 id="{cid}" data-sticky '))
                if p.get('part_subtitle', ''):
                    html_parts.append(rich_h('p', 'part-subtitle', p['part_subtitle']))
            else:
                # generated preamble or chapter-led part 0: anchor-only in the
                # body — the label lives in the nav/TOC, not an on-page heading
                html_parts.append(f'<a id="{cid}"></a>')
        else:
            indicator_chapters.append({'id': cid, 'label': f'Part {int_to_roman(p["part"])}', 'spacer': True, 'part': p['part']})
            part_nav[p['part']] = (cid, p['part_title'])
            html_parts.append(h('h1', 'part-num', f'Part {int_to_roman(p["part"])}').replace('<h1 ', f'<h1 id="{cid}" '))
            if p['part_title']:
                html_parts.append(h('h2', 'part-title', p['part_title']).replace('<h2 ', '<h2 data-sticky '))
            if p.get('part_subtitle', ''):
                html_parts.append(rich_h('p', 'part-subtitle', p['part_subtitle']))
        seen_part        = part
        seen_chapter     = object()
        seen_section     = object()
        seen_sub_heading = object()

    if chapter != seen_chapter and p['chapter'] != 0:
        cid = next_cid()
        label = chapter_full_label(p['chapter'], p['chapter_title']) if chapter_style == 'roman' else p['chapter_title'] or (
            f'Part {int_to_roman(p["part"])}, Ch. {p["chapter"]}' if p['part']
            else f'Chapter {p["chapter"]}'
        )
        indicator_chapters.append({'id': cid, 'label': label, 'spacer': False, 'part': p['part']})
        # The conclusion is structurally a chapter but the source labels it
        # only 'CONCLUSION', not 'CHAPTER SIX' — suppress the "Chapter N"
        # prefix so the rendered heading matches the source. The id then
        # rides on the title <h3> instead of the (omitted) chapter-num <h2>.
        is_unnumbered = chapter_style != 'roman' and (
            p['chapter_title'].strip().lower() == 'conclusion'
            or BARE_CHAPTERS
        )
        if chapter_style == 'roman':
            # Roman-numeral docs (AeN): chapter number lives in the
            # left gutter as a Roman numeral (data-ch-num + CSS
            # ::before), so the heading text is just the title.
            # The sticky bar reads both attrs and renders 'II  Title'
            # without the inline prefix doubling the numeral up.
            ch_num = int_to_roman(p['chapter'])
            html_parts.append(
                h('h3', 'chapter-title', p['chapter_title'])
                .replace('<h3 ', f'<h3 id="{cid}" data-sticky data-ch-num="{ch_num}" ')
            )
            if p.get('chapter_subtitle', ''):
                html_parts.append(rich_h('p', 'chapter-subtitle',
                                         p['chapter_subtitle']))
        else:
            if not is_unnumbered:
                html_parts.append(h('h2', 'chapter-num', chapter_num_label(p['chapter'])).replace('<h2 ', f'<h2 id="{cid}" '))
            if p['chapter_title']:
                ch_num = f'{int_to_roman(p["part"])}.{p["chapter"]}' if p['part'] else f'{p["chapter"]}'
                id_attr = f'id="{cid}" ' if is_unnumbered else ''
                html_parts.append(
                    h('h3', 'chapter-title', p['chapter_title'])
                    .replace('<h3 ', f'<h3 {id_attr}data-sticky data-ch-num="{ch_num}" ')
                )
                if p.get('chapter_subtitle', ''):
                    html_parts.append(rich_h('p', 'chapter-subtitle',
                                             p['chapter_subtitle']))
        seen_chapter     = chapter
        seen_section     = object()
        seen_sub_heading = object()

    para_id = para_id_by_index[idx]
    para_ch_id[para_id] = indicator_chapters[-1]['id']

    if section != seen_section and p['section'] != 0:
        sec_id = f'sec-{p["part"]}-{p["chapter"]}-{p["section"]}'
        if BARE_SECTIONS:
            label = p['section_title']
        else:
            label = f'Section {p["section"]}'
            if p['section_title']:
                label += f': {p["section_title"]}'
        ch_label = p['chapter_title'] or f'Part {int_to_roman(p["part"])}, Ch. {p["chapter"]}'
        sections_for_drawer.append({'id': sec_id, 'label': label, 'ch_label': ch_label,
                                     'part': p['part'], 'chapter': p['chapter'],
                                     'section': p['section']})
        html_parts.append(h('h4', 'section-title', label).replace('<h4 ', f'<h4 id="{sec_id}" '))
        seen_section     = section
        seen_sub_heading = object()

    sub = p.get('sub_heading', '')
    if sub != seen_sub_heading:
        if sub:
            _cur_sub_id = f'sub-{para_id.removeprefix("para-")}'
            _cur_sub_text = sub
            subs_for_drawer.append({
                'id': _cur_sub_id, 'label': sub,
                'part': p['part'], 'chapter': p['chapter'], 'section': p['section'],
                'first_para': p['number'],
            })
            html_parts.append(
                h('h5', 'sub-heading', sub).replace('<h5 ', f'<h5 id="{_cur_sub_id}" ')
            )
        else:
            _cur_sub_id = ''
            _cur_sub_text = ''
        seen_sub_heading = sub
    para_to_sub_id[para_id] = _cur_sub_id

    # paragraph block
    num  = p['number']
    head = p.get('heading_la', '')
    body = para_html(
        p['text'], p['part'], p['chapter'],
        footnote_ref_ids_by_index.get(idx, []),
    )

    # Per-doc sticky-bar sub-line. GeS prefers the larger structural unit
    # (section title) and falls back to the paragraph's Latin micro-summary
    # when not in a section. LS and MH both track sections — sub-headings
    # are too granular for the sub-bar (they change every 2-5 paras), and
    # section context is the orientation level a reader actually wants
    # while scrolling. Sub-heading nav is still available in the TOC
    # drawer. Kept as separate branches so per-doc tweaks don't have to
    # disentangle a shared one.
    if args.doc == 'gaudium_et_spes':
        sub_text = (p['section_title'] if p['section'] else '') or head
    elif IS_LONG:
        sub_text = p['section_title'] if p['section'] else ''
    else:
        sub_text = _cur_sub_text

    visible_num = '' if p.get('hide_number', False) else f'<span class="para-num">{num}</span>'
    html_parts.append(
        f'<div class="paragraph" id="{para_id}" data-para-num="{num}" data-sub-text="{e(sub_text)}">'
        f'{visible_num}'
        + (f' <em class="heading-la">{e(head)}</em>' if head else '')
        + f'\n{body}'
        f'</div>'
    )
    if p.get('break_after', False):
        html_parts.append('<hr class="document-break">')

# (part, chapter) → first cid containing those paragraphs (for footnote links)
part_chapter_to_cid: dict[tuple, str] = {}
for idx, p in enumerate(paragraphs):
    key = (p['part'], p['chapter'])
    if key not in part_chapter_to_cid:
        part_chapter_to_cid[key] = para_ch_id[para_id_by_index[idx]]

# ── drawer: sections + sub-headings + footnotes interleaved by chapter ──────

secs_by_ch = defaultdict(list)
for s in sections_for_drawer:
    secs_by_ch[(s['part'], s['chapter'])].append(s)

subs_by_chsec: dict[tuple, list] = defaultdict(list)
for sb in subs_for_drawer:
    subs_by_chsec[(sb['part'], sb['chapter'], sb['section'])].append(sb)

fns_by_ch = defaultdict(list)
for fn in footnotes:
    fns_by_ch[(fn['part'], fn['chapter'])].append(fn)

# Footnote heading placement is canonical TOML data. Only the link back to
# the first citing paragraph is renderer-owned, because paragraph anchors are
# an HTML navigation detail rather than source structure.
fn_section: dict[tuple[int, int, int, int], int] = {}
fn_sub:     dict[tuple[int, int, int, int], str] = {}
sub_id_by_context: dict[tuple, str] = {}
for sb in subs_for_drawer:
    key = (sb['part'], sb['chapter'], sb['section'], sb['label'])
    sub_id_by_context.setdefault(key, sb['id'])
for fn in footnotes:
    key = fn_render_key_by_object[id(fn)]
    section = fn.get('section', 0)
    fn_section[key] = section
    sub_heading = fn.get('sub_heading', '')
    if sub_heading:
        fn_sub[key] = sub_id_by_context.get(
            (fn['part'], fn['chapter'], section, sub_heading), ''
        )
for idx, p in enumerate(paragraphs):
    refs = CANONICAL_FOOTNOTE_REF.findall(p['text'])
    for r in refs:
        context_key = (p['part'], p['chapter'], int(r))
        candidates = fn_keys_by_context_number.get(context_key, [])
        key = candidates[0] if len(candidates) == 1 else None
        if key is None:
            continue
        # Keep older TOML intermediates renderable until they are rebuilt.
        fn_section.setdefault(key, p['section'])
        fn_sub.setdefault(key, para_to_sub_id.get(para_id_by_index[idx], ''))

# chapter order from document
ch_order = []
seen_ch_order = set()
for p in paragraphs:
    key = (p['part'], p['chapter'])
    if key not in seen_ch_order:
        ch_order.append((key, ch_order_label(p)))
        seen_ch_order.add(key)

def fn_item_html(part, chapter, fn):
    key  = fn_render_key_by_object[id(fn)]
    para_id = fn_para.get(key)
    href = f'#{para_id}' if para_id else ''
    if href:
        num = f'<a href="{href}" class="fn-num-link">{fn["number"]}</a>'
    else:
        num = f'<span class="fn-num-link">{fn["number"]}</span>'
    body = para_html(fn['text'])
    fn_id = 'fn-' + footnote_key(*key)
    return f'<li id="{fn_id}" class="fn-item">{num}{body}</li>'

# Per-doc drawer style. 'chapter' = chapter group headings + flat footnote
# list (no section/sub nav lines). 'full' = chapter + section + sub-heading
# navigation interleaved with footnotes (the default; LS now uses this too
# since the vertical-bar hierarchy makes the three levels scannable).
DOC_DRAWER_STYLE = {}
drawer_style = DOC_DRAWER_STYLE.get(args.doc, 'full')

def toc_item(tag, cls, link_cls, target, label):
    return (
        f'<{tag} class="{cls} toc-item" data-target="{target}" data-label="{e(label)}">'
        f'<a href="#{target}" class="{link_cls}">{e(label)}</a>'
        f'<button class="bookmark-toggle" type="button" data-bookmark-target="{target}" '
        f'aria-label="Bookmark {e(label)}" aria-pressed="false"></button>'
        f'</{tag}>'
    )

def part_nav_label(part):
    cid, title = part_nav[part]
    label = f'Part {int_to_roman(part)}'
    return cid, (f'{label}: {title}' if title else label)

drawer_items = []
toc_items = []
toc_part_seen = 0
for (part, chapter), ch_label in ch_order:
    # Parted documents (VD, DCE, GeS) get a part row in the contents tree,
    # mirroring the body's Part I/II headings; chapters group beneath it.
    if part and part != toc_part_seen and part in part_nav:
        p_cid, p_label = part_nav_label(part)
        toc_items.append(toc_item('h3', 'fn-group part-group', 'fn-ch-link', p_cid, p_label))
    toc_part_seen = part
    secs    = secs_by_ch.get((part, chapter), [])
    fns     = fns_by_ch.get((part, chapter), [])
    ch_subs = [sb for sb in subs_for_drawer
               if sb['part'] == part and sb['chapter'] == chapter]
    cid = part_chapter_to_cid.get((part, chapter), '')
    group_label = chapter_group_label(part, chapter, ch_label)

    # Part-0/chapter-0 regions without an authored title now get a generated
    # Preamble heading, so their sections can stay nested under that root.
    unrooted = False
    item_cls = 'sec-nav-item unrooted' if unrooted else 'sec-nav-item'

    if not unrooted:
        toc_items.append(toc_item('h3', 'fn-group', 'fn-ch-link', cid, group_label))

    for sb in subs_by_chsec.get((part, chapter, 0), []):
        toc_items.append(toc_item('p', 'sub-nav-item', 'sub-nav-link', sb['id'], sb['label']))
    for s in sorted(secs, key=lambda x: x['section']):
        toc_items.append(toc_item('p', item_cls, 'sec-nav-link', s['id'], s['label']))
        for sb in subs_by_chsec.get((part, chapter, s['section']), []):
            toc_items.append(toc_item('p', 'sub-nav-item', 'sub-nav-link', sb['id'], sb['label']))

    if not secs and not fns and not ch_subs:
        continue
    if not unrooted:
        drawer_items.append(f'<h3 class="fn-group"><a href="#{cid}" class="fn-ch-link">{e(group_label)}</a></h3>')

    if drawer_style == 'chapter':
        # Flat list of footnotes for this chapter, in number order.
        if fns:
            drawer_items.append('<ol class="fn-list">')
            for fn in sorted(fns, key=lambda x: x['number']):
                drawer_items.append(fn_item_html(part, chapter, fn))
            drawer_items.append('</ol>')
        continue

    # Group footnotes by section. Section 0 holds anything before the
    # first numbered section (or all of a chapter that has no sections).
    fns_by_sec: dict[int, list] = defaultdict(list)
    for fn in fns:
        sec = fn_section.get(fn_render_key_by_object[id(fn)], 0)
        fns_by_sec[sec].append(fn)

    sec_nums = [0] + [s['section'] for s in sorted(secs, key=lambda s: s['section'])]
    sec_meta = {0: None}
    for s in secs:
        sec_meta[s['section']] = s

    for sec_num in sec_nums:
        s        = sec_meta.get(sec_num)
        sec_subs = subs_by_chsec.get((part, chapter, sec_num), [])
        sec_fns  = fns_by_sec.get(sec_num, [])
        if not s and not sec_subs and not sec_fns:
            continue

        if s:
            sec_cls = 'sec-nav-item unrooted' if unrooted else 'sec-nav-item'
            drawer_items.append(f'<p class="{sec_cls}"><a class="sec-nav-link" href="#{s["id"]}">{e(s["label"])}</a></p>')

        # Bucket the section's footnotes by which sub-heading (if any)
        # the citing paragraph fell under.
        fns_by_sub: dict[str, list] = defaultdict(list)
        for fn in sec_fns:
            sid = fn_sub.get(fn_render_key_by_object[id(fn)], '')
            fns_by_sub[sid].append(fn)

        # Footnotes not under any sub-heading come first (preserves
        # current behaviour for sections without sub-headings).
        if fns_by_sub.get(''):
            drawer_items.append('<ol class="fn-list">')
            for fn in fns_by_sub['']:
                drawer_items.append(fn_item_html(part, chapter, fn))
            drawer_items.append('</ol>')

        # Then each sub-heading as a nav link, followed by its footnotes.
        for sb in sec_subs:
            drawer_items.append(f'<p class="sub-nav-item"><a class="sub-nav-link" href="#{sb["id"]}">{e(sb["label"])}</a></p>')
            sub_fns = fns_by_sub.get(sb['id'], [])
            if sub_fns:
                drawer_items.append('<ol class="fn-list">')
                for fn in sub_fns:
                    drawer_items.append(fn_item_html(part, chapter, fn))
                drawer_items.append('</ol>')

for idx, app in enumerate(appendices):
    toc_items.append(
        toc_item('h3', 'fn-group', 'fn-ch-link',
                 f'appendix-{idx + 1}', app['title'])
    )

# ── appendices (e.g. LS's two closing prayers) ───────────────────────────────

appendix_html = ''
if appendices:
    parts = ['<section class="appendix-block">']
    for idx, app in enumerate(appendices):
        aid = f'appendix-{idx + 1}'
        kind_cls = (
            f' appendix-{e(app["kind"])}'
            if app.get('kind') else ''
        )
        stanzas = para_html(app['text'])    # honours \n\n and \n the same way as body paragraphs
        parts.append(
            f'<div class="appendix{kind_cls}" id="{aid}">'
            f'<h1 class="appendix-title" data-sticky>{e(app["title"])}</h1>'
            f'{stanzas}'
            f'</div>'
        )
    parts.append('</section>')
    appendix_html = '\n'.join(parts)

# ── page ──────────────────────────────────────────────────────────────────────


fn_drawer_html = '\n'.join(drawer_items)
toc_drawer_html = '\n'.join(toc_items)

# ── no-JS fallback TOC (simple link list, no bookmark widgets) ───────────────
noscript_toc_parts = ['<ul class="noscript-toc-list">']
ntoc_part_seen = 0
for (part, chapter), ch_label in ch_order:
    if part and part != ntoc_part_seen and part in part_nav:
        p_cid, p_label = part_nav_label(part)
        noscript_toc_parts.append(
            f'<li class="ntoc-ch ntoc-part"><a href="#{p_cid}">{e(p_label)}</a></li>')
    ntoc_part_seen = part
    cid = part_chapter_to_cid.get((part, chapter), '')
    gl = chapter_group_label(part, chapter, ch_label)
    noscript_toc_parts.append(f'<li class="ntoc-ch"><a href="#{cid}">{e(gl)}</a>')
    secs = sorted(secs_by_ch.get((part, chapter), []), key=lambda x: x['section'])
    if secs:
        noscript_toc_parts.append('<ul>')
        for s in secs:
            noscript_toc_parts.append(f'<li class="ntoc-sec"><a href="#{s["id"]}">{e(s["label"])}</a></li>')
        noscript_toc_parts.append('</ul>')
    noscript_toc_parts.append('</li>')
noscript_toc_parts.append('</ul>')
noscript_toc_html = '\n'.join(noscript_toc_parts)

# Per-chapter indicator segments. By default each para is its own seg
# ('paragraphs' mode); for long docs that's too dense, so we can switch
# to 'sections' where each section is a single seg covering its para
# range. The cur-para JS test (curPara within [first, last]) is the same
# either way — JS doesn't know or care which mode.
DOC_INDICATOR_LEVEL = {
    'laudato_si': 'sections',   # 246 paras across 36 sections — much cleaner
    'magnifica_humanitas': 'sections',
    'verbum_domini': 'sections',
}
indicator_level = DOC_INDICATOR_LEVEL.get(args.doc, 'paragraphs')

ch_paras: dict[str, list[int]] = {}
for idx, p in enumerate(paragraphs):
    if not p.get('hide_number', False):
        ch_paras.setdefault(para_ch_id[para_id_by_index[idx]], []).append(p['number'])

# Map each section id → its (first, last) paragraph range so we can
# build section-mode segs without re-walking paragraphs.
sec_paras: dict[str, list[int]] = defaultdict(list)
for p in paragraphs:
    if p['section']:
        sid = f'sec-{p["part"]}-{p["chapter"]}-{p["section"]}'
        sec_paras[sid].append(p['number'])

sub_paras: dict[str, list[int]] = defaultdict(list)
for idx, p in enumerate(paragraphs):
    sid = para_to_sub_id.get(para_id_by_index[idx], '')
    if sid:
        sub_paras[sid].append(p['number'])

for ch in indicator_chapters:
    paras = sorted(ch_paras.get(ch['id'], []))
    ch_secs = [s for s in sections_for_drawer
               if part_chapter_to_cid.get((s['part'], s['chapter'])) == ch['id']]
    ch_subs = [s for s in subs_for_drawer
               if part_chapter_to_cid.get((s['part'], s['chapter'])) == ch['id']]

    if indicator_level == 'sections' and ch_secs:
        # Include any chapter opening before its first named section, then
        # one segment per section in document order.
        ch['segs'] = []
        first_sec_para = min(
            min(sec_paras[s['id']]) for s in ch_secs if sec_paras.get(s['id'])
        )
        leading = [p for p in paras if p < first_sec_para]
        if leading:
            ch['segs'].append({
                'first': min(leading), 'last': max(leading),
                'target': ch['id'], 'label': ch['label'],
            })
        for s in sorted(ch_secs, key=lambda x: x['section']):
            sp = sec_paras.get(s['id'], [])
            if sp:
                ch['segs'].append({
                    'first': min(sp), 'last': max(sp),
                    'target': s['id'], 'label': s['label'],
                })
    elif indicator_level == 'sections' and ch_subs:
        # LS's introduction is divided by authored italic headings rather
        # than numbered sections. Reflect that structure when it is the
        # lowest available level instead of collapsing the introduction.
        ch['segs'] = []
        first_sub_para = min(
            min(sub_paras[s['id']]) for s in ch_subs if sub_paras.get(s['id'])
        )
        leading = [p for p in paras if p < first_sub_para]
        if leading:
            ch['segs'].append({
                'first': min(leading), 'last': max(leading),
                'target': ch['id'], 'label': ch['label'],
            })
        for s in ch_subs:
            sp = sub_paras.get(s['id'], [])
            if sp:
                ch['segs'].append({
                    'first': min(sp), 'last': max(sp),
                    'target': s['id'], 'label': s['label'],
                })
    elif indicator_level == 'sections' and paras:
        ch['segs'] = [{
            'first': min(paras), 'last': max(paras),
            'target': ch['id'], 'label': ch['label'],
        }]
    else:
        # paragraphs mode — one seg per paragraph (the GeS default)
        ch['segs'] = [{
            'first': p, 'last': p,
            'target': f'para-{p}', 'label': f'§{p}',
        } for p in paras]

    # JS still wants ch.paras for the para → chapter index lookup
    ch['paras'] = paras

# Appendices are rendered outside `paragraphs[]` but remain root-level
# reading regions: include them alongside unparted chapters in the indicator.
for idx, appendix in enumerate(appendices):
    aid = f'appendix-{idx + 1}'
    indicator_chapters.append({
        'id': aid,
        'label': appendix['title'],
        'spacer': False,
        'part': 0,
        'paras': [aid],
        'segs': [{
            'key': aid,
            'target': aid,
            'label': appendix['title'],
        }],
    })

indicator_json = json.dumps(indicator_chapters)

JS = (JS_TEMPLATE
      .replace('__INDICATOR_JSON__', indicator_json)
      .replace('__DOC_NAME__', json.dumps(doc_name)))

page = f"""<!DOCTYPE html>
<html lang="en" class="no-js" style="--hue: {doc_hue}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="icon" href="favicon.ico" type="image/x-icon">
<title>{e(doc_name)}</title>
<style>{CSS}</style>
<script>
  document.documentElement.classList.remove('no-js');
  // Apply saved prefs before paint to avoid a flash of the default theme.
  // 'auto' (or no value) for theme leaves the attr unset so the CSS
  // prefers-color-scheme media query decides.
  try {{
    const p = JSON.parse(localStorage.getItem('va_reader_prefs') || '{{}}');
    if (p.theme === 'light' || p.theme === 'dark') document.documentElement.dataset.theme = p.theme;
    if (p.size) document.documentElement.dataset.size = p.size;
    if (p.font) document.documentElement.dataset.font = p.font;
  }} catch (e) {{}}
</script>
</head>
<body class="doc-{args.doc}{layout_classes}">
<noscript>
<p class="noscript-banner noscript-screen">Non-interactive render, you might want to enable JavaScript.<a href="https://circulars.forthrast.com">circulars.forthrast.com</a></p>
<p class="noscript-banner noscript-print">Printed from circulars.forthrast.com</p>
</noscript>
<div id="doc-title-corner">{e(doc_name)}</div>
<div id="sticky-bar">
  <span id="sticky-text">
    <span id="sticky-line">
      <span id="sticky-num"></span>
      <span id="sticky-label"></span>
    </span>
    <span id="sticky-sub"></span>
  </span>
</div>

<div id="bar-actions">
  <button id="action-home" aria-label="Home" title="Home"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 14 15" width="12" height="13" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"><path d="M7,1 L13,7 L13,14 L9,14 L9,9 L5,9 L5,14 L1,14 L1,7 Z"/></svg></button>
  <button id="action-info" aria-label="About this document" title="About">i</button>
  <button id="action-prefs" aria-label="Reader settings" title="Reader settings"><span class="a-small">a</span>A</button>
  <button id="fn-tab" aria-label="Notes &amp; contents" title="Notes &amp; contents" aria-expanded="false"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 14 9" width="14" height="9" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><line x1="0" y1="1.5" x2="14" y2="1.5"/><line x1="5" y1="4.5" x2="14" y2="4.5"/><line x1="9" y1="7.5" x2="14" y2="7.5"/></svg></button>
</div>

<div id="info-panel" hidden>
  <p class="panel-title">About this edition</p>
  <p>Generated via templater scripts from Vatican HTML.</p>
  {f'<p><a href="{e(doc_source)}" target="_blank" rel="noopener">Original Vatican document</a></p>' if doc_source else ''}
  <p>Email: <a href="mailto:me@forthrast.com">me@forthrast.com</a><br>
  Bluesky: <a href="https://bsky.app/profile/forthrast.com" target="_blank" rel="noopener">@forthrast.com</a><br>
  GitHub: <a href="https://github.com/forthrast-com/va_beautifier" target="_blank" rel="noopener">@forthrast-com</a></p>
</div>

<div id="prefs-panel" hidden>
  <div class="pref-row">
    <span class="pref-label">Theme</span>
    <div class="pref-segments">
      <button data-pref="theme" data-value="auto"  title="Follow system">Auto</button>
      <button data-pref="theme" data-value="light">Light</button>
      <button data-pref="theme" data-value="dark">Dark</button>
    </div>
  </div>
  <div class="pref-row">
    <span class="pref-label">Size</span>
    <div class="pref-segments">
      <button class="size-s" data-pref="size" data-value="small"  title="Small">A</button>
      <button class="size-m" data-pref="size" data-value="medium" title="Medium">A</button>
      <button class="size-l" data-pref="size" data-value="large"  title="Large">A</button>
    </div>
  </div>
  <div class="pref-row">
    <span class="pref-label">Font</span>
    <div class="pref-segments">
      <button data-pref="font" data-value="serif">Serif</button>
      <button data-pref="font" data-value="sans">Sans</button>
    </div>
  </div>
</div>

{title_block}
<noscript>
<nav class="noscript-toc">
  <h2>Contents</h2>
  {noscript_toc_html}
</nav>
</noscript>
{''.join(html_parts)}
{appendix_html}
{end_matter_html}

<noscript>
<section class="noscript-fn">
  <h2>Notes</h2>
  {fn_drawer_html}
</section>
</noscript>

<nav id="ch-indicator"></nav>

<aside id="fn-drawer">
  <div id="fn-content">
    <div class="drawer-tabs" role="tablist" aria-label="Drawer view">
      <button class="drawer-view-tab active" type="button" role="tab" aria-controls="drawer-toc"       aria-selected="true"  data-drawer-view="toc">Contents</button>
      <button class="drawer-view-tab"        type="button" role="tab" aria-controls="drawer-footnotes" aria-selected="false" data-drawer-view="footnotes">Footnotes</button>
      <button class="drawer-view-tab"        type="button" role="tab" aria-controls="drawer-bookmarks" aria-selected="false" data-drawer-view="bookmarks">Bookmarks</button>
    </div>
    <div id="drawer-toc" class="drawer-view active" role="tabpanel">
      {toc_drawer_html}
    </div>
    <div id="drawer-footnotes" class="drawer-view" role="tabpanel" hidden>
      {fn_drawer_html}
    </div>
    <div id="drawer-bookmarks" class="drawer-view" role="tabpanel" hidden>
      <div class="bookmarks-empty">
        <p>No bookmarks yet.</p>
        <p>In Contents, hover over a heading and select its bookmark icon to save it here.</p>
      </div>
      <div id="bookmark-list"></div>
    </div>
  </div>
</aside>
<script>{JS}</script>
</body>
</html>
"""

SITE.mkdir(exist_ok=True)
out_path = SITE / f'{args.doc}.html'
out_path.write_text(page, encoding='utf-8')

print(f'Wrote {out_path} — {len(paragraphs)} paragraphs, {len(footnotes)} footnotes')
