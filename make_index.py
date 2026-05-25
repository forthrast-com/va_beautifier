"""Render the flat GitHub Pages landing page from document TOML metadata."""

from html import escape
import sys

from core import read_toml, title_case
from project import BUILD, SITE


def render_card(slug):
    data = read_toml(BUILD / f'{slug}.toml')

    name = escape(data['name'])
    # The title-block descriptor is split across desc (above title) and
    # desc_post (below title) in the TOML. The card already shows the doc
    # name as <h2>, so glue desc + desc_post into one flowing subtitle
    # without re-inserting the title between them, then title-case the
    # whole concatenation as a single phrase (keeps small words like
    # "on" / "in" lowercase mid-flow and preserves Roman numerals).
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
  width: min(62rem, calc(100% - 2.5rem));
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
