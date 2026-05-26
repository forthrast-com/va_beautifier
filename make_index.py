"""Render the flat GitHub Pages landing page from document TOML metadata."""

from html import escape
import sys

from core import read_toml, title_case
from project import BUILD, SITE


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
# whose template controls what gets bolded, where the linebreaks fall,
# and how the subtitle attaches. Adding a doc means adding a row here;
# adding a doc category means adding a branch in `_build_description`.
CARD_META = {
    'gaudium_et_spes': {
        'type': 'council_constitution',
        'kind': 'Pastoral Constitution on the Church in the Modern World',
        'body': 'Second Vatican Council',
        'promulgated_by': 'Pope Paul VI',
        'date': '7 December 1965',
    },
    'sacrosanctum_concilium': {
        'type': 'council_constitution',
        'kind': 'Constitution on the Sacred Liturgy',
        'body': 'Second Vatican Council',
        'promulgated_by': 'Pope Paul VI',
        'date': '4 December 1963',
    },
    'laudato_si': {
        'type': 'encyclical',
        'kind': 'Encyclical Letter',
        'issuer_prefix': 'of the Holy Father',
        'issuer': 'Francis',
        'subtitle': 'on Care for Our Common Home',
    },
    'magnifica_humanitas': {
        'type': 'encyclical',
        'kind': 'Encyclical Letter',
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


def _build_description(slug):
    meta = CARD_META.get(slug)
    if not meta:
        return None
    kind = meta['type']
    if kind == 'council_constitution':
        return (
            f"{meta['kind']}"
            f"<br>of the <strong>{meta['body']}</strong>"
            f"<br>Promulgated by {meta['promulgated_by']} "
            f"on {meta['date']}"
        )
    if kind == 'encyclical':
        return (
            f"{meta['kind']}"
            f"<br>{meta['issuer_prefix']} "
            f"<strong>{meta['issuer']}</strong>"
            f"<br>{meta['subtitle']}"
        )
    # Organisation-issued (Curia note, Theological-Commission paper):
    # bold every co-signing body on its own line, then the subtitle.
    bodies = '<br>'.join(
        f'<strong>{body}</strong>' for body in meta.get('bodies', ())
    )
    if not bodies:
        return None
    return f'{bodies}<br>{meta["subtitle"]}'


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
            return f'{size:.1f} {unit}'
    return ''


def render_downloads(slug):
    formats = []
    for extension, label in (('pdf', 'PDF'), ('epub', 'EPUB')):
        size = file_size(BUILD / f'{slug}.{extension}')
        if size:
            formats.append(
                f'<a class="format" href="downloads/{slug}.{extension}">'
                f'<span>{label}</span><small>{size}</small></a>'
            )
    if not formats:
        return ''
    return (
        '<div class="formats" aria-label="Download formats">'
        + ''.join(formats)
        + '</div>'
    )


def render_card(slug):
    data = read_toml(BUILD / f'{slug}.toml')

    name = escape(data['name'])
    # The card description is composed from structured CARD_META by
    # template — council constitutions append "of the …Council" and bold
    # the council; encyclicals bold the issuer; org-issued notes stack
    # each co-signing body bolded. Docs without a CARD_META row fall
    # back to the flowed desc + desc_post from the TOML.
    description = _build_description(slug)
    if description is None:
        joined = ' '.join(
            line.strip()
            for part in (data.get('desc', ''), data.get('desc_post', ''))
            for line in part.splitlines()
            if line.strip()
        )
        description = escape(title_case(joined)) if joined else ''
    source_url = escape(data.get('source_url', ''), quote=True)
    original = (
        f'<a class="source" href="{source_url}" target="_blank" rel="noopener">'
        'Original Vatican document</a>'
        if source_url else ''
    )
    hue = data.get('hue', 42)
    downloads = render_downloads(slug)
    return f'''<article class="edition" style="--hue: {hue}">
  <a class="edition-link" href="{slug}.html">
    <h2>{name}</h2>
    <p>{description}</p>
    <span class="read">Read edition</span>
  </a>
  {downloads}
  {original}
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
  --bg: #fbfaf7;
  --surface: #fffefa;
  --fg: #252119;
  --dim: #645d50;
  --rule: #ded7ca;
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    --bg: #171614;
    --surface: #211f1b;
    --fg: #eee9df;
    --dim: #b7b09f;
    --rule: #413c33;
  }}
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  background: var(--bg);
  color: var(--fg);
  font-family: Georgia, 'Times New Roman', serif;
}}
main {{
  width: min(68rem, calc(100% - 2.5rem));
  margin: 0 auto;
  padding: clamp(1.75rem, 5vh, 3rem) 0 3rem;
}}
.brand {{
  color: var(--dim);
  font-family: system-ui, -apple-system, sans-serif;
  font-size: .85rem;
}}
h1 {{
  max-width: 15ch;
  font-size: clamp(2.6rem, 6vw, 4.2rem);
  font-weight: normal;
  line-height: 1.05;
  margin: .7rem 0 1rem;
}}
.intro {{
  max-width: 36rem;
  color: var(--dim);
  font-size: 1.12rem;
  line-height: 1.55;
  margin: 0 0 clamp(2.6rem, 6vw, 4rem);
}}
.sort-bar {{
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: .55rem;
  margin: 0 0 .9rem;
  color: var(--dim);
  font-family: system-ui, -apple-system, sans-serif;
  font-size: .8rem;
}}
.sort-label {{
  letter-spacing: .02em;
}}
.sort-toggle {{
  background: transparent;
  border: 1px solid var(--rule);
  border-radius: 3px;
  color: var(--dim);
  cursor: not-allowed;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: .25rem .4rem;
  opacity: .85;
}}
.sort-icon {{
  width: 1rem;
  height: 1rem;
  fill: currentColor;
}}
.editions {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(20rem, 100%), 1fr));
  gap: 1.15rem;
}}
.edition {{
  border: 1px solid var(--rule);
  border-top: 4px solid hsl(var(--hue), 44%, 42%);
  border-radius: 4px;
  background: var(--surface);
  padding: 0 1.3rem 1.25rem;
}}
.edition-link {{
  color: inherit;
  display: flex;
  flex-direction: column;
  min-height: 14rem;
  padding: 1.25rem 0 .85rem;
  text-decoration: none;
}}
.edition h2 {{
  font-size: 1.6rem;
  font-weight: normal;
  line-height: 1.18;
  margin: 0 0 .8rem;
}}
.edition p {{
  color: var(--dim);
  font-family: system-ui, -apple-system, sans-serif;
  font-size: .9rem;
  line-height: 1.5;
  margin: 0 0 1.35rem;
}}
.read, .source {{
  color: hsl(var(--hue), 50%, 35%);
  font-family: system-ui, -apple-system, sans-serif;
  font-size: .9rem;
}}
.edition-link .read {{
  margin-top: auto;        /* anchor "Read edition" to the bottom of the card */
}}
.formats {{
  border-top: 1px solid var(--rule);
  display: flex;
  gap: .55rem;
  padding: .85rem 0;
}}
.format {{
  align-items: baseline;
  border: 1px solid var(--rule);
  border-radius: 3px;
  color: hsl(var(--hue), 50%, 35%);
  display: flex;
  flex: 1;
  font: .82rem system-ui, -apple-system, sans-serif;
  justify-content: space-between;
  padding: .45rem .55rem;
  text-decoration: none;
}}
.format small {{
  color: var(--dim);
  font-size: .76rem;
}}
.source {{
  border-top: 1px solid var(--rule);
  display: block;
  padding-top: .85rem;
}}
footer {{
  border-top: 1px solid var(--rule);
  color: var(--dim);
  font-family: system-ui, -apple-system, sans-serif;
  font-size: .9rem;
  line-height: 1.7;
  margin-top: 4rem;
  padding-top: 1.2rem;
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  flex-wrap: wrap;
  gap: 1rem;
}}
footer a {{ color: inherit; }}
.attribution {{ text-align: right; font-size: .8rem; opacity: .8; }}
</style>
</head>
<body>
<main>
  <p class="brand">the circulars · vatican.va, retypeset.</p>
  <h1>Vatican documents, set for reading.</h1>
  <p class="intro">Reader editions of a few papal and conciliar documents.<br>Generated via templater scripts from the Vatican HTML.</p>
  <div class="sort-bar" aria-label="Sort controls">
    <span class="sort-label">Sorted by promulgation, newest first</span>
    <button class="sort-toggle" type="button" aria-label="Change sort order" disabled>
      {SORT_ICON_SVG}
    </button>
  </div>
  <section class="editions" aria-label="Available documents">
{cards}
  </section>
  <footer>
    <div class="contacts">
      <div>Email: <a href="mailto:me@forthrast.com">me@forthrast.com</a></div>
      <div>Bluesky: <a href="https://bsky.app/profile/forthrast.com" target="_blank" rel="noopener">@forthrast.com</a></div>
      <div>GitHub: <a href="https://github.com/forthrast-com" target="_blank" rel="noopener">@forthrast-com</a></div>
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
