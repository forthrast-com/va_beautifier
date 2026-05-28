import argparse
import json
import re
from collections import defaultdict
from html import escape

from core import CANONICAL_FOOTNOTE_REF, int_to_roman, read_toml, title_case
from project import ASSETS, BUILD, SITE

CSS         = (ASSETS / 'styles.css').read_text()
JS_TEMPLATE = (ASSETS / 'scripts.js').read_text()

# External hyperlinks come through clean_text as `[text](href)` markdown.
# `[^)\s]+` for the href so a stray `)` in surrounding prose can't extend
# the match — vatican.va URLs are paren-free.
INLINE_LINK_RE = re.compile(r'\[([^\]]+)\]\(([^)\s]+)\)')
INLINE_STRONG_RE = re.compile(r'\*\*(.+?)\*\*')
INLINE_EM_RE = re.compile(r'(?<!\*)\*([^*\n]+?)\*(?!\*)')
INLINE_SCRIPT_RE = re.compile(r'&lt;(sup|sub)&gt;(.*?)&lt;/\1&gt;')

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
footnotes    = data['footnotes']
appendices   = data.get('appendices', [])
doc_name     = data.get('name', args.doc)
doc_source   = data.get('source_url', '')
doc_desc      = data.get('desc', '')
doc_desc_post = data.get('desc_post', '')
doc_promulg   = data.get('promulgation', '')
doc_signature = data.get('signature', '')

# Default = warm gold for legacy TOML files without explicit document colour.
doc_hue = data.get('hue', 42)

# ── helpers ──────────────────────────────────────────────────────────────────

def e(s): return escape(s)

def linkify_footnotes(text, part, chapter):
    """Replace (N) inline refs with linked superscripts."""
    def replace(m):
        n = m.group(1)
        return f'<sup><a href="#fn-{part}-{chapter}-{n}">{n}</a></sup>'
    return CANONICAL_FOOTNOTE_REF.sub(replace, text)

def linkify_anchors(text):
    """Convert `[text](href)` markdown back to anchor tags.

    Run BEFORE linkify_footnotes so the URL's parens get consumed before the
    footnote regex sees them and mistakes (e.g.) `(2021)` for a fn ref."""
    def replace(m):
        body, href = m.group(1), m.group(2)
        return f'<a href="{href}" class="ext-link" target="_blank" rel="noopener">{body}</a>'
    return INLINE_LINK_RE.sub(replace, text)

def format_inline(text):
    """Render the restricted Markdown-compatible markup emitted by `core`."""
    text = INLINE_SCRIPT_RE.sub(r'<\1>\2</\1>', text)
    text = INLINE_STRONG_RE.sub(r'<strong>\1</strong>', text)
    return INLINE_EM_RE.sub(r'<em>\1</em>', text)

def para_html(text, part=None, chapter=None):
    """Convert paragraph text to <p> tags.

    `\\n\\n` separates sub-paragraphs (each becomes its own <p>).
    `\\n` within a sub-paragraph is a poetic line break and becomes <br>
    (the LS canticle + closing prayers use this).
    """
    text = tighten(text)
    out = []
    for sub in [p.strip() for p in text.split('\n\n') if p.strip()]:
        lines = sub.split('\n')
        rendered = []
        for ln in lines:
            ln = e(ln)
            ln = linkify_anchors(ln)
            if part is not None:
                ln = linkify_footnotes(ln, part, chapter)
            ln = format_inline(ln)
            rendered.append(ln)
        out.append('<p>' + '<br>'.join(rendered) + '</p>')
    return '\n'.join(out)

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


def _desc_block(text, cls, *, break_before_on=False):
    """Render `text` (one source line per output span) as a centred desc
    paragraph. With `break_before_on`, insert a hard line break before any
    line starting with "ON " — the modern encyclicals' subtitles open
    with "ON CARE FOR…" / "ON SAFEGUARDING…", and the user wants those
    visually separated from the preceding "OF THE HOLY FATHER / NAME"
    stanza regardless of viewport width."""
    pieces = []
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        if break_before_on and pieces and ln.upper().startswith('ON '):
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

