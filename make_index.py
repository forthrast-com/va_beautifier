"""Render the flat GitHub Pages landing page from document TOML metadata."""

import datetime
from html import escape, unescape
import json
import re
import sys

from core import read_toml, title_case
from project import BUILD, DOWNLOADS, SITE


# Pontificates that have promulgated a doc in the catalogue. `start` is
# the pontificate-sort key; `honorific` and `display` carry editorial
# styling so encyclical bylines can be built purely from kind + pope.
# Add an entry when adding a doc under a new pope.
PONTIFICATES = {
    'Paul VI': {
        'start':     '1963-06-21',
        'honorific': 'of His Holiness',
        'display':   'Pope Paul VI',
    },
    'John Paul II': {
        'start':     '1978-10-16',
        'honorific': 'of His Holiness',
        'display':   'Pope John Paul II',
    },
    'Benedict XVI': {
        'start':     '2005-04-19',
        'honorific': 'of His Holiness',
        'display':   'Pope Benedict XVI',
    },
    'Francis': {
        'start':     '2013-03-13',
        'honorific': 'of the Holy Father',
        'display':   'Francis',
    },
    'Leo XIV': {
        'start':     '2025-05-08',
        'honorific': 'of His Holiness',
        'display':   'Pope Leo XIV',
    },
}


# Structured card metadata lives in each document TOML: `type`, plus either
# `subtitle` or `kind_long`. Adding a document should not require touching this
# renderer unless it introduces a new document category.

# Short label that appears tracked at the head of each tile.
TILE_KIND_LABEL = {
    'encyclical':           'Encyclical Letter',
    'apostolic_exhortation': 'Apostolic Exhortation',
    'council_constitution': 'Conciliar Constitution',
    'curia_note':           'Doctrinal Note',
    'commission_paper':     'Commission Paper',
}

# Canonical authority ranking, low = highest authority. Conciliar
# constitutions (ecumenical council, promulgated by the Pope) outrank a
# papal encyclical; a papal apostolic exhortation ranks just below an
# encyclical; a dicasterial doctrinal note exercises the Pope's authority
# without speaking in his voice; an ITC commission paper is explicitly
# advisory, not magisterial.
AUTHORITY_RANK = {
    'council_constitution':  1,
    'encyclical':            2,
    'apostolic_exhortation': 3,
    'curia_note':            4,
    'commission_paper':      5,
}


_TAG_RE = re.compile(r'<[^>]+>')
_MARKDOWN_LINK_RE = re.compile(r'\[([^\]]+)\]\([^)]+\)')
_FOOTNOTE_REF_RE = re.compile(r'\(\d{1,3}\)')
_TITLE_PREFIX_RE = re.compile(r'^(the |a |an )', re.IGNORECASE)
_WORD_RE = re.compile(r"[^\W_]+(?:[’'-][^\W_]+)*")

# Search aliases. If the blob (post-tag-strip, post-entity-decode,
# lowercased) contains the trigger substring, the alias terms get
# appended. Keeps 'Vatican II' searchable on the conciliar texts and
# the DDF's older names (CDF, Holy Office, Inquisition) searchable on
# anything currently bylined to the dicastery.
SEARCH_ALIASES = (
    ('second vatican council',
     'vatican ii vatican 2 second vatican'),
    ('dicastery for the doctrine of the faith',
     'cdf congregation for the doctrine of the faith holy office inquisition'),
)


def _formatted_date(iso_date):
    """Render '2026-05-15' as '15 May 2026'. Leaves an unparseable value
    alone so we never silently drop information."""
    if not iso_date:
        return ''
    try:
        d = datetime.date.fromisoformat(iso_date)
    except ValueError:
        return iso_date
    return f'{d.day} {d.strftime("%B")} {d.year}'


def _title_sort_key(name):
    """Strip a leading article so 'A Note on…' sorts under N, not A."""
    stripped = _TITLE_PREFIX_RE.sub('', name.strip())
    return stripped.lower()


def _body_word_count(data):
    """Count body words from paragraph text only.

    This deliberately excludes footnotes, front matter, signatures, and
    appendices: catalogue size is a rough reading-body measure, not a
    complete edition byte count.
    """
    text = '\n'.join(
        para.get('text', '')
        for para in data.get('paragraphs', ())
    )
    text = _MARKDOWN_LINK_RE.sub(r'\1', text)
    text = _FOOTNOTE_REF_RE.sub(' ', text)
    text = _TAG_RE.sub('', text)
    return len(_WORD_RE.findall(text))


