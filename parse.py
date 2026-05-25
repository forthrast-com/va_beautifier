import re
from bs4 import BeautifulSoup, NavigableString, Tag

with open('sources/gaudium_et_spes_en.html', encoding='iso-8859-1') as f:
    html = f.read()


def clean_text(element):
    text = element.get_text(separator=' ')
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def roman_to_int(s):
    vals = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100}
    s = s.upper().strip()
    result, prev = 0, 0
    for c in reversed(s):
        curr = vals.get(c, 0)
        result += curr if curr >= prev else -curr
        prev = curr
    return result


def parse_num(s):
    s = s.strip()
    return int(s) if s.isdigit() else roman_to_int(s)


_SMALL = {'a', 'an', 'the', 'and', 'but', 'or', 'nor', 'for', 'yet', 'so',
          'at', 'by', 'in', 'of', 'on', 'to', 'up', 'as', 'from', 'with'}

def title_case(s):
    words = s.lower().split()
    result = []
    for i, word in enumerate(words):
        if "'" in word:
            parts = word.split("'")
            parts[0] = parts[0].capitalize()
            result.append("'".join(parts))
        elif i == 0 or i == len(words) - 1 or word not in _SMALL:
            result.append(word.capitalize())
        else:
            result.append(word)
    return ' '.join(result)


notes_split = html.split('NOTES</b>', 1)
body_html = notes_split[0]
notes_html = notes_split[1] if len(notes_split) > 1 else ''

content_start = body_html.find('<hr />')
body_html = body_html[content_start:]
body_soup = BeautifulSoup(body_html, 'html.parser')

# ── Parse front matter (desc + promulgation) ─────────────────────────────────

def _br_text(tag):
    """Get text from tag, using \n to mark original <br /> positions."""
    parts = []
    for child in tag.descendants:
        if hasattr(child, 'name') and child.name == 'br':
            parts.append('\n')
        elif isinstance(child, str):
            parts.append(child)
    return re.sub(r'[ \t]+', ' ', ''.join(parts)).strip()

_fm_soup = BeautifulSoup(body_html, 'html.parser')
_fm_tag = None
for p in _fm_soup.find_all('p'):
    if 'PASTORAL CONSTITUTION' in p.get_text():
        _fm_tag = p
        break

_fm_text = _br_text(_fm_tag) if _fm_tag else ''

# Extract desc: everything up to "GAUDIUM ET SPES"
_desc_match = re.match(r'(.+?)\s*GAUDIUM ET SPES', _fm_text, re.DOTALL)
desc = _desc_match.group(1).strip() if _desc_match else ''

# Extract promulgation: everything after "GAUDIUM ET SPES"
_prom_match = re.search(r'GAUDIUM ET SPES\s*\n(.+)', _fm_text, re.DOTALL)
promulgation = _prom_match.group(1).strip() if _prom_match else ''

current_part = 0
current_part_title = ''
current_chapter = 0
current_chapter_title = ''
current_section = 0
current_section_title = ''

paragraphs = []
current_para = None


def flush_para():
    if current_para:
        paragraphs.append(dict(current_para))


RE_PART     = re.compile(r'^PART\s+([IVX]+)\s*$')
RE_CHAPTER  = re.compile(r'^CHAPTER\s+([IVX]+)\s*$')
RE_SECTION  = re.compile(r'^SECTION\s+(\d+|[IVX]+)\s*(.*)$', re.DOTALL)
RE_PARA_NUM = re.compile(r'^\s*(\d+)\.\s+(.+)', re.DOTALL)

CHAPTER_TITLES = {
    'THE DIGNITY OF THE HUMAN PERSON',
    'THE COMMUNITY OF MANKIND',
    "MAN'S ACTIVITY THROUGHOUT THE WORLD",
    'THE ROLE OF THE CHURCH IN THE MODERN WORLD',
    'FOSTERING THE NOBILITY OF MARRIAGE AND THE FAMILY',
    'THE PROPER DEVELOPMENT OF CULTURE',
    'ECONOMIC AND SOCIAL LIFE',
    'THE LIFE OF THE POLITICAL COMMUNITY',
    'THE FOSTERING OF PEACE AND THE PROMOTION OF A COMMUNITY OF NATIONS',
}

PART_TITLES = {
    "THE CHURCH AND MAN'S CALLING",
    'SOME PROBLEMS OF SPECIAL URGENCY',
}


def process_bold_heading(text):
    global current_part, current_part_title
    global current_chapter, current_chapter_title
    global current_section, current_section_title

    text = re.sub(r'\s+', ' ', text).strip()

    if text == 'PREFACE':
        current_part, current_part_title = 0, 'Preface'
        current_chapter, current_chapter_title = 0, ''
        current_section, current_section_title = 0, ''
        return True

    if text == 'INTRODUCTORY STATEMENT THE SITUATION OF MEN IN THE MODERN WORLD':
        current_part, current_part_title = 0, title_case(text)
        current_chapter, current_chapter_title = 0, ''
        current_section, current_section_title = 0, ''
        return True

    m = RE_PART.match(text)
    if m:
        current_part = roman_to_int(m.group(1))
        current_part_title = ''
        current_chapter, current_chapter_title = 0, ''
        current_section, current_section_title = 0, ''
        return True

    if text in PART_TITLES:
        current_part_title = title_case(text)
        return True

    m = RE_CHAPTER.match(text)
    if m:
        current_chapter = roman_to_int(m.group(1))
        current_chapter_title = ''
        current_section, current_section_title = 0, ''
        return True

    if text in CHAPTER_TITLES:
        current_chapter_title = title_case(text)
        return True

    m = RE_SECTION.match(text)
    if m:
        current_section = parse_num(m.group(1))
        current_section_title = title_case(re.sub(r'\s+', ' ', m.group(2)).strip())
        return True

    return False