MODERN_DOCS = {'laudato_si', 'magnifica_humanitas'}

# The Vatican sources place the document title *between* lines of the
# front-matter block: e.g. MH has "ENCYCLICAL LETTER" above the title and
# "OF HIS HOLINESS … IN THE TIME OF AI" below; GeS has "PASTORAL
# CONSTITUTION …" above the title and "PROMULGATED BY … DECEMBER 7, 1965"
# below. Each extractor pre-splits these into desc (above) + desc_post
# (below); the renderer just stacks them around the name.
title_block = ''
if doc_desc or doc_name or doc_desc_post:
    is_modern = args.doc in MODERN_DOCS
    title_block = (
        '<div class="doc-title">'
        + _desc_block(doc_desc, 'doc-desc doc-desc-pre')
        + f'<p class="doc-name">{e(doc_name)}</p>'
        + _desc_block(doc_desc_post, 'doc-desc doc-desc-post',
                      break_before_on=is_modern)
        + '</div>'
    )

# Dedication + papal signature belong at the END in the Vatican sources
# (after the body, just before the footnote block), not in the front matter
# where the dedication used to live.
end_matter_html = ''
if doc_promulg or doc_signature:
    parts = ['<div class="doc-end-matter">']
    if doc_promulg:
        promulg_spans = " ".join(
            f'<span style="display:inline-block">{e(l.strip())}</span>'
            for l in doc_promulg.splitlines() if l.strip()
        )
        parts.append(f'<p class="doc-promulg">{promulg_spans}</p>')
    if doc_signature:
        parts.append(f'<p class="doc-signature">{e(doc_signature)}</p>')
    parts.append('</div>')
    end_matter_html = ''.join(parts)

html_parts = []

def h(tag, cls, text):
    return f'<{tag} class="{cls}">{e(text)}</{tag}>'

seen_part        = object()
seen_chapter     = object()
seen_section     = object()
seen_sub_heading = object()

sections_for_drawer = []  # list of {id, label, chapter_label}
subs_for_drawer    = []   # list of {id, label, part, chapter, section, first_para}
para_to_sub_id     = {}   # para_num → sub id ('' if no sub-heading)
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

# para → indicator chapter id (for ch_paras)
para_ch_id: dict[int, str] = {}