def _card_fields(slug, data):
    """Collect all the tile-level fields for one document into one dict.

    Each tile renders the same shape (kind, title, subtitle, byline,
    date) so the layout can stay uniform across encyclicals, conciliar
    constitutions, dicastery notes, and theological-commission papers.
    The bolded element in each byline is the human-or-body that the
    rendered card most wants the eye to land on."""
    kind_type = data.get('type', '')
    subtitle = data.get('subtitle', '')
    byline = ''

    if kind_type == 'council_constitution':
        subtitle = data.get('kind_long', '')
    issued_by = data.get('issued_by', '')
    pont_name = data.get('pontificate', '')
    pont = PONTIFICATES.get(pont_name, {})

    # Byline shape is purely a function of `kind_type` + `PONTIFICATES`:
    #   encyclical,
    #   apostolic_exhortation → '{honorific} <strong>{pope}</strong>'
    #   council_constitution  → 'of the <strong>{body}</strong>,
    #                            promulgated by {pope.display}'
    #   curia_note,
    #   commission_paper      → '<strong>{body}</strong>'
    # No per-doc editorial overrides — pope styling lives in PONTIFICATES,
    # body name comes from the TOML's `issued_by` field.
    if kind_type in ('encyclical', 'apostolic_exhortation') and pont:
        byline = f'{pont["honorific"]} <strong>{escape(pont["display"])}</strong>'
    elif kind_type == 'council_constitution' and issued_by:
        byline = f'of the <strong>{escape(issued_by)}</strong>'
        if pont.get('display'):
            byline += f', promulgated by {escape(pont["display"])}'
    elif issued_by:
        byline = f'<strong>{escape(issued_by)}</strong>'
    else:
        # No issued_by — flow the TOML's desc / desc_post fallback.
        joined = ' '.join(
            line.strip()
            for part in (data.get('desc', ''), data.get('desc_post', ''))
            for line in part.splitlines()
            if line.strip()
        )
        byline = escape(title_case(joined)) if joined else ''

    return {
        'name':            data['name'],
        'kind_type':       kind_type,
        'kind_label':      TILE_KIND_LABEL.get(kind_type, ''),
        'subtitle':        subtitle,
        'byline':          byline,
        'date':            _formatted_date(data.get('date', '')),
        'iso_date':        data.get('date', ''),
        'hue':             data.get('hue', 42),
        'source_url':      data.get('source_url', ''),
        'pontificate':     pont_name,
        'pontif_name':     pont_name,
        'pontif_start':    pont.get('start', ''),
        'title_key':       _title_sort_key(data['name']),
        'word_count':      _body_word_count(data),
    }


# Ordered: which sort field is active controls which label appears
# next to "Sorting by". The two direction labels read 'default' first
# (what you get when reverse is off) then 'reversed'. Only date
# and size default to descending; the rest default ascending (so name starts
# at A, pope starts at Paul VI, and class starts at the conciliar
# constitutions).
SORT_FIELDS = (
    ('date',  'Date',  'most recent',        'oldest first'),
    ('name',  'Name',  'A-Z',                'Z-A'),
    ('pope',  'Pope',  'earliest',           'most recent'),
    ('class', 'Class', 'highest authority',  'lowest authority'),
    ('size',  'Size',  'longest first',      'shortest first'),
)

REVERSE_ICON_SVG = (
    '<svg class="reverse-icon" viewBox="0 0 16 16" aria-hidden="true" '
    'focusable="false">'
    '<path d="M4 2v10.2L1.7 9.9.6 11l4.2 4.2 4.2-4.2L7.9 9.9 5.6 12.2V2H4z" />'
    '<path d="M12 14V3.8l2.3 2.3 1.1-1.1L11.2.8 7 5l1.1 1.1L10.4 3.8V14H12z" />'
    '</svg>'
)


def file_size(path):
    """Present a compact download size for an artefact, if it was built."""
    if not path.exists():
        return ''
    size = path.stat().st_size
    for unit in ('KB', 'MB', 'GB'):
        size /= 1024
        if size < 1024 or unit == 'GB':
            return f'{size:.0f} {unit}'
    return ''


def render_downloads(slug):
    """Primary download controls, including a no-JS PDF size menu."""
    a6_size = file_size(DOWNLOADS / f'{slug}-a6.pdf')
    a5_size = file_size(DOWNLOADS / f'{slug}-a5.pdf')
    a4_size = file_size(DOWNLOADS / f'{slug}-a4.pdf')
    epub_size = file_size(DOWNLOADS / f'{slug}.epub')

    pdf_html = ''
    if a4_size or a5_size or a6_size:
        menu_parts = []
        if a4_size:
            menu_parts.append(
                f'<a href="downloads/{slug}-a4.pdf">'
                f'<span>A4 (Printer)</span><small>{a4_size}</small></a>'
            )
        if a5_size:
            menu_parts.append(
                f'<a href="downloads/{slug}-a5.pdf">'
                f'<span>A5 (Reader)</span><small>{a5_size}</small></a>'
            )
        if a6_size:
            menu_parts.append(
                f'<a href="downloads/{slug}-a6.pdf">'
                f'<span>A6 (Booklet)</span><small>{a6_size}</small></a>'
            )
        pdf_html = (
            '<details class="pdf-control pdf-menu">'
            '<summary class="action-button" aria-label="Choose PDF edition">'
            '<span class="dl-name">PDF</span>'
            '<span class="pdf-chevron" aria-hidden="true"></span></summary>'
            f'<div class="pdf-options">{"".join(menu_parts)}</div>'
            '</details>'
        )
    epub_html = ''
    if epub_size:
        epub_html = (
            f'<a class="action-button" href="downloads/{slug}.epub">'
            f'<span class="dl-name">EPUB</span>'
            f'<span class="dl-size">{epub_size}</span></a>'
        )

    return pdf_html, epub_html


def _search_blob(f):
    """Lowercase, tag-stripped, entity-decoded haystack of everything a
    user might type. Entities go through `unescape` so `&amp;` in the
    byline doesn't haunt the matcher; SEARCH_ALIASES appends historical
    and shorthand names for bodies the document is tied to."""
    parts = (
        f['name'],
        f['subtitle'],
        unescape(_TAG_RE.sub('', f['byline'])),
        f['kind_label'],
        f['pontif_name'],
    )
    blob = ' '.join(p for p in parts if p).lower()
    extras = [aliases for trigger, aliases in SEARCH_ALIASES if trigger in blob]
    if extras:
        blob = blob + ' ' + ' '.join(extras)
    return blob


