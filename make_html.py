import argparse
import json
import re
import tomllib
from collections import defaultdict
from html import escape
from pathlib import Path

ASSETS = Path(__file__).parent / 'assets'
CSS         = (ASSETS / 'styles.css').read_text()
JS_TEMPLATE = (ASSETS / 'scripts.js').read_text()

# Inline footnote refs: paragraph text carries them as canonical `(N)`. We
# match 1-3 digits to avoid catching years/citations like "(1995)".
INLINE_REF_RE = re.compile(r'\((\d{1,3})\)')

ap = argparse.ArgumentParser(description='Render a TOML intermediate to a single-file HTML edition.')
ap.add_argument('doc', help='Doc slug (looks for {slug}.toml, writes {slug}.html)')
args = ap.parse_args()

with open(f'{args.doc}.toml', 'rb') as f:
    data = tomllib.load(f)

paragraphs   = data['paragraphs']
footnotes    = data['footnotes']
appendices   = data.get('appendices', [])
doc_name     = data.get('name', args.doc)
doc_desc     = data.get('desc', '')
doc_promulg  = data.get('promulgation', '')

# Per-doc accent hue. Drives the whole hsl() accent palette in styles.css
# via an inline `style="--hue: …"` on the <html> tag. Default = warm gold.
DOC_HUES = {
    'laudato_si': 140,   # botanical green for the ecology encyclical
    # 'dilexit_nos': 8,  # red, when the doc lands
}
doc_hue = DOC_HUES.get(args.doc, 42)

# ── helpers ──────────────────────────────────────────────────────────────────

def e(s): return escape(s)

def to_roman(n):
    result = ''
    for val, sym in [(1000,'M'),(900,'CM'),(500,'D'),(400,'CD'),(100,'C'),(90,'XC'),
                     (50,'L'),(40,'XL'),(10,'X'),(9,'IX'),(5,'V'),(4,'IV'),(1,'I')]:
        while n >= val:
            result += sym
            n -= val
    return result

def linkify_footnotes(text, part, chapter):
    """Replace (N) inline refs with linked superscripts."""
    def replace(m):
        n = m.group(1)
        return f'<sup><a href="#fn-{part}-{chapter}-{n}">{n}</a></sup>'
    return INLINE_REF_RE.sub(replace, text)

def para_html(text, part=None, chapter=None):
    """Convert paragraph text (double-newline separated) to <p> tags."""
    parts = [p.strip() for p in text.split('\n\n') if p.strip()]
    return '\n'.join(
        f'<p>{linkify_footnotes(e(p), part, chapter) if part is not None else e(p)}</p>'
        for p in parts
    )

# footnotes indexed by (part, chapter, number)
fn_index = {(fn['part'], fn['chapter'], fn['number']): fn for fn in footnotes}


# ── build sections ────────────────────────────────────────────────────────────

title_block = ''
if doc_desc or doc_promulg:
    title_block = (
        '<div class="doc-title">'
        + (f'<p class="doc-desc">{" ".join(f'<span style="display:inline-block">{e(l.strip())}</span>' for l in doc_desc.splitlines() if l.strip())}</p>' if doc_desc else '')
        + f'<p class="doc-name">{e(doc_name)}</p>'
        + (f'<p class="doc-promulg">{" ".join(f'<span style="display:inline-block">{e(l.strip())}</span>' for l in doc_promulg.splitlines() if l.strip())}</p>' if doc_promulg else '')
        + '</div>'
    )

html_parts = []

def h(tag, cls, text):
    return f'<{tag} class="{cls}">{e(text)}</{tag}>'

seen_part        = object()
seen_chapter     = object()
seen_section     = object()
seen_sub_heading = object()

