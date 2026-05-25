import re
import tomllib
from html import escape

with open('gaudium_et_spes.toml', 'rb') as f:
    data = tomllib.load(f)

paragraphs   = data['paragraphs']
footnotes    = data['footnotes']
doc_desc     = data.get('desc', '')
doc_promulg  = data.get('promulgation', '')

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
    """Replace (N) inline refs with linked superscripts. Only 1-3 digit numbers to avoid years."""
    def replace(m):
        n = m.group(1)
        return f'<sup><a href="#fn-{part}-{chapter}-{n}">{n}</a></sup>'
    return re.sub(r'\((\d{1,3})\)', replace, text)

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
        + '<p class="doc-name">Gaudium et Spes</p>'
        + (f'<p class="doc-promulg">{" ".join(f'<span style="display:inline-block">{e(l.strip())}</span>' for l in doc_promulg.splitlines() if l.strip())}</p>' if doc_promulg else '')
        + '</div>'
    )

html_parts = []

def h(tag, cls, text):
    return f'<{tag} class="{cls}">{e(text)}</{tag}>'

seen_part    = object()
seen_chapter = object()
seen_section = object()

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
            indicator_chapters.append({'id': cid, 'label': p['part_title'], 'spacer': False, 'part': p['part']})
            html_parts.append(h('h1', 'part-title', p['part_title']).replace('<h1 ', f'<h1 id="{cid}" data-sticky '))
        else:
            indicator_chapters.append({'id': cid, 'label': f'Part {to_roman(p["part"])}', 'spacer': True, 'part': p['part']})
            html_parts.append(h('h1', 'part-num', f'Part {to_roman(p["part"])}').replace('<h1 ', f'<h1 id="{cid}" '))
            if p['part_title']:
                html_parts.append(h('h2', 'part-title', p['part_title']).replace('<h2 ', '<h2 data-sticky '))
        seen_part    = part
        seen_chapter = object()
        seen_section = object()

    if chapter != seen_chapter and p['chapter'] != 0:
        cid = next_cid()
        label = p['chapter_title'] or f'Part {to_roman(p["part"])}, Ch. {p["chapter"]}'
        indicator_chapters.append({'id': cid, 'label': label, 'spacer': False, 'part': p['part']})
        html_parts.append(h('h2', 'chapter-num', f'Chapter {p["chapter"]}').replace('<h2 ', f'<h2 id="{cid}" '))
        if p['chapter_title']:
            ch_num = f'{to_roman(p["part"])}.{p["chapter"]}'
            html_parts.append(h('h3', 'chapter-title', p['chapter_title']).replace('<h3 ', f'<h3 data-sticky data-ch-num="{ch_num}" '))
        seen_chapter = chapter
        seen_section = object()

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
        seen_section = section

    # paragraph block
    num  = p['number']
    head = p.get('heading_la', '')
    body = para_html(p['text'], p['part'], p['chapter'])

    html_parts.append(
        f'<div class="paragraph" id="para-{num}">'
        f'<span class="para-num">{num}.</span>'
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

from collections import defaultdict

secs_by_ch = defaultdict(list)
for s in sections_for_drawer:
    secs_by_ch[(s['part'], s['chapter'])].append(s)

fns_by_ch = defaultdict(list)
for fn in footnotes:
    fns_by_ch[(fn['part'], fn['chapter'])].append(fn)

# Map (part, chapter, fn_number) → (section, para_number) via first paragraph that cites it
import re as _re
fn_section: dict[tuple, int] = {}
fn_para:    dict[tuple, int] = {}
for p in paragraphs:
    refs = _re.findall(r'\((\d{1,3})\)', p['text'])
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

# ── page ──────────────────────────────────────────────────────────────────────

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: Georgia, serif;
    font-size: 1.2rem;
    line-height: 1.75;
    color: #1a1a1a;
    background: #faf9f7;
    max-width: 780px;
    margin-left: clamp(2rem, calc(50vw - 390px), 10rem);
    margin-right: auto;
    padding: 4rem 2rem 6rem;
}
h1, h2, h3, h4 { font-family: 'Palatino Linotype', Palatino, serif; }