def render_card(slug, f):
    pdf_html, epub_html = render_downloads(slug)

    subtitle_html = (
        f'<p class="subtitle">{escape(f["subtitle"])}</p>'
        if f['subtitle'] else ''
    )
    date_html = (
        f'<time class="date" datetime="{escape(f["iso_date"])}">'
        f'{escape(f["date"])}</time>'
        if f['date'] else ''
    )
    kind_html = (
        f'<span class="kind">{escape(f["kind_label"])}</span>'
        if f['kind_label'] else ''
    )

    source_html = ''
    if f['source_url']:
        source_html = (
            f'<a class="action-button source-link" href="{escape(f["source_url"], quote=True)}"'
            ' target="_blank" rel="noopener">'
            '<span class="dl-name">Vatican source</span>'
            '<span aria-hidden="true">↗</span></a>'
        )

    data_attrs = (
        f'data-date="{escape(f["iso_date"], quote=True)}" '
        f'data-pontificate="{escape(f["pontificate"], quote=True)}" '
        f'data-pontif-name="{escape(f["pontif_name"], quote=True)}" '
        f'data-pontif-start="{escape(f["pontif_start"], quote=True)}" '
        f'data-type="{escape(f["kind_type"], quote=True)}" '
        f'data-type-label="{escape(f["kind_label"], quote=True)}" '
        f'data-authority-rank="{AUTHORITY_RANK.get(f["kind_type"], 99)}" '
        f'data-title-key="{escape(f["title_key"], quote=True)}" '
        f'data-word-count="{f["word_count"]}" '
        f'data-search="{escape(_search_blob(f), quote=True)}"'
    )

    return f'''<article class="edition" {data_attrs} style="--hue: {f["hue"]}">
  <header class="edition-head">
    {kind_html}
    {date_html}
  </header>

  <a class="edition-link" href="{slug}.html">
    <h2 class="title">{escape(f["name"])}</h2>
    {subtitle_html}
    <p class="byline">{f["byline"]}</p>
  </a>

  <div class="actions">
    <div class="action-group">
      <span class="action-label">Read</span>
      <div class="action-row">
        <a class="action-button reader-button" href="{slug}.html">
          <span class="dl-name">Web reader</span>
          <span aria-hidden="true">→</span>
        </a>
        {source_html}
      </div>
    </div>
    <div class="action-group">
      <span class="action-label">Download</span>
      <div class="action-row">
        <div class="downloads-row">{epub_html}</div>
        <div class="downloads-row">{pdf_html}</div>
      </div>
    </div>
  </div>
</article>'''


def _sort_options_html():
    """Render the row of sort-field buttons. The first is pre-marked
    active; JS keeps it in sync after that."""
    buttons = []
    for i, (key, label, _asc_dir, _desc_dir) in enumerate(SORT_FIELDS):
        active = ' is-active' if i == 0 else ''
        pressed = 'true' if i == 0 else 'false'
        buttons.append(
            f'<button type="button" class="sort-option{active}" '
            f'data-sort="{key}" aria-pressed="{pressed}">{label}</button>'
        )
    return ''.join(buttons)


def _sort_field_meta_json():
    """Direction labels per sort field, surfaced to JS so the 'Sorting by'
    caption stays accurate without duplicating the table in two places."""
    return json.dumps({
        key: {
            'label':        label,
            'default_dir':  default_dir,
            'reversed_dir': reversed_dir,
        }
        for key, label, default_dir, reversed_dir in SORT_FIELDS
    })


def missing_tile_meta(docs):
    """Slugs whose TOML lacks tile metadata.

    Missing metadata is allowed so queued/local experiments can still render,
    but first-class catalogue documents should carry it beside their document
    metadata in the extractor.
    """
    missing = []
    for slug, data in docs.items():
        kind_type = data.get('type', '')
        if not kind_type:
            missing.append(slug)
        elif kind_type == 'council_constitution' and not data.get('kind_long'):
            missing.append(slug)
        elif kind_type != 'council_constitution' and not data.get('subtitle'):
            missing.append(slug)
    return missing


def main():
    slugs = sys.argv[1:]
    if not slugs:
        raise SystemExit('usage: python make_index.py DOC [DOC ...]')

    docs = {slug: read_toml(BUILD / f'{slug}.toml') for slug in slugs}
    unstyled = missing_tile_meta(docs)
    if unstyled:
        print(
            f'make_index.py: warning: no tile metadata in TOML for '
            f'{", ".join(unstyled)} — tile renders without kind/subtitle/'
            f'byline styling',
            file=sys.stderr,
        )

    # Server-side default: reverse chronological by promulgation date. JS
    # picks up the same default when it boots, so first paint matches.
    fields_by_slug = {slug: _card_fields(slug, docs[slug]) for slug in slugs}
    slugs = sorted(
        slugs,
        key=lambda s: fields_by_slug[s]['iso_date'],
        reverse=True,
    )

    cards = '\n'.join(render_card(slug, fields_by_slug[slug]) for slug in slugs)
    page = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="icon" href="favicon.ico" type="image/x-icon">
