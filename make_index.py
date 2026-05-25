"""Render the flat GitHub Pages landing page from document TOML metadata."""

from html import escape
from pathlib import Path
import sys
import tomllib


HUES = {
    'gaudium_et_spes': 42,
    'laudato_si': 140,
    'magnifica_humanitas': 230,
}


def render_card(slug):
    with open(f'{slug}.toml', 'rb') as source:
        data = tomllib.load(source)

    name = escape(data['name'])
    description = ' '.join(
        escape(line.strip()) for line in data.get('desc', '').splitlines()
        if line.strip()
    )
    source_url = escape(data.get('source_url', ''), quote=True)
    original = (
        f'<a class="source" href="{source_url}" target="_blank" rel="noopener">'
        'Original Vatican document</a>'
        if source_url else ''
    )
    hue = HUES.get(slug, 42)
    return f'''<article class="edition" style="--hue: {hue}">
  <a class="edition-link" href="{slug}.html">
    <h2>{name}</h2>
    <p>{description}</p>
    <span class="read">Read edition</span>
  </a>
  {original}
</article>'''


def main():
    slugs = sys.argv[1:]
    if not slugs:
        raise SystemExit('usage: python make_index.py DOC [DOC ...]')

    cards = '\n'.join(render_card(slug) for slug in slugs)
    page = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Forthrast Editions | Vatican Documents</title>
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
  width: min(62rem, calc(100% - 2.5rem));
  margin: 0 auto;
  padding: clamp(3rem, 9vh, 6rem) 0 3rem;
}}
.brand {{
  color: var(--dim);
  font-family: system-ui, -apple-system, sans-serif;
  font-size: .8rem;
  letter-spacing: .18em;
  text-transform: uppercase;
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
.editions {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(16rem, 1fr));
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
  display: block;
  color: inherit;
  min-height: 15rem;
  padding-top: 1.25rem;
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
}}
footer a {{ color: inherit; }}
</style>
</head>
<body>
<main>
  <p class="brand">Forthrast Editions</p>
  <h1>Vatican documents, set for reading.</h1>
  <p class="intro">Reader editions with navigation, footnotes and persistent bookmarks. Generated via templater scripts from Vatican HTML.</p>
  <section class="editions" aria-label="Available documents">
{cards}
  </section>
  <footer>
    <div><a href="mailto:me@forthrast.com">me@forthrast.com</a></div>
    <div><a href="https://bsky.app/profile/forthrast.com" target="_blank" rel="noopener">@forthrast.com on Bluesky</a></div>
  </footer>
</main>
</body>
</html>
'''
    Path('index.html').write_text(page, encoding='utf-8')
    print(f'Wrote index.html - {len(slugs)} documents')


if __name__ == '__main__':
    main()