/* ── sticky heading bar ── */
#sticky-bar {
    position: fixed;
    top: 0; left: 0; right: 0;
    z-index: 80;
    background: #faf9f7;
    border-bottom: 1px solid #ddd;
    /* left padding matches body margin-left (no body padding), so label aligns with body text */
    padding: .55rem clamp(2rem, calc(50vw - 390px + 2rem), 12rem) .55rem clamp(2rem, calc(50vw - 390px), 10rem);
    font-family: 'Palatino Linotype', Palatino, serif;
    font-size: 1.8rem;
    color: #333;
    display: flex;
    align-items: baseline;
    gap: .4rem;
    overflow: hidden;
}
#sticky-num {
    /* fills the body's 2rem left padding, sits in the gutter */
    width: 1.6rem;
    text-align: right;
    flex-shrink: 0;
    color: #aaa;
    font-size: .65em;
}
#sticky-label {
    flex: 1;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
h1.part-num      { font-size: 1rem; text-transform: uppercase; letter-spacing: .15em; color: #888; margin: 3rem 0 .25rem; }
h1.part-title    { font-size: 1.6rem; margin: 1.5rem 0 1rem; }
h2.chapter-num   { font-size: .9rem; text-transform: uppercase; letter-spacing: .15em; color: #888; margin: 2.5rem 0 .2rem; }
h3.chapter-title { font-size: 1.3rem; margin: 0 0 1rem; }
h4.section-title { font-size: 1rem; font-style: italic; color: #555; margin: 2rem 0 .75rem; }
.paragraph       { margin: 1.25rem 0; }
.para-num        { font-weight: bold; }
.heading-la      { color: #555; font-size: .95em; }
.paragraph p     { margin-top: .6rem; }
sup a            { color: #7a5c3a; text-decoration: none; font-size: .75em; }
sup a:hover      { text-decoration: underline; }

/* ── chapter scroll indicator ── */
#ch-indicator {
    position: fixed;
    left: 1.25rem;
    top: 50%;
    transform: translateY(-50%);
    display: flex;
    flex-direction: column;
    gap: 5px;
    z-index: 50;
}
.ch-part-gap { height: 10px; }
.ch-bar {
    width: 5px;
    display: flex;
    flex-direction: column;
    gap: 1px;
    cursor: pointer;
    transition: width .2s ease;
    overflow: hidden;
    border-radius: 3px;
}
.ch-bar:hover       { width: 10px; }
.ch-bar.part-active { width: 9px; }
.ch-bar.active      { width: 13px; }
.ch-seg {
    height: 6px;
    background: #ccc;
    flex-shrink: 0;
    transition: background .2s ease;
}
.ch-bar.active .ch-seg         { background: #b8941f; }
.ch-bar.active .ch-seg.cur-para { background: #5c3d0a; }
@media (max-width: 700px) {
    #ch-indicator { display: none; }
    body { margin-left: auto; }
    #sticky-bar { font-size: 1.1rem; }
    #sticky-num { display: none; }
}

/* ── footnote drawer ── */
#fn-drawer {
    position: fixed;
    top: 0; right: 0;
    width: 380px;
    height: 100vh;
    background: #f0ece4;
    border-left: 1px solid #ccc;
    transform: translateX(100%);
    transition: transform .3s ease;
    display: flex;
    z-index: 100;
}
#fn-drawer.open { transform: translateX(0); }
#fn-tab {
    position: absolute;
    left: -2rem;
    top: 50%;
    transform: translateY(-50%);
    writing-mode: vertical-rl;
    background: #f0ece4;
    border: 1px solid #ccc;
    border-right: none;
    padding: .6rem .4rem;
    cursor: pointer;
    font-family: Georgia, serif;
    font-size: .8rem;
    color: #555;
    letter-spacing: .05em;
    user-select: none;
    border-radius: 4px 0 0 4px;
}
#fn-tab:hover { color: #1a1a1a; }
#fn-content {
    overflow-y: auto;
    padding: 2rem 1.5rem;
    flex: 1;
}


@media (max-width: 900px) {
    #fn-drawer { width: 280px; }
}
#fn-content h2   { font-size: 1.1rem; margin-bottom: 1.25rem; }
.fn-group        { font-size: .75rem; text-transform: uppercase; letter-spacing: .1em; color: #888; margin: 1.5rem 0 .4rem; }
.fn-list         { list-style: none; padding-left: 0; font-size: 1rem; line-height: 1.55; }
.fn-item         { margin-bottom: .65rem; padding-left: 2rem; text-indent: -2rem; }
.fn-item p       { display: inline; }
.fn-num-link     { color: inherit; text-decoration: none; margin-right: .25rem; }
.fn-num-link:hover { color: #7a5c3a; text-decoration: underline; }
.fn-item.fn-active { background: #f7f4ef; margin-left: -1.5rem; margin-right: -1.5rem; padding-left: calc(2rem + 1.5rem); padding-right: 1.5rem; }
.fn-ch-link    { color: inherit; text-decoration: none; }
.fn-ch-link:hover { text-decoration: underline; }
.sec-nav-item  { margin: .6rem 0 .25rem .5rem; line-height: 1.25; }
.sec-nav-link  { color: #777; text-decoration: none; font-size: .85rem; font-style: italic; line-height: 1.25; }
.sec-nav-link:hover { color: #1a1a1a; text-decoration: underline; }

/* ── document title block ── */
.doc-title {
    text-align: center;
    margin: 4rem 0 4rem;
    color: #663300;
    font-family: Georgia, serif;
}
.doc-desc {
    font-size: 1rem;
    text-transform: uppercase;
    letter-spacing: .08em;
    line-height: 1.5;
    margin-bottom: .75rem;
}
.doc-name {
    font-size: 2rem;
    font-style: italic;
    font-weight: bold;
    margin-bottom: .75rem;
}
.doc-promulg {
    font-size: 1rem;
    text-transform: uppercase;
    letter-spacing: .05em;
    line-height: 1.5;
    margin: 0 auto;
    max-width: 16rem;
}
"""

import json
fn_drawer_html = '\n'.join(drawer_items)

# attach paragraph numbers to each chapter entry
ch_paras: dict[str, list[int]] = {}
for pnum, cid in para_ch_id.items():
    ch_paras.setdefault(cid, []).append(pnum)
for ch in indicator_chapters:
    ch['paras'] = ch_paras.get(ch['id'], [])

indicator_json = json.dumps(indicator_chapters)

page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Gaudium et Spes</title>
<style>{CSS}</style>
</head>
<body>
<div id="sticky-bar"><span id="sticky-num"></span><span id="sticky-label">Gaudium et Spes</span></div>
{title_block}
{''.join(html_parts)}

<nav id="ch-indicator"></nav>

<aside id="fn-drawer">
  <div id="fn-tab">Notes</div>
  <div id="fn-content">
    {fn_drawer_html}
  </div>
</aside>

<script>
  // ── sticky heading bar ──
  const stickyNum   = document.getElementById('sticky-num');
  const stickyLabel = document.getElementById('sticky-label');
  const stickyEls   = Array.from(document.querySelectorAll('[data-sticky]'));
  function updateSticky() {{
    let current = null;
    for (const el of stickyEls) {{
      if (el.getBoundingClientRect().top < 40) current = el;
      else break;
    }}
    if (current) {{
      stickyLabel.textContent = current.textContent;
      stickyNum.textContent   = current.dataset.chNum || '';
    }} else {{
      stickyLabel.textContent = 'Gaudium et Spes';
      stickyNum.textContent   = '';
    }}
  }}
  window.addEventListener('scroll', updateSticky, {{passive: true}});
  updateSticky();

  function scrollToEl(el, smooth) {{
    const barH = document.getElementById('sticky-bar').offsetHeight;
    const top = el.getBoundingClientRect().top + window.scrollY - barH - 8;
    window.scrollTo({{ top, behavior: smooth ? 'smooth' : 'instant' }});
    if (el.id) history.replaceState(null, '', '#' + el.id);
  }}

  // ── chapter indicator ──
  const chapters = {indicator_json};
  const nav = document.getElementById('ch-indicator');

  // build bars (skip spacer entries for bar array, but insert gap divs)
  const bars = [];
  chapters.forEach(ch => {{
    if (ch.spacer) {{
      const gap = document.createElement('div');
      gap.className = 'ch-part-gap';
      nav.appendChild(gap);
    }}
    const bar = document.createElement('div');
    bar.className = 'ch-bar';
    bar.title = ch.label;
    ch.paras.forEach(pn => {{
      const seg = document.createElement('div');
      seg.className = 'ch-seg';
      seg.dataset.para = pn;
      seg.addEventListener('click', e => {{
        e.stopPropagation();
        scrollToEl(document.getElementById('para-' + pn), true);
      }});
      bar.appendChild(seg);
    }});
    bar.addEventListener('click', () =>
      scrollToEl(document.getElementById(ch.id), true)
    );
    nav.appendChild(bar);
    bars.push(bar);
  }});

  // para → chapter index lookup
  const paraToChIdx = {{}};
  chapters.forEach((ch, i) => ch.paras.forEach(pn => paraToChIdx[pn] = i));

  // collect all para elements in order
  const paraEls = Array.from(document.querySelectorAll('.paragraph'));

  function updateIndicator() {{
    const threshold = window.innerHeight * 0.35;
    let curPara = paraEls[0]?.dataset?.para;
    for (const el of paraEls) {{
      if (el.getBoundingClientRect().top <= threshold) curPara = el.id.replace('para-', '');
      else break;
    }}
    const chIdx = paraToChIdx[curPara] ?? 0;
    const activePart = chapters[chIdx]?.part;
    bars.forEach((b, i) => {{
      const isActive = i === chIdx;
      b.classList.toggle('active', isActive);
      b.classList.toggle('part-active', !isActive && chapters[i].part === activePart);
      if (isActive) {{
        b.querySelectorAll('.ch-seg').forEach(s =>
          s.classList.toggle('cur-para', s.dataset.para == curPara)
        );
      }}
    }});
  }}
  window.addEventListener('scroll', updateIndicator, {{passive: true}});
  updateIndicator();

  // ── footnote drawer ──
  const drawer  = document.getElementById('fn-drawer');
  const tab     = document.getElementById('fn-tab');
  const content = document.getElementById('fn-content');

  tab.addEventListener('click', () => drawer.classList.toggle('open'));

  function selectFn(id) {{
    document.querySelectorAll('.fn-item.fn-active')
      .forEach(el => el.classList.remove('fn-active'));
    const target = document.getElementById(id);
    if (!target) return;
    target.classList.add('fn-active');
    const rect = target.getBoundingClientRect();
    const cRect = content.getBoundingClientRect();
    if (rect.top < cRect.top || rect.bottom > cRect.bottom) {{
      content.scrollTop += rect.top - cRect.top - content.clientHeight / 3;
    }}
  }}

  document.querySelectorAll('.fn-ch-link').forEach(a => {{
    a.addEventListener('click', e => {{
      e.preventDefault();
      const target = document.getElementById(a.getAttribute('href').slice(1));
      if (target) scrollToEl(target, true);
    }});
  }});

  document.querySelectorAll('.fn-num-link').forEach(a => {{
    a.addEventListener('click', e => {{
      e.preventDefault();
      const target = document.getElementById(a.getAttribute('href').slice(1));
      if (target) scrollToEl(target, true);
    }});
  }});

  document.querySelectorAll('.sec-nav-link').forEach(a => {{
    a.addEventListener('click', e => {{
      e.preventDefault();
      const target = document.getElementById(a.getAttribute('href').slice(1));
      if (target) scrollToEl(target, true);
    }});
  }});

  document.querySelectorAll('sup a').forEach(a => {{
    a.addEventListener('click', e => {{
      e.preventDefault();
      drawer.classList.add('open');
      selectFn(a.getAttribute('href').slice(1));
    }});
  }});
</script>
</body>
</html>
"""

with open('gaudium_et_spes.html', 'w', encoding='utf-8') as f:
    f.write(page)

print(f'Written gaudium_et_spes.html — {len(paragraphs)} paragraphs, {len(footnotes)} footnotes')