<title>The Circulars | Vatican Documents</title>
<style>
:root {{
  color-scheme: light dark;
  /* Surface */
  --bg:           #f7f4ec;
  --paper:        #fcfaf3;
  --paper-edge:   #e8e1cf;
  --rule:         #d8d0bb;
  --rule-soft:    #ebe5d4;
  /* Ink */
  --ink:          #1f1b13;
  --ink-dim:      #6a6253;
  --ink-fainter:  #948a76;
  /* Display fallback hue when the per-tile --hue isn't set */
  --hue: 42;
  --accent:       hsl(calc(var(--hue) -  6),  44%, 30%);
  --accent-soft:  hsl(calc(var(--hue) +  2),  32%, 56%);
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    --bg:           #14120e;
    --paper:        #1d1a14;
    --paper-edge:   #2a261d;
    --rule:         #3a3528;
    --rule-soft:    #2b2620;
    --ink:          #ece5d3;
    --ink-dim:      #b6ad95;
    --ink-fainter:  #807761;
    --accent:       hsl(calc(var(--hue) -  4), 42%, 70%);
    --accent-soft:  hsl(calc(var(--hue) +  2), 30%, 50%);
  }}
}}

* {{ box-sizing: border-box; }}
html, body {{ margin: 0; padding: 0; }}
body {{
  background: var(--bg);
  color: var(--ink);
  font-family: Georgia, 'Times New Roman', serif;
  font-feature-settings: "onum" 1, "lnum" 0;   /* oldstyle figures */
  line-height: 1.55;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}}

::selection {{ background: var(--accent); color: var(--paper); }}

main {{
  width: min(92rem, calc(100% - 2.5rem));
  margin: 0 auto;
  padding: clamp(2rem, 6vh, 4rem) 0 4rem;
}}

/* ── Masthead ────────────────────────────────────────────────────────── */
.masthead {{
  border-bottom: 1px solid var(--rule);
  padding-bottom: clamp(1.6rem, 4vh, 2.6rem);
  margin-bottom: clamp(2rem, 5vh, 3.4rem);
}}
.brand {{
  color: var(--ink-fainter);
  font-family: ui-monospace, "SF Mono", Menlo, monospace;
  font-size: .72rem;
  letter-spacing: .18em;
  text-transform: uppercase;
  margin: 0 0 1.1rem;
}}
.brand b {{ font-weight: 600; color: var(--ink-dim); letter-spacing: .15em; }}
h1 {{
  font-size: clamp(2.6rem, 6.4vw, 4.4rem);
  font-style: italic;
  font-weight: normal;
  line-height: 1.04;
  letter-spacing: -0.005em;
  margin: 0 0 1.1rem;
}}
/* Each clause is a no-break unit, so the only legal break point is the
   space between them — i.e. after the comma. If the viewport is wide
   enough for both to share a line, they do. */
h1 .clause {{ white-space: nowrap; }}
.intro {{
  max-width: 38rem;
  color: var(--ink-dim);
  font-size: 1.06rem;
  line-height: 1.6;
  margin: 0;
}}
.intro a {{ color: inherit; text-decoration-color: var(--ink-fainter); }}

/* ── Filter / sort controls ──────────────────────────────────────────── */
.controls {{
  display: grid;
  gap: .9rem;
  margin: 0 0 1.6rem;
  padding-bottom: 1.2rem;
  border-bottom: 1px solid var(--rule);
}}
.search-row {{
  position: relative;
}}
.search-icon {{
  position: absolute;
  left: .8rem;
  top: 50%;
  transform: translateY(-50%);
  width: 1rem;
  height: 1rem;
  color: var(--ink-fainter);
  pointer-events: none;
}}
.search-input {{
  width: 100%;
  padding: .55rem .8rem .55rem 2.3rem;
  background: var(--paper);
  border: 1px solid var(--rule);
  border-radius: 2px;
  color: var(--ink);
  font-family: Georgia, 'Times New Roman', serif;
  font-size: 1rem;
  line-height: 1.4;
  transition: border-color .15s ease, box-shadow .15s ease;
}}
.search-input::placeholder {{
  color: var(--ink-fainter);
  font-style: italic;
}}
.search-input:focus {{
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--accent) 14%, transparent);
}}

.sort-bar {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
  color: var(--ink-fainter);
  font-family: ui-monospace, "SF Mono", Menlo, monospace;
  font-size: .72rem;
  letter-spacing: .12em;
  text-transform: uppercase;
}}
.sort-label {{
  display: inline-flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: .35rem .55rem;
}}
.sort-label small {{ color: var(--ink-dim); font-size: inherit; }}
.sort-label .sort-current {{ color: var(--ink); font-weight: 600; }}
.sort-label .sort-direction {{
  color: var(--ink-fainter);
  text-transform: none;
  letter-spacing: .04em;
  font-style: italic;
}}

.sort-options {{
  display: inline-flex;
  flex-wrap: wrap;
  gap: .35rem;
  align-items: center;
}}
.sort-option {{
  background: transparent;
  border: 1px solid var(--rule);
  border-radius: 2px;
  color: var(--ink-fainter);
  cursor: pointer;
  font: inherit;
  letter-spacing: inherit;
  text-transform: inherit;
  padding: .28rem .55rem;
  transition: border-color .15s ease, color .15s ease, background .15s ease;
}}
.sort-option:hover {{
  border-color: var(--accent-soft);
  color: var(--ink-dim);
}}
.sort-option.is-active {{
  border-color: var(--accent);
  color: var(--accent);
  background: color-mix(in srgb, var(--accent) 6%, var(--paper));
}}
.sort-option:focus-visible {{
  outline: 2px solid var(--accent);
  outline-offset: 1px;
}}

.sort-reverse {{
  background: transparent;
  border: 1px solid var(--rule);
  border-radius: 2px;
  color: var(--ink-fainter);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: .28rem .35rem;
  transition: border-color .15s ease, color .15s ease, background .15s ease;
}}
.sort-reverse:hover {{
  border-color: var(--accent-soft);
  color: var(--ink-dim);
}}
.sort-reverse.is-reversed {{
  border-color: var(--accent);
  color: var(--accent);
  background: color-mix(in srgb, var(--accent) 6%, var(--paper));
}}
.sort-reverse:focus-visible {{
  outline: 2px solid var(--accent);
  outline-offset: 1px;
}}
.reverse-icon {{
  width: .85rem;
  height: .85rem;
  fill: currentColor;
}}
.sort-reverse.is-reversed .reverse-icon {{
  transform: scaleY(-1);
}}