for p in paragraphs:
    part    = (p['part'], p['part_title'])
    chapter = (p['chapter'], p['chapter_title'], p.get('chapter_subtitle', ''))
    section = (p['section'], p['section_title'])

    if part != seen_part:
        cid = next_cid()
        if p['part'] == 0:
            # Preface/introduction group. Documents that name it (GeS) get
            # the heading; documents that don't (LS) still get an indicator
            # entry so the bars cover the unnumbered intro paragraphs.
            label = p['part_title'] or 'Introduction'
            indicator_chapters.append({'id': cid, 'label': label, 'spacer': False, 'part': 0})
            if p['part_title']:
                html_parts.append(h('h1', 'part-title', p['part_title']).replace('<h1 ', f'<h1 id="{cid}" data-sticky '))
            else:
                # anchor-only — give the next element the id instead of leaving an empty <h1>
                html_parts.append(f'<a id="{cid}"></a>')
        else:
            indicator_chapters.append({'id': cid, 'label': f'Part {int_to_roman(p["part"])}', 'spacer': True, 'part': p['part']})
            html_parts.append(h('h1', 'part-num', f'Part {int_to_roman(p["part"])}').replace('<h1 ', f'<h1 id="{cid}" '))
            if p['part_title']:
                html_parts.append(h('h2', 'part-title', p['part_title']).replace('<h2 ', '<h2 data-sticky '))
        seen_part        = part
        seen_chapter     = object()
        seen_section     = object()
        seen_sub_heading = object()

    if chapter != seen_chapter and p['chapter'] != 0:
        cid = next_cid()
        label = p['chapter_title'] or (
            f'Part {int_to_roman(p["part"])}, Ch. {p["chapter"]}' if p['part']
            else f'Chapter {p["chapter"]}'
        )
        indicator_chapters.append({'id': cid, 'label': label, 'spacer': False, 'part': p['part']})
        # The conclusion is structurally a chapter but the source labels it
        # only 'CONCLUSION', not 'CHAPTER SIX' — suppress the "Chapter N"
        # prefix so the rendered heading matches the source. The id then
        # rides on the title <h3> instead of the (omitted) chapter-num <h2>.
        is_unnumbered = p['chapter_title'].strip().lower() == 'conclusion'
        if not is_unnumbered:
            html_parts.append(h('h2', 'chapter-num', f'Chapter {p["chapter"]}').replace('<h2 ', f'<h2 id="{cid}" '))
        if p['chapter_title']:
            ch_num = f'{int_to_roman(p["part"])}.{p["chapter"]}' if p['part'] else f'{p["chapter"]}'
            id_attr = f'id="{cid}" ' if is_unnumbered else ''
            html_parts.append(
                h('h3', 'chapter-title', p['chapter_title'])
                .replace('<h3 ', f'<h3 {id_attr}data-sticky data-ch-num="{ch_num}" ')
            )
            if p.get('chapter_subtitle', ''):
                html_parts.append(h('p', 'chapter-subtitle', p['chapter_subtitle']))
        seen_chapter     = chapter
        seen_section     = object()
        seen_sub_heading = object()

    para_ch_id[p['number']] = indicator_chapters[-1]['id']

    if section != seen_section and p['section'] != 0:
        sec_id = f'sec-{p["part"]}-{p["chapter"]}-{p["section"]}'
        if args.doc == 'magnifica_humanitas':
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
            _cur_sub_id = f'sub-{p["number"]}'
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
    para_to_sub_id[p['number']] = _cur_sub_id

    # paragraph block
    num  = p['number']
    head = p.get('heading_la', '')
    body = para_html(p['text'], p['part'], p['chapter'])

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
    elif args.doc in MODERN_DOCS:
        sub_text = p['section_title'] if p['section'] else ''
    else:
        sub_text = _cur_sub_text

    html_parts.append(
        f'<div class="paragraph" id="para-{num}" data-sub-text="{e(sub_text)}">'
        f'<span class="para-num">{num}</span>'
        + (f' <em class="heading-la">{e(head)}</em>' if head else '')
        + f'\n{body}'
        f'</div>'
    )
    if p.get('break_after', False):
        html_parts.append('<hr class="document-break">')

# (part, chapter) → first cid containing those paragraphs (for footnote links)
part_chapter_to_cid: dict[tuple, str] = {}
for p in paragraphs:
    key = (p['part'], p['chapter'])
    if key not in part_chapter_to_cid:
        part_chapter_to_cid[key] = para_ch_id[p['number']]

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
fn_section: dict[tuple, int] = {}
fn_sub:     dict[tuple, str] = {}
fn_para:    dict[tuple, int] = {}
sub_id_by_context: dict[tuple, str] = {}
for sb in subs_for_drawer:
    key = (sb['part'], sb['chapter'], sb['section'], sb['label'])
    sub_id_by_context.setdefault(key, sb['id'])
for fn in footnotes:
    key = (fn['part'], fn['chapter'], fn['number'])
    section = fn.get('section', 0)
    fn_section[key] = section
    sub_heading = fn.get('sub_heading', '')
    if sub_heading:
        fn_sub[key] = sub_id_by_context.get(
            (fn['part'], fn['chapter'], section, sub_heading), ''
        )
for p in paragraphs:
    refs = CANONICAL_FOOTNOTE_REF.findall(p['text'])
    for r in refs:
        key = (p['part'], p['chapter'], int(r))
        if key not in fn_para:
            fn_para[key] = p['number']
        # Keep older TOML intermediates renderable until they are rebuilt.
        fn_section.setdefault(key, p['section'])
        fn_sub.setdefault(key, para_to_sub_id.get(p['number'], ''))

