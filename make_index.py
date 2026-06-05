"""Render the flat GitHub Pages landing page from document TOML metadata."""

import datetime
from html import escape
import sys

from core import read_toml, title_case
from project import BUILD, DOWNLOADS, SITE


# Promulgation dates lifted from each source's `eventDate` meta tag. Used to
# sort the landing page reverse-chronologically; missing entries sort to the
# bottom (treated as the empty string).
PROMULGATION_DATES = {
    'gaudium_et_spes':       '1965-12-07',
    'laudato_si':            '2015-05-24',
    'magnifica_humanitas':   '2026-05-15',
    'antiqua_et_nova':       '2025-01-28',
    'quo_vadis_humanitas':   '2026-03-04',
    'sacrosanctum_concilium':'1963-12-04',
}


# Structured card metadata per document. Each entry declares a `type`
# whose template controls what gets bolded and how the description flows.
# Adding a doc means adding a row here; adding a doc category means adding
# a branch in `_card_fields`.
CARD_META = {
    'gaudium_et_spes': {
        'type': 'council_constitution',
        'kind_long': 'Pastoral Constitution on the Church in the Modern World',
        'body': 'Second Vatican Council',
        'promulgated_by': 'Pope Paul VI',
    },
    'sacrosanctum_concilium': {
        'type': 'council_constitution',
        'kind_long': 'Constitution on the Sacred Liturgy',
        'body': 'Second Vatican Council',
        'promulgated_by': 'Pope Paul VI',
    },
    'laudato_si': {
        'type': 'encyclical',
        'issuer_prefix': 'of the Holy Father',
        'issuer': 'Francis',
        'subtitle': 'on Care for Our Common Home',
    },
    'magnifica_humanitas': {
        'type': 'encyclical',
        'issuer_prefix': 'of His Holiness',
        'issuer': 'Pope Leo XIV',
        'subtitle': (
            'on Safeguarding the Human Person '
            'in the Time of Artificial Intelligence'
        ),
    },
    'antiqua_et_nova': {
        'type': 'curia_note',
        'bodies': (
            'Dicastery for the Doctrine of the Faith',
            'Dicastery for Culture and Education',
        ),
        'subtitle': (
            'Note on the Relationship Between Artificial Intelligence '
            'and Human Intelligence'
        ),
    },
    'quo_vadis_humanitas': {
        'type': 'commission_paper',
        'bodies': ('International Theological Commission',),
        'subtitle': (
            'Thinking through Christian Anthropology in the Face of '
            'Certain Scenarios for the Future of Humanity'
        ),
    },
}

# Short label that appears tracked at the head of each tile.
TILE_KIND_LABEL = {
    'encyclical':           'Encyclical Letter',
    'council_constitution': 'Conciliar Constitution',
    'curia_note':           'Doctrinal Note',
    'commission_paper':     'Commission Paper',
}


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


def _card_fields(slug, data):
    """Collect all the tile-level fields for one document into one dict.

    Each tile renders the same shape (kind, title, subtitle, byline,
    date) so the layout can stay uniform across encyclicals, conciliar
    constitutions, dicastery notes, and theological-commission papers.
    The bolded element in each byline is the human-or-body that the
    rendered card most wants the eye to land on."""
    meta = CARD_META.get(slug, {})
    kind_type = meta.get('type', '')
    subtitle = meta.get('subtitle', '')
    byline = ''

    if kind_type == 'encyclical':
        byline = f'{meta["issuer_prefix"]} <strong>{meta["issuer"]}</strong>'
    elif kind_type == 'council_constitution':
        subtitle = meta.get('kind_long', '')
        byline = f'of the <strong>{meta["body"]}</strong>'
        if meta.get('promulgated_by'):
            byline += f', promulgated by {meta["promulgated_by"]}'
    elif kind_type == 'curia_note':
        # Signers (Prefects, sub-commission chair) ride dc:creator and
        # appear in the PDF colophon; the tile keeps the institutional
        # voice up top so it doesn't read like four bylines stacked.
        byline = '<strong>' + ' &amp; '.join(meta.get('bodies', ())) + '</strong>'
    elif kind_type == 'commission_paper':
        byline = '<strong>' + ', '.join(meta.get('bodies', ())) + '</strong>'
    else:
        # No CARD_META row — flow the TOML's desc / desc_post fallback.
        joined = ' '.join(
            line.strip()
            for part in (data.get('desc', ''), data.get('desc_post', ''))
            for line in part.splitlines()
            if line.strip()
        )
        byline = escape(title_case(joined)) if joined else ''

    return {
        'name':        data['name'],
        'kind_label':  TILE_KIND_LABEL.get(kind_type, ''),
        'subtitle':    subtitle,
        'byline':      byline,
        'date':        _formatted_date(data.get('date', '')),
        'iso_date':    data.get('date', ''),
        'hue':         data.get('hue', 42),
        'source_url':  data.get('source_url', ''),
    }