/* Hide controls when JS isn't available; the cards still render in
   reverse-chronological order so the page stays useful. */
.no-js .controls {{ display: none; }}

.empty-state {{
  display: none;
  padding: 2.2rem 1rem;
  text-align: center;
  color: var(--ink-dim);
  border: 1px dashed var(--rule);
  border-radius: 2px;
  font-style: italic;
}}
.editions.is-empty + .empty-state {{ display: block; }}

/* ── Editions grid ───────────────────────────────────────────────────── */
.editions {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(27rem, 100%), 1fr));
  gap: 1.4rem;
}}

.group-heading {{
  grid-column: 1 / -1;
  margin: 1rem 0 .1rem;
  padding-bottom: .35rem;
  border-bottom: 1px solid var(--rule);
  color: var(--accent);
  font-family: ui-monospace, "SF Mono", Menlo, monospace;
  font-size: .72rem;
  font-weight: 600;
  letter-spacing: .18em;
  text-transform: uppercase;
  animation: heading-drop .28s ease-out both;
}}
.group-heading:first-child {{ margin-top: 0; }}
.group-heading[hidden] {{ display: none; }}
@keyframes heading-drop {{
  from {{ opacity: 0; transform: translateY(-.3rem); }}
  to   {{ opacity: 1; transform: none; }}
}}

.edition {{
  position: relative;
  background: var(--paper);
  border: 1px solid var(--paper-edge);
  padding: 1.6rem 1.7rem 1.4rem;
  display: flex;
  flex-direction: column;
  min-height: 22rem;
  box-shadow: 0 1px 0 0 var(--rule-soft);
  /* FLIP-reorder transition. Spring-y curve + per-card stagger (set
     inline from JS) makes a sort change feel goofily mechanical
     rather than instant. Slightly longer than feels strictly
     necessary so long-distance cards don't whip too cartoonishly. */
  transition: transform .58s cubic-bezier(.34, 1.45, .64, 1),
              box-shadow .25s ease;
}}
/* Flat accent bar on the left edge. Lives as a pseudo so its corners
   stay square — a 5px `border-left` against a 1px top/bottom would
   miter at 45° and chamfer the join. The -1px overhangs put the bar
   flush with the card's outer rectangle, covering the paper-edge
   border on those three sides. */
.edition::before {{
  content: '';
  position: absolute;
  top: -1px;
  bottom: -1px;
  left: -1px;
  width: 5px;
  background: hsl(calc(var(--hue) - 4), 42%, 40%);
  pointer-events: none;
}}
@media (prefers-color-scheme: dark) {{
  .edition::before {{
    background: hsl(calc(var(--hue) - 4), 42%, 56%);
  }}
}}
.edition[hidden] {{ display: none; }}
/* `will-change: transform` only during a shuffle. Declaring it at
   rest would make every card its own stacking context, which traps
   the PDF dropdown (`z-index: 2`) inside the card and lets sibling
   cards paint over it. */
.editions.is-shuffling .edition {{
  will-change: transform;
  box-shadow: 0 6px 18px color-mix(in srgb, var(--ink) 14%, transparent),
              0 1px 0 0 var(--rule-soft);
}}
.edition-head {{
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 1rem;
  margin: 0 0 1.2rem;
  font-family: ui-monospace, "SF Mono", Menlo, monospace;
  font-size: .68rem;
  letter-spacing: .14em;
  text-transform: uppercase;
}}
.edition .kind {{ color: var(--ink-dim); }}
.edition .date {{ color: var(--ink-fainter); font-variant-numeric: lining-nums tabular-nums; white-space: nowrap; }}

.edition-link {{
  color: inherit;
  text-decoration: none;
  display: block;
}}
.edition .title {{
  font-size: clamp(1.65rem, 2.4vw, 2rem);
  font-style: italic;
  font-weight: normal;
  line-height: 1.1;
  letter-spacing: -0.005em;
  margin: 0 0 .55rem;
  color: var(--accent);
}}
.edition-link:hover .title {{ text-decoration: underline; text-decoration-thickness: 1px; text-underline-offset: 3px; }}

.edition .subtitle {{
  font-size: .98rem;
  line-height: 1.45;
  color: var(--ink);
  margin: 0 0 .7rem;
}}
.edition .byline {{
  font-size: .9rem;
  line-height: 1.5;
  color: var(--ink-dim);
  margin: 0;
}}
.edition .byline strong {{ font-weight: 600; color: var(--ink); }}
.edition .signers {{
  display: inline-block;
  margin-top: .15rem;
  font-style: italic;
  color: var(--ink-dim);
}}

/* ── Actions (CTA + downloads) ───────────────────────────────────────── */
.actions {{
  margin-top: auto;
  padding-top: 1.4rem;
  border-top: 1px solid var(--rule-soft);
  flex: 0 0 auto;
  display: grid;
  gap: .85rem;
}}
.action-group {{
  display: grid;
  grid-template-columns: 4.7rem minmax(0, 1fr);
  gap: .65rem;
  align-items: center;
}}
.action-label {{
  justify-self: start;
  text-align: left;
  color: var(--ink-fainter);
  font-family: ui-monospace, "SF Mono", Menlo, monospace;
  font-size: .68rem;
  font-weight: 600;
  letter-spacing: .15em;
  line-height: 1;
  text-transform: uppercase;
}}
.action-row {{
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: .55rem;
}}
.downloads-row {{
  min-width: 0;
}}