# chapter order from document
ch_order = []
seen_ch_order = set()
for p in paragraphs:
    key = (p['part'], p['chapter'])
    if key not in seen_ch_order:
        if p['part'] == 0 and p['chapter'] == 0:
            label = p['part_title']                     # preface / introduction
        elif p['part'] == 0:
            label = p['chapter_title'] or f'Chapter {p["chapter"]}'
        else:
            label = p['chapter_title'] or f'Part {int_to_roman(p["part"])}, Ch. {p["chapter"]}'
        ch_order.append((key, label))
        seen_ch_order.add(key)

def fn_item_html(part, chapter, fn):
    key  = (part, chapter, fn['number'])
    pnum = fn_para.get(key)
    href = f'#para-{pnum}' if pnum else ''
    if href:
        num = f'<a href="{href}" class="fn-num-link">{fn["number"]}</a>'
    else:
        num = f'<span class="fn-num-link">{fn["number"]}</span>'
    body = para_html(fn['text'])
    return f'<li id="fn-{part}-{chapter}-{fn["number"]}" class="fn-item">{num}{body}</li>'

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

drawer_items = []
toc_items = []
for (part, chapter), ch_label in ch_order:
    secs    = secs_by_ch.get((part, chapter), [])
    fns     = fns_by_ch.get((part, chapter), [])
    ch_subs = [sb for sb in subs_for_drawer
               if sb['part'] == part and sb['chapter'] == chapter]
    cid = part_chapter_to_cid.get((part, chapter), '')
    if part == 0 and chapter == 0:
        group_label = ch_label or 'Preface / Introduction'
    elif part == 0:
        group_label = ch_label or f'Chapter {chapter}'
    else:
        group_label = ch_label or f'Part {int_to_roman(part)}, Chapter {chapter}'
    toc_items.append(toc_item('h3', 'fn-group', 'fn-ch-link', cid, group_label))

    for sb in subs_by_chsec.get((part, chapter, 0), []):
        toc_items.append(toc_item('p', 'sub-nav-item', 'sub-nav-link', sb['id'], sb['label']))
    for s in sorted(secs, key=lambda x: x['section']):
        toc_items.append(toc_item('p', 'sec-nav-item', 'sec-nav-link', s['id'], s['label']))
        for sb in subs_by_chsec.get((part, chapter, s['section']), []):
            toc_items.append(toc_item('p', 'sub-nav-item', 'sub-nav-link', sb['id'], sb['label']))

    if not secs and not fns and not ch_subs:
        continue
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
        sec = fn_section.get((part, chapter, fn['number']), 0)
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
            drawer_items.append(f'<p class="sec-nav-item"><a class="sec-nav-link" href="#{s["id"]}">{e(s["label"])}</a></p>')

        # Bucket the section's footnotes by which sub-heading (if any)
        # the citing paragraph fell under.
        fns_by_sub: dict[str, list] = defaultdict(list)
        for fn in sec_fns:
            sid = fn_sub.get((part, chapter, fn['number']), '')
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
        toc_item('p', 'sec-nav-item', 'sec-nav-link',
                 f'appendix-{idx + 1}', app['title'])
    )

# ── appendices (e.g. LS's two closing prayers) ───────────────────────────────

appendix_html = ''
if appendices:
    parts = ['<section class="appendix-block">']
    for idx, app in enumerate(appendices):
        aid = f'appendix-{idx + 1}'
        stanzas = para_html(app['text'])    # honours \n\n and \n the same way as body paragraphs
        parts.append(
            f'<div class="appendix" id="{aid}">'
            f'<h2 class="appendix-title" data-sticky>{e(app["title"])}</h2>'
            f'{stanzas}'
            f'</div>'
        )
    parts.append('</section>')
    appendix_html = '\n'.join(parts)