sections_for_drawer = []  # list of {id, label, chapter_label}

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
    chapter = (p['chapter'], p['chapter_title'])
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
            indicator_chapters.append({'id': cid, 'label': f'Part {to_roman(p["part"])}', 'spacer': True, 'part': p['part']})
            html_parts.append(h('h1', 'part-num', f'Part {to_roman(p["part"])}').replace('<h1 ', f'<h1 id="{cid}" '))
            if p['part_title']:
                html_parts.append(h('h2', 'part-title', p['part_title']).replace('<h2 ', '<h2 data-sticky '))
        seen_part        = part
        seen_chapter     = object()
        seen_section     = object()
        seen_sub_heading = object()

    if chapter != seen_chapter and p['chapter'] != 0:
        cid = next_cid()
        label = p['chapter_title'] or (
            f'Part {to_roman(p["part"])}, Ch. {p["chapter"]}' if p['part']
            else f'Chapter {p["chapter"]}'
        )
        indicator_chapters.append({'id': cid, 'label': label, 'spacer': False, 'part': p['part']})
        html_parts.append(h('h2', 'chapter-num', f'Chapter {p["chapter"]}').replace('<h2 ', f'<h2 id="{cid}" '))
        if p['chapter_title']:
            ch_num = f'{to_roman(p["part"])}.{p["chapter"]}' if p['part'] else f'{p["chapter"]}'
            html_parts.append(h('h3', 'chapter-title', p['chapter_title']).replace('<h3 ', f'<h3 data-sticky data-ch-num="{ch_num}" '))
        seen_chapter     = chapter
        seen_section     = object()
        seen_sub_heading = object()

    para_ch_id[p['number']] = indicator_chapters[-1]['id']

    if section != seen_section and p['section'] != 0:
        sec_id = f'sec-{p["part"]}-{p["chapter"]}-{p["section"]}'
        label = f'Section {p["section"]}'
        if p['section_title']:
            label += f': {p["section_title"]}'
        ch_label = p['chapter_title'] or f'Part {to_roman(p["part"])}, Ch. {p["chapter"]}'
        sections_for_drawer.append({'id': sec_id, 'label': label, 'ch_label': ch_label,
                                     'part': p['part'], 'chapter': p['chapter'],
                                     'section': p['section']})
        html_parts.append(h('h4', 'section-title', label).replace('<h4 ', f'<h4 id="{sec_id}" '))
        seen_section     = section
        seen_sub_heading = object()

    sub = p.get('sub_heading', '')
    if sub != seen_sub_heading:
        if sub:
            html_parts.append(h('h5', 'sub-heading', sub))
        seen_sub_heading = sub

    # paragraph block
    num  = p['number']
    head = p.get('heading_la', '')
    body = para_html(p['text'], p['part'], p['chapter'])

    # The period after the number is added by CSS for docs that want it
    # (GeS inline-style); LS keeps the number naked in its gutter column.
    html_parts.append(
        f'<div class="paragraph" id="para-{num}">'
        f'<span class="para-num">{num}</span>'
        + (f' <em class="heading-la">{e(head)}</em>' if head else '')
        + f'\n{body}'
        f'</div>'
    )

# (part, chapter) → first cid containing those paragraphs (for footnote links)
part_chapter_to_cid: dict[tuple, str] = {}
for p in paragraphs:
    key = (p['part'], p['chapter'])
    if key not in part_chapter_to_cid:
        part_chapter_to_cid[key] = para_ch_id[p['number']]

# ── drawer: sections + footnotes interleaved by chapter ───────────────────────

secs_by_ch = defaultdict(list)
for s in sections_for_drawer:
    secs_by_ch[(s['part'], s['chapter'])].append(s)

fns_by_ch = defaultdict(list)
for fn in footnotes:
    fns_by_ch[(fn['part'], fn['chapter'])].append(fn)

# Map (part, chapter, fn_number) → (section, para_number) via first paragraph that cites it
fn_section: dict[tuple, int] = {}
fn_para:    dict[tuple, int] = {}
for p in paragraphs:
    refs = INLINE_REF_RE.findall(p['text'])
    for r in refs:
        key = (p['part'], p['chapter'], int(r))
        if key not in fn_section:
            fn_section[key] = p['section']
            fn_para[key]    = p['number']

# chapter order from document
ch_order = []
seen_ch_order = set()
for p in paragraphs:
    key = (p['part'], p['chapter'])
    if key not in seen_ch_order:
        ch_order.append((key, p['part_title'] if p['part'] == 0 else
                         (p['chapter_title'] or f'Part {to_roman(p["part"])}, Ch. {p["chapter"]}')))
        seen_ch_order.add(key)

def fn_item_html(part, chapter, fn):
    key  = (part, chapter, fn['number'])
    pnum = fn_para.get(key)
    href = f'#para-{pnum}' if pnum else ''
    num  = f'<a href="{href}" class="fn-num-link">{fn["number"]}.</a>' if href else f'{fn["number"]}.'
    body = para_html(fn['text'])
    return f'<li id="fn-{part}-{chapter}-{fn["number"]}" class="fn-item">{num} {body}</li>'