.dl-primary,
.action-button {{
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
  gap: .4rem;
  padding: .25rem .65rem;
  border: 1px solid var(--rule);
  border-radius: 2px;
  background: var(--paper);
  color: var(--accent);
  font-family: ui-monospace, "SF Mono", Menlo, monospace;
  font-size: .72rem;
  letter-spacing: .12em;
  text-transform: uppercase;
  text-decoration: none;
  transition: border-color .15s ease, background .15s ease;
  height: 2.2rem;
  min-width: 0;
  white-space: nowrap;
}}
.action-button {{
  width: 100%;
}}
.action-button > [aria-hidden="true"] {{
  flex: 0 0 auto;
  margin-left: auto;
}}
.dl-primary:hover,
.action-button:hover {{
  border-color: var(--accent);
  background: hsl(calc(var(--hue) - 4), 42%, 96%);
}}
@media (prefers-color-scheme: dark) {{
  .dl-primary:hover,
  .action-button:hover {{
    background: hsl(calc(var(--hue) - 4), 18%, 18%);
  }}
}}
.dl-name {{ font-weight: 600; }}
.dl-detail {{
  color: var(--ink-dim);
  font-weight: normal;
  letter-spacing: .06em;
  text-transform: none;
}}
.dl-size {{
  color: var(--ink-fainter);
  font-weight: normal;
  letter-spacing: .08em;
  text-transform: none;
}}

.pdf-control {{
  position: relative;
  display: block;
  width: 100%;
}}

@media (max-width: 38rem) {{
  .action-group {{
    grid-template-columns: 1fr;
    gap: .5rem;
  }}
  .action-label {{
    padding-top: 0;
  }}
  .action-row {{
    grid-template-columns: 1fr;
  }}
}}
.pdf-menu summary {{
  width: 100%;
  cursor: pointer;
  list-style: none;
  user-select: none;
}}
.pdf-chevron {{
  width: .52rem;
  height: .52rem;
  border-right: 1.5px solid currentColor;
  border-bottom: 1.5px solid currentColor;
  transform: translateY(-.14rem) rotate(45deg);
}}
.pdf-menu summary::-webkit-details-marker {{ display: none; }}
.pdf-menu summary:hover,
.pdf-menu[open] summary {{
  border-color: var(--accent);
  background: hsl(calc(var(--hue) - 4), 42%, 96%);
}}
.pdf-options {{
  position: absolute;
  z-index: 2;
  right: 0;
  top: 100%;
  width: 100%;
  padding: .3rem;
  background: var(--paper);
  border: 1px solid var(--rule);
  border-radius: 2px;
  box-shadow: 0 .35rem 1rem color-mix(in srgb, var(--ink) 12%, transparent);
  /* Parent grid: a single track for labels, one for sizes. The
     anchors below use `grid-template-columns: subgrid` so every row
     inherits this same pair of tracks — sizes get a shared right
     gutter even when one is '9 KB' and the next is '1.2 MB'. */
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
}}
.pdf-options a {{
  display: grid;
  grid-column: 1 / -1;
  grid-template-columns: subgrid;
  column-gap: .8rem;
  align-items: baseline;
  padding: .45rem;
  color: var(--ink-dim);
  font-family: ui-monospace, "SF Mono", Menlo, monospace;
  font-size: .72rem;
  text-decoration: none;
}}
.pdf-options span {{
  white-space: nowrap;
}}
.pdf-options a:hover {{
  color: var(--accent);
  background: var(--rule-soft);
}}
.pdf-options small {{
  color: var(--ink-fainter);
  font-size: inherit;
  white-space: nowrap;
  text-align: right;
  font-variant-numeric: tabular-nums;
}}
@media (prefers-color-scheme: dark) {{
  .pdf-menu summary:hover,
  .pdf-menu[open] summary {{
    background: hsl(calc(var(--hue) - 4), 18%, 18%);
  }}
}}

/* ── Footer ──────────────────────────────────────────────────────────── */
footer {{
  border-top: 1px solid var(--rule);
  margin-top: clamp(3rem, 8vh, 5rem);
  padding-top: 1.4rem;
  color: var(--ink-dim);
  font-size: .88rem;
  line-height: 1.7;
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  flex-wrap: wrap;
  gap: 1rem 2rem;
}}
footer a {{
  color: inherit;
  text-decoration-color: var(--ink-fainter);
}}
footer a:hover {{ color: var(--accent); text-decoration-color: var(--accent); }}
.contacts {{
  display: grid;
  gap: .15rem;
  font-family: ui-monospace, "SF Mono", Menlo, monospace;
  font-size: .78rem;
  letter-spacing: .04em;
}}
.contacts span {{ color: var(--ink-fainter); text-transform: uppercase; letter-spacing: .15em; font-size: .68rem; margin-right: .6rem; }}
.attribution {{ text-align: right; font-size: .76rem; opacity: .75; font-style: italic; }}