# ── page ──────────────────────────────────────────────────────────────────────


fn_drawer_html = '\n'.join(drawer_items)
toc_drawer_html = '\n'.join(toc_items)

# Per-chapter indicator segments. By default each para is its own seg
# ('paragraphs' mode); for long docs that's too dense, so we can switch
# to 'sections' where each section is a single seg covering its para
# range. The cur-para JS test (curPara within [first, last]) is the same
# either way — JS doesn't know or care which mode.
DOC_INDICATOR_LEVEL = {
    'laudato_si': 'sections',   # 246 paras across 36 sections — much cleaner
    'magnifica_humanitas': 'sections',
}
indicator_level = DOC_INDICATOR_LEVEL.get(args.doc, 'paragraphs')

ch_paras: dict[str, list[int]] = {}
for pnum, cid in para_ch_id.items():
    ch_paras.setdefault(cid, []).append(pnum)

# Map each section id → its (first, last) paragraph range so we can
# build section-mode segs without re-walking paragraphs.
sec_paras: dict[str, list[int]] = defaultdict(list)
for p in paragraphs:
    if p['section']:
        sid = f'sec-{p["part"]}-{p["chapter"]}-{p["section"]}'
        sec_paras[sid].append(p['number'])

for ch in indicator_chapters:
    paras = sorted(ch_paras.get(ch['id'], []))
    ch_secs = [s for s in sections_for_drawer
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
    elif indicator_level == 'sections' and paras:
        # chapter has paragraphs but no sections (e.g. LS preface) —
        # one seg covering the whole chapter
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

indicator_json = json.dumps(indicator_chapters)

JS = (JS_TEMPLATE
      .replace('__INDICATOR_JSON__', indicator_json)
      .replace('__DOC_NAME__', json.dumps(doc_name)))

page = f"""<!DOCTYPE html>
<html lang="en" style="--hue: {doc_hue}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="icon" href="favicon.ico" type="image/x-icon">
<title>{e(doc_name)}</title>
<style>{CSS}</style>
<script>
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
<body class="doc-{args.doc}">
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
  <button id="action-home" aria-label="Home" title="Home">⌂</button>
  <button id="action-info" aria-label="About this document" title="About">i</button>
  <button id="action-prefs" aria-label="Reader settings" title="Reader settings"><span class="a-small">a</span>A</button>
  <button id="fn-tab" aria-label="Notes &amp; contents" title="Notes &amp; contents" aria-expanded="false"><span class="dr-lines"><span>—</span><span>–</span><span>-</span></span></button>
</div>

<div id="info-panel" hidden>
  <p class="panel-title">About this edition</p>
  <p>Generated via templater scripts from Vatican HTML.</p>
  {f'<p><a href="{e(doc_source)}" target="_blank" rel="noopener">Original Vatican document</a></p>' if doc_source else ''}
  <p>Email: <a href="mailto:me@forthrast.com">me@forthrast.com</a><br>
  Bluesky: <a href="https://bsky.app/profile/forthrast.com" target="_blank" rel="noopener">@forthrast.com</a><br>
  GitHub: <a href="https://github.com/forthrast-com" target="_blank" rel="noopener">@forthrast-com</a></p>
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
{''.join(html_parts)}
{appendix_html}
{end_matter_html}

<nav id="ch-indicator"></nav>

<aside id="fn-drawer">
  <div id="fn-content">
    <div class="drawer-tabs" role="tablist" aria-label="Drawer view">
      <button class="drawer-view-tab active" type="button" role="tab" aria-controls="drawer-toc" aria-selected="true" data-drawer-view="toc">Contents</button>
      <button class="drawer-view-tab" type="button" role="tab" aria-controls="drawer-footnotes" aria-selected="false" data-drawer-view="footnotes">Footnotes</button>
      <button class="drawer-view-tab" type="button" role="tab" aria-controls="drawer-bookmarks" aria-selected="false" data-drawer-view="bookmarks">Bookmarks</button>
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