drawer_items = []
for (part, chapter), ch_label in ch_order:
    secs = secs_by_ch.get((part, chapter), [])
    fns  = fns_by_ch.get((part, chapter), [])
    if not secs and not fns:
        continue
    cid = part_chapter_to_cid.get((part, chapter), '')
    group_label = (ch_label or 'Preface / Introduction') if not part else f'Part {to_roman(part)}, Chapter {chapter}'
    drawer_items.append(f'<h3 class="fn-group"><a href="#{cid}" class="fn-ch-link">{e(group_label)}</a></h3>')

    if not secs:
        # no sections — just emit footnotes
        if fns:
            drawer_items.append('<ol class="fn-list">')
            for fn in fns:
                drawer_items.append(fn_item_html(part, chapter, fn))
            drawer_items.append('</ol>')
    else:
        # interleave: for each section emit its heading then its footnotes
        # section 0 = footnotes before the first section heading
        sec_nums = [0] + [s['section'] for s in sorted(secs, key=lambda s: s['section'])]
        sec_meta = {0: None}
        for s in secs:
            sec_meta[s['section']] = s

        fns_by_sec: dict[int, list] = defaultdict(list)
        for fn in fns:
            sec = fn_section.get((part, chapter, fn['number']), 0)
            fns_by_sec[sec].append(fn)

        for sec_num in sec_nums:
            s = sec_meta.get(sec_num)
            if s:
                drawer_items.append(f'<p class="sec-nav-item"><a class="sec-nav-link" href="#{s["id"]}">{e(s["label"])}</a></p>')
            sec_fns = fns_by_sec.get(sec_num, [])
            if sec_fns:
                drawer_items.append('<ol class="fn-list">')
                for fn in sec_fns:
                    drawer_items.append(fn_item_html(part, chapter, fn))
                drawer_items.append('</ol>')

# ── appendices (e.g. LS's two closing prayers) ───────────────────────────────

appendix_html = ''
if appendices:
    parts = ['<section class="appendix-block">']
    for idx, app in enumerate(appendices):
        aid = f'appendix-{idx + 1}'
        stanzas = '\n'.join(
            f'<p>{e(stanza.strip())}</p>'
            for stanza in app['text'].split('\n\n') if stanza.strip()
        )
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

# attach paragraph numbers to each chapter entry
ch_paras: dict[str, list[int]] = {}
for pnum, cid in para_ch_id.items():
    ch_paras.setdefault(cid, []).append(pnum)
for ch in indicator_chapters:
    ch['paras'] = ch_paras.get(ch['id'], [])

indicator_json = json.dumps(indicator_chapters)

JS = (JS_TEMPLATE
      .replace('__INDICATOR_JSON__', indicator_json)
      .replace('__DOC_NAME__', json.dumps(doc_name)))

page = f"""<!DOCTYPE html>
<html lang="en" style="--hue: {doc_hue}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(doc_name)}</title>
<style>{CSS}</style>
<script>
  // Apply saved theme/size before paint to avoid a flash of the default light theme.
  try {{
    const p = JSON.parse(localStorage.getItem('va_reader_prefs') || '{{}}');
    if (p.theme) document.documentElement.dataset.theme = p.theme;
    if (p.size)  document.documentElement.dataset.size  = p.size;
  }} catch (e) {{}}
</script>
</head>
<body class="doc-{args.doc}">
<div id="sticky-bar">
  <span id="sticky-num"></span>
  <span id="sticky-label">{e(doc_name)}</span>
  <div id="bar-actions">
    <button id="action-home" aria-label="Home" title="Home">⌂</button>
    <button id="action-info" aria-label="About this document" title="About">i</button>
    <button id="action-prefs" aria-label="Reader settings" title="Reader settings"><span class="a-small">a</span>A</button>
  </div>
</div>

<div id="prefs-panel" hidden>
  <div class="pref-row">
    <span class="pref-label">Theme</span>
    <div class="pref-segments">
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
</div>

{title_block}
{''.join(html_parts)}
{appendix_html}

<nav id="ch-indicator"></nav>

<aside id="fn-drawer">
  <div id="fn-tab">Notes</div>
  <div id="fn-content">
    {fn_drawer_html}
  </div>
</aside>

<script>{JS}</script>
</body>
</html>
"""

out_path = f'{args.doc}.html'
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(page)

print(f'Wrote {out_path} — {len(paragraphs)} paragraphs, {len(footnotes)} footnotes')