for tag in body_soup.find_all(['p', 'center', 'hr']):
    if tag.name == 'hr':
        continue

    text = clean_text(tag)
    if not text:
        continue

    bolds = tag.find_all('b')
    if bolds:
        for b in bolds:
            bt = re.sub(r'\s+', ' ', b.get_text(separator=' ')).strip()
            if bt:
                process_bold_heading(bt)
        if tag.name == 'center':
            continue
        if tag.find('b') and RE_SECTION.match(re.sub(r'\s+', ' ', tag.find('b').get_text()).strip()):
            continue

    m = RE_PARA_NUM.match(text)
    if m:
        flush_para()
        current_para = {
            'number': int(m.group(1)),
            'part': current_part,
            'part_title': current_part_title,
            'chapter': current_chapter,
            'chapter_title': current_chapter_title,
            'section': current_section,
            'section_title': current_section_title,
            'text': m.group(2).strip(),
        }
    elif current_para is not None and text and not any(
        text.startswith(h) for h in ['[', 'Print', 'Index']
    ):
        all_bold = all(
            isinstance(c, NavigableString) and not str(c).strip()
            or (isinstance(c, Tag) and c.name == 'b')
            for c in tag.children
            if not (isinstance(c, NavigableString) and not str(c).strip())
        )
        if not all_bold:
            current_para['text'] += '\n\n' + text

flush_para()

# ── Parse NOTES section ───────────────────────────────────────────────────────
notes_soup = BeautifulSoup(notes_html, 'html.parser')

footnotes = []
note_part = 0
note_chapter = 0

RE_NOTE_NUM = re.compile(r'^(\d+)[.\s]\s*(.+)', re.DOTALL)
RE_NOTE_CHAPTER = re.compile(r'^Chapter\s+(\d+|[IVX]+)$', re.IGNORECASE)

for tag in notes_soup.find_all('p'):
    text = clean_text(tag)
    if not text:
        continue

    if text == 'PART I':
        note_part, note_chapter = 1, 0
        continue
    if text == 'PART II':
        note_part, note_chapter = 2, 0
        continue
    if text in ('Preface', 'Introduction'):
        note_part, note_chapter = 0, 0
        continue

    mc = RE_NOTE_CHAPTER.match(text)
    if mc:
        note_chapter = parse_num(mc.group(1))
        continue

    m = RE_NOTE_NUM.match(text)
    if m:
        footnotes.append({
            'part': note_part,
            'chapter': note_chapter,
            'number': int(m.group(1)),
            'text': m.group(2).strip(),
        })

# ── Parse Latin headings ──────────────────────────────────────────────────────

with open('sources/gaudium_et_spes_lt.html', encoding='latin-1') as f:
    lt_soup = BeautifulSoup(f.read(), 'html.parser')

bolds_lt = [re.sub(r'\s+', ' ', b.get_text(' ', strip=True))
            for b in lt_soup.find_all('b')
            if re.sub(r'\s+', ' ', b.get_text(' ', strip=True))]

headings_la = {}
i = 0
while i < len(bolds_lt):
    t = bolds_lt[i]
    m = re.match(r'^(\d+)\.\s+(.+)', t)
    if m:
        headings_la[int(m.group(1))] = m.group(2).strip()
        i += 1
        continue
    if re.match(r'^\d+$', t) and i + 1 < len(bolds_lt):
        nxt = bolds_lt[i + 1]
        if not re.match(r'^\d+$', nxt) and not nxt.isupper():
            headings_la[int(t)] = nxt.strip()
            i += 2
            continue
    i += 1

# ── Write TOML ────────────────────────────────────────────────────────────────

def toml_str(s):
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'


def toml_multiline_str(s):
    escaped = s.replace('\\', '\\\\').replace('"""', '\\"\\"\\"')
    return '"""\n' + escaped + '"""'


def write_toml(paragraphs, footnotes, path, desc='', promulgation=''):
    lines = []
    if desc:
        lines.append(f'desc = {toml_multiline_str(desc)}')
    if promulgation:
        lines.append(f'promulgation = {toml_multiline_str(promulgation)}')
    if desc or promulgation:
        lines.append('')
    for p in paragraphs:
        lines.append('[[paragraphs]]')
        lines.append(f'number = {p["number"]}')
        lines.append(f'part = {p["part"]}')
        lines.append(f'part_title = {toml_str(p["part_title"])}')
        lines.append(f'chapter = {p["chapter"]}')
        lines.append(f'chapter_title = {toml_str(p["chapter_title"])}')
        lines.append(f'section = {p["section"]}')
        lines.append(f'section_title = {toml_str(p["section_title"])}')
        lines.append(f'heading_la = {toml_str(p.get("heading_la", ""))}')
        lines.append(f'text = {toml_multiline_str(p["text"])}')
        lines.append('')
    for fn in footnotes:
        lines.append('[[footnotes]]')
        lines.append(f'part = {fn["part"]}')
        lines.append(f'chapter = {fn["chapter"]}')
        lines.append(f'number = {fn["number"]}')
        lines.append(f'text = {toml_multiline_str(fn["text"])}')
        lines.append('')
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))


for p in paragraphs:
    p['heading_la'] = headings_la.get(p['number'], '')

write_toml(paragraphs, footnotes, 'gaudium_et_spes.toml', desc=desc, promulgation=promulgation)

print(f"Written: {len(paragraphs)} paragraphs, {len(footnotes)} footnotes")
print("\nSample:")
for p in paragraphs[:3]:
    print(f"  §{p['number']} part={p['part']} chapter={p['chapter']} section={p['section']}")
    print(f"    text: {p['text'][:120]!r}")