SORT_ICON_SVG = (
    '<svg class="sort-icon" viewBox="0 0 16 16" aria-hidden="true" '
    'focusable="false">'
    '<rect x="2" y="3"  width="12" height="1.6" rx=".5" />'
    '<rect x="2" y="7"  width="8"  height="1.6" rx=".5" />'
    '<rect x="2" y="11" width="4"  height="1.6" rx=".5" />'
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


def render_card(slug):
    data = read_toml(BUILD / f'{slug}.toml')
    f = _card_fields(slug, data)
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

    return f'''<article class="edition" style="--hue: {f["hue"]}">
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


def main():
    slugs = sys.argv[1:]
    if not slugs:
        raise SystemExit('usage: python make_index.py DOC [DOC ...]')

    # Reverse chronological by promulgation date (newest first). Unknown
    # slugs sort to the bottom in their original order.
    slugs = sorted(
        slugs,
        key=lambda slug: PROMULGATION_DATES.get(slug, ''),
        reverse=True,
    )

    cards = '\n'.join(render_card(slug) for slug in slugs)
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
  max-width: 22ch;
  font-size: clamp(2.6rem, 6.4vw, 4.4rem);
  font-style: italic;
  font-weight: normal;
  line-height: 1.04;
  letter-spacing: -0.005em;
  margin: 0 0 1.1rem;
}}
.intro {{
  max-width: 38rem;
  color: var(--ink-dim);
  font-size: 1.06rem;
  line-height: 1.6;
  margin: 0;
}}
.intro a {{ color: inherit; text-decoration-color: var(--ink-fainter); }}

/* ── Sort bar ────────────────────────────────────────────────────────── */
.sort-bar {{
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: .8rem;
  margin: 0 0 1.4rem;
  color: var(--ink-fainter);
  font-family: ui-monospace, "SF Mono", Menlo, monospace;
  font-size: .72rem;
  letter-spacing: .12em;
  text-transform: uppercase;
}}
.sort-label small {{ color: var(--ink-dim); font-size: inherit; }}
.sort-toggle {{
  background: transparent;
  border: 1px solid var(--rule);
  border-radius: 2px;
  color: var(--ink-fainter);
  cursor: not-allowed;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: .3rem .35rem;
  opacity: .85;
}}
.sort-icon {{
  width: .9rem;
  height: .9rem;
  fill: currentColor;
}}

/* ── Editions grid ───────────────────────────────────────────────────── */
.editions {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(27rem, 100%), 1fr));
  gap: 1.4rem;
}}

.edition {{
  position: relative;
  background: var(--paper);
  border: 1px solid var(--paper-edge);
  border-left: 5px solid hsl(calc(var(--hue) - 4), 42%, 40%);
  padding: 1.6rem 1.7rem 1.4rem;
  display: flex;
  flex-direction: column;
  min-height: 22rem;
  box-shadow: 0 1px 0 0 var(--rule-soft);
}}
@media (prefers-color-scheme: dark) {{
  .edition {{
    border-left-color: hsl(calc(var(--hue) - 4), 42%, 56%);
  }}
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
}}
.pdf-options a {{
  display: flex;
  justify-content: space-between;
  gap: .5rem;
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
<body>
<main>
  <header class="masthead">
    <p class="brand"><b>The&nbsp;Circulars</b> · vatican.va, retypeset</p>
    <h1>Vatican documents, set for reading.</h1>
    <p class="intro">Reading editions of papal and conciliar texts, drawn from the
    canonical HTML on <a href="https://www.vatican.va" target="_blank" rel="noopener">vatican.va</a>
    and run through templated extractors into a web reader, a typeset PDF,
    and an EPUB. Source on <a href="https://github.com/forthrast-com/va_beautifier" target="_blank" rel="noopener">GitHub</a>.</p>
  </header>

  <div class="sort-bar" aria-label="Sort controls">
    <span class="sort-label"><small>Sorted by</small> Promulgation, newest first</span>
    <button class="sort-toggle" type="button" aria-label="Change sort order" disabled>
      {SORT_ICON_SVG}
    </button>
  </div>

  <section class="editions" aria-label="Available documents">
{cards}
  </section>

  <footer>
    <div class="contacts">
      <div><span>email</span><a href="mailto:me@forthrast.com">me@forthrast.com</a></div>
      <div><span>bsky</span><a href="https://bsky.app/profile/forthrast.com" target="_blank" rel="noopener">@forthrast.com</a></div>
      <div><span>code</span><a href="https://github.com/forthrast-com" target="_blank" rel="noopener">@forthrast-com</a></div>
    </div>
    <div class="attribution">made with claude and codex ^•^</div>
  </footer>
</main>
</body>
</html>
'''
    SITE.mkdir(exist_ok=True)
    out_path = SITE / 'index.html'
    out_path.write_text(page, encoding='utf-8')
    print(f'Wrote {out_path} - {len(slugs)} documents')


if __name__ == '__main__':
    main()