/* ── Motion preferences ─────────────────────────────────────────────── */
@media (prefers-reduced-motion: reduce) {{
  *, *::before, *::after {{
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }}
}}
</style>
</head>
<body class="no-js">
<main>
  <header class="masthead">
    <p class="brand"><b>The&nbsp;Circulars</b> · vatican.va, retypeset</p>
    <h1><span class="clause">Vatican documents,</span> <span class="clause">set for reading.</span></h1>
    <p class="intro">Reading editions of papal and conciliar texts, drawn from the
    canonical HTML on <a href="https://www.vatican.va" target="_blank" rel="noopener">vatican.va</a>
    and run through templated extractors into a web reader, a typeset PDF,
    and an EPUB. Source on <a href="https://github.com/forthrast-com/va_beautifier" target="_blank" rel="noopener">GitHub</a>.</p>
  </header>

  <form class="controls" role="search" aria-label="Filter and sort editions"
        onsubmit="return false">
    <div class="search-row">
      <svg class="search-icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false">
        <circle cx="7" cy="7" r="4.5" fill="none" stroke="currentColor" stroke-width="1.4"/>
        <line x1="10.5" y1="10.5" x2="14" y2="14" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>
      </svg>
      <input class="search-input" type="search" id="filter-input"
             placeholder="Filter by title, pope, body, or kind…"
             aria-label="Filter documents" autocomplete="off">
    </div>
    <div class="sort-bar" aria-label="Sort controls">
      <span class="sort-label">
        <small>Sorting by</small>
        <span class="sort-current">Date</span>
        <span class="sort-direction">— most recent</span>
      </span>
      <div class="sort-options" role="group" aria-label="Sort field">
        {_sort_options_html()}
        <button type="button" class="sort-reverse" aria-pressed="false"
                aria-label="Reverse sort order" title="Reverse order">
          {REVERSE_ICON_SVG}
        </button>
      </div>
    </div>
  </form>

  <section class="editions" aria-label="Available documents">
{cards}
  </section>
  <p class="empty-state" role="status">No editions match that filter.</p>

  <footer>
    <div class="contacts">
      <div><span>email</span><a href="mailto:me@forthrast.com">me@forthrast.com</a></div>
      <div><span>bsky</span><a href="https://bsky.app/profile/forthrast.com" target="_blank" rel="noopener">@forthrast.com</a></div>
      <div><span>code</span><a href="https://github.com/forthrast-com/va_beautifier" target="_blank" rel="noopener">@forthrast-com</a></div>
    </div>
    <div class="attribution">made with claude and codex ^•^</div>
  </footer>
</main>
<script>
(function() {{
  document.body.classList.remove('no-js');

  var SORT_META = {_sort_field_meta_json()};
  var LEGACY_SORTS = {{ title: 'name', pontificate: 'pope', authority: 'class' }};
  var STORE_KEY = 'circulars:sort:v2';

  var grid     = document.querySelector('.editions');
  var input    = document.getElementById('filter-input');
  var options  = Array.prototype.slice.call(document.querySelectorAll('.sort-option'));
  var reverse  = document.querySelector('.sort-reverse');
  var current  = document.querySelector('.sort-current');
  var dirLabel = document.querySelector('.sort-direction');
  var cards    = Array.prototype.slice.call(grid.querySelectorAll('.edition'));

  // Pull each card's sort handles up-front so we're not parsing data
  // attributes on every reorder.
  var rows = cards.map(function(el) {{
    return {{
      el:         el,
      date:       el.dataset.date || '',
      pontif:     el.dataset.pontifStart || '',
      pontifName: el.dataset.pontifName || '',
      type:       el.dataset.typeLabel || '',
      authority:  parseInt(el.dataset.authorityRank, 10) || 99,
      name:       el.dataset.titleKey || '',
      wordCount:  parseInt(el.dataset.wordCount, 10) || 0,
      search:     el.dataset.search || '',
    }};
  }});

  // Which sorts get group headings. Date/name/size are continuous
  // orderings where headings would be noise; pope and class
  // are the buckets the user scans by, so they get a tracked-caps
  // label (pope name, kind label).
  var GROUPING_KEY = {{
    pope:  function(r) {{ return r.pontifName; }},
    class: function(r) {{ return r.type; }},
  }};

  var state = {{ sort: 'date', reversed: false }};
  var REDUCED_MOTION = !!(window.matchMedia &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  var shuffleTimer = null;

  try {{
    var stored = JSON.parse(localStorage.getItem(STORE_KEY) || 'null');
    var storedSort = stored && (LEGACY_SORTS[stored.sort] || stored.sort);
    if (stored && SORT_META[storedSort]) {{
      state.sort = storedSort;
      state.reversed = !!stored.reversed;
    }}
  }} catch (e) {{ /* ignore corrupt prefs */ }}

  // FLIP reorder: capture each visible child's rect, mutate the DOM,
  // then translate every moved card to its old slot and let the CSS
  // transition spring it back. A small per-card stagger turns the
  // batch into a cascade instead of a synchronised whoosh.
  function animateReorder(mutate) {{
    if (REDUCED_MOTION || typeof grid.children[0] === 'undefined') {{
      mutate();
      return;
    }}
    var children = Array.prototype.slice.call(grid.children);
    var firstRects = [];
    children.forEach(function(el) {{
      // Reset leftover inline transition state before measuring so a
      // mid-flight stagger delay doesn't poison the next pass.
      el.style.transition = '';
      el.style.transitionDelay = '';
      el.style.transform = '';
      if (!el.hidden) firstRects.push({{ el: el, rect: el.getBoundingClientRect() }});
    }});

    mutate();

    var moved = [];
    firstRects.forEach(function(rec) {{
      if (!rec.el.isConnected || rec.el.hidden) return;
      var last = rec.el.getBoundingClientRect();
      var dx = rec.rect.left - last.left;
      var dy = rec.rect.top - last.top;
      if (Math.abs(dx) < 0.5 && Math.abs(dy) < 0.5) return;
      rec.el.style.transition = 'none';
      rec.el.style.transform = 'translate(' + dx + 'px, ' + dy + 'px)';
      moved.push(rec.el);
    }});
    if (!moved.length) return;

    grid.classList.add('is-shuffling');
    if (shuffleTimer) clearTimeout(shuffleTimer);

    requestAnimationFrame(function() {{
      requestAnimationFrame(function() {{
        moved.forEach(function(el, i) {{
          el.style.transition = '';
          el.style.transitionDelay = Math.min(i * 22, 220) + 'ms';
          el.style.transform = '';
        }});
        shuffleTimer = setTimeout(function() {{
          grid.classList.remove('is-shuffling');
          moved.forEach(function(el) {{
            el.style.transitionDelay = '';
          }});
          shuffleTimer = null;
        }}, 1100);
      }});
    }});
  }}

  function compare(a, b) {{
    var sort = state.sort;
    if (sort === 'date')  return cmp(a.date, b.date);
    if (sort === 'name')  return cmp(a.name, b.name);
    if (sort === 'pope')  return cmp(a.pontif, b.pontif) || cmp(a.name, b.name);
    if (sort === 'class') return cmp(a.authority, b.authority) || cmp(a.name, b.name);
    if (sort === 'size')  return cmp(a.wordCount, b.wordCount) || cmp(a.name, b.name);
    return 0;
  }}
  function cmp(x, y) {{ return x < y ? -1 : x > y ? 1 : 0; }}

  function applySort() {{
    // Snap any open PDF size menu shut. A floating dropdown anchored
    // to a card mid-FLIP looks janky and the user is plainly engaged
    // with the sort, not the download menu.
    Array.prototype.slice.call(grid.querySelectorAll('details.pdf-menu[open]'))
      .forEach(function(d) {{ d.removeAttribute('open'); }});

    // Date and size default to descending (most recent, longest body).
    // Name, pope, and class default ascending: letters from A, pope from
    // Paul VI forward, and class from conciliar constitution down. Grouped
    // sorts use name as their in-category tie-breaker.
    var descByDefault = (state.sort === 'date' || state.sort === 'size');
    var descending = descByDefault !== state.reversed;
    rows.sort(function(a, b) {{
      var c = compare(a, b);
      return descending ? -c : c;
    }});

    // Remove leftover headings from the previous sort, then re-thread
    // cards into a fragment, inserting a heading at each group break.
    animateReorder(function() {{
      Array.prototype.slice.call(grid.querySelectorAll('.group-heading'))
        .forEach(function(h) {{ h.remove(); }});
      var groupKey = GROUPING_KEY[state.sort];
      var frag = document.createDocumentFragment();
      var lastKey = null;
      rows.forEach(function(r) {{
        if (groupKey) {{
          var key = groupKey(r);
          if (key !== lastKey) {{
            var h = document.createElement('h2');
            h.className = 'group-heading';
            h.textContent = key;
            h.dataset.group = key;
            frag.appendChild(h);
            lastKey = key;
          }}
        }}
        frag.appendChild(r.el);
      }});
      grid.appendChild(frag);
    }});

    options.forEach(function(opt) {{
      var active = opt.dataset.sort === state.sort;
      opt.classList.toggle('is-active', active);
      opt.setAttribute('aria-pressed', active ? 'true' : 'false');
    }});
    reverse.classList.toggle('is-reversed', state.reversed);
    reverse.setAttribute('aria-pressed', state.reversed ? 'true' : 'false');

    var meta = SORT_META[state.sort];
    current.textContent = meta.label;
    dirLabel.textContent = '— ' + (state.reversed ? meta.reversed_dir : meta.default_dir);

    try {{
      localStorage.setItem(STORE_KEY, JSON.stringify(state));
    }} catch (e) {{ /* ignore quota / private mode */ }}

    // Refresh heading visibility against the active query.
    applyFilter();
  }}

  function applyFilter() {{
    var q = (input.value || '').trim().toLowerCase();
    var visible = 0;
    rows.forEach(function(r) {{
      var match = !q || r.search.indexOf(q) !== -1;
      r.el.hidden = !match;
      if (match) visible++;
    }});
    // Walk the grid: each heading owns the cards between it and the
    // next heading, so hide a heading whose group has nothing visible.
    var children = Array.prototype.slice.call(grid.children);
    for (var i = 0; i < children.length; i++) {{
      var node = children[i];
      if (!node.classList.contains('group-heading')) continue;
      var anyVisible = false;
      for (var j = i + 1; j < children.length; j++) {{
        if (children[j].classList.contains('group-heading')) break;
        if (!children[j].hidden) {{ anyVisible = true; break; }}
      }}
      node.hidden = !anyVisible;
    }}
    grid.classList.toggle('is-empty', visible === 0);
  }}

  options.forEach(function(opt) {{
    opt.addEventListener('click', function() {{
      if (state.sort === opt.dataset.sort) {{
        state.reversed = !state.reversed;
      }} else {{
        state.sort = opt.dataset.sort;
        state.reversed = false;
      }}
      applySort();
    }});
  }});
  reverse.addEventListener('click', function() {{
    state.reversed = !state.reversed;
    applySort();
  }});
  input.addEventListener('input', applyFilter);

  applySort();
  applyFilter();
}})();
</script>
</body>
</html>
'''
    SITE.mkdir(exist_ok=True)
    out_path = SITE / 'index.html'
    out_path.write_text(page, encoding='utf-8')
    print(f'Wrote {out_path} - {len(slugs)} documents')


if __name__ == '__main__':
    main()
