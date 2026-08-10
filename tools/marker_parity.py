#!/usr/bin/env python3
"""Compare English footnote-marker counts against the Latin edition's.

Three documents ship both languages (GeS, SC, LS). The two texts are
translations of one another and carry the *same* citations at the same
points, but number them differently — English restarts per chapter, Latin
runs continuously — so numbers cannot be compared directly. Paragraph
numbers *are* shared, though, which gives a clean alignment: for each §N,
count the markers on each side. A disagreement localises a dropped or
duplicated marker to a single paragraph.

This is how GeS II.2's two defects were settled: §62 citing a note that did
not exist (a typo for 15) and §57 having lost its (3) outright, which cost
Gen 1:28 its place in every EPUB and PDF, since an uncited note never
reaches the books.

What it catches and what it doesn't: a *count* disagreement, so a dropped
or spurious marker. It would have caught GeS §57 (three English markers
against the Latin's four). It would **not** have caught §62, where the count
matched and the defect was a wrong *number* — that shape is caught by
`test_no_note_is_cited_from_two_paragraphs` and the cite/definition
resolution check instead. The three together cover the marker bug classes
seen so far.

Coverage: nine documents ship a Latin twin. Six were added 2026-08 as
`reference` sources (FeR, LF, DCE, SS, CiV, FT). Verbum Domini's Latin page
is a 34 KB stub with no body; Ecclesia in Oceania and Magnifica Humanitas
404; the Curia notes (AeN, QVH, LN) have no Latin edition.

Known-good: SC (130/130), CiV (79/79), plus GeS and LS below.

Not yet usable: **Lumen Fidei and Fratelli tutti report nonsense** — the
paragraph splitter below is tuned to the old-flat pages, and on those two it
loses the sequence early (LF at §1, FT at §80), so the last span swallows
the rest of the document. Their reports are tool failures, not findings.
DCE, FeR and SS produce small candidate lists that have **not** been
adjudicated; treat them as leads only, and note DCE's §42 is its last
paragraph and so hits the same notes-block leak.

Status: SC agrees on all 130 paragraphs; LS on all but §246 (structural —
the English lifts the closing prayers into appendices). GeS's ten candidates
were adjudicated one by one against the Latin: four were real dropped
markers (§§14, 18, 64, 75) and are repaired in the extractor; six are not
defects and are expected to keep reporting —

  §3          the English merges two Latin notes into one ("John 18:37;
              Matt. 20:28; Mark 10:45" against the Latin's (2) and (3)),
  §78, 92, 93 part II chapter 5, where the English edition carries four
              notes against the Latin's many — a translation difference,
  §81, §82    the same, plus a split artefact: the Latin 81/82 boundary
              lands early here, so (168) is filed under §82 though it sits
              on §81's "safeguards" clause.

A count disagreement is a lead, not a verdict. It also cannot see a marker
that is present but *mis-numbered* — GeS had three of those (§14, §48, §52),
found instead by looking for notes that no paragraph cites.

Usage: python3 tools/marker_parity.py [slug …]
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import CANONICAL_FOOTNOTE_REF, read_toml
from download_sources import SOURCES_MANIFEST
from project import BUILD, SOURCES

# The Latin editions carry the same dialect split as the English ones: the
# old-flat pages (GeS, SC) mark cites "(N)" in latin-1, the modern ones (LS)
# use "[N]" inside anchors and are UTF-8. Accept both forms.
LATIN_MARKER = re.compile(r'\((\d{1,3})\)')  # after marked_text normalisation
# "57 ." / "57." opens a Latin paragraph; the space before the stop is the
# vatican.va typesetting, not a typo.
LATIN_PARA = re.compile(r'(?<![\d.\-–])(\d{1,3})\s*\.\s')


def decoded(path):
    """Latin snapshots are latin-1 (old flat) or UTF-8 (modern)."""
    raw = path.read_bytes()
    try:
        return raw.decode('utf-8')
    except UnicodeDecodeError:
        return raw.decode('latin-1')


def latin_sources():
    """slug → Latin snapshot, for the documents that ship one.

    Category is not a filter here: GeS's Latin is an extractor input and so
    `implemented`, while the editions pulled purely for this cross-check are
    `reference`. Both are equally usable as a second witness.
    """
    out = {}
    for source in SOURCES_MANIFEST:
        if source.key.endswith(('_lt', '_la')):
            out[source.key.rsplit('_', 1)[0]] = source
    return out


def marked_text(raw):
    """Tag-stripped text with every footnote marker normalised to "(N)".

    Three marker dialects across the Latin editions, and getting this wrong
    is how a first pass "found" 105 defects in LS that were really just
    bracket-blindness:

      (N)                 old flat (GeS, SC)
      [<a …>N</a>]        modern bracketed (LS, CiV) — note the brackets sit
                          *outside* the anchor, so stripping tags to spaces
                          leaves "[ N ]" and a naive `\\[\\d+\\]` misses it
      <sup><a …></a>N</sup>   bare superscript (FeR) — no delimiters at all,
                          so it can only be recognised before tags are lost
    """
    # Bare-superscript markers first, while the markup still exists.
    raw = re.sub(r'<sup>\s*(?:<a[^>]*>\s*</a>\s*)?(\d{1,3})\s*</sup>',
                 r'(\1)', raw)
    text = re.sub(r'<[^>]+>', ' ', raw)
    text = re.sub(r'\s+', ' ', text)
    # Re-close brackets the tag strip pulled apart: "[ 12 ]" → "(12)".
    return re.sub(r'[(\[]\s*(\d{1,3})\s*[)\]]', r'(\1)', text)


def latin_paragraph_markers(path):
    """§N → marker count, read from a Latin snapshot's body."""
    raw = decoded(path)
    body = raw.split('NOTAE')[0].split('NOTES')[0]
    text = marked_text(body)

    # Only accept the *next* expected paragraph number. Citations are full of
    # incidental numerals ("AAS 57 (1965), pp. 42-43. Cf. …"), and a greedy
    # splitter reads those as paragraph openings, which silently shifts every
    # subsequent span and manufactures disagreements.
    spans = []
    expected = 1
    for match in LATIN_PARA.finditer(text):
        number = int(match.group(1))
        if number != expected:
            continue
        spans.append((number, match.end()))
        expected += 1

    counts = {}
    for i, (number, start) in enumerate(spans):
        last = i + 1 == len(spans)
        end = len(text) if last else spans[i + 1][1]
        markers = list(LATIN_MARKER.finditer(text, start, end))
        if last:
            # GeS and SC's Latin pages carry no NOTAE heading — the note
            # block simply follows the body, so the final paragraph's span
            # otherwise swallows every definition (§93 read 176 markers).
            # The notes restart at 1, and a closing paragraph under
            # continuous numbering never cites note 1, so the first such
            # marker is the boundary.
            for j, m in enumerate(markers):
                if m.group(1) == '1':
                    markers = markers[:j]
                    break
        counts[number] = len(markers)
    return counts


def main():
    latin = latin_sources()
    slugs = sys.argv[1:] or sorted(latin)
    problems = 0
    for slug in slugs:
        source = latin.get(slug)
        toml = BUILD / f'{slug}.toml'
        if source is None or not toml.exists():
            print(f'{slug}: no Latin edition or no built TOML — skipped')
            continue
        path = SOURCES / source.filename
        if not path.exists():
            print(f'{slug}: {source.filename} missing — skipped')
            continue

        la = latin_paragraph_markers(path)
        data = read_toml(toml)
        print(f'\n=== {slug} ===')
        mismatches = []
        for p in data['paragraphs']:
            n = p['number']
            if n not in la:
                continue
            en_count = len(CANONICAL_FOOTNOTE_REF.findall(p['text']))
            if en_count != la[n]:
                mismatches.append((n, en_count, la[n]))
        if not mismatches:
            print(f'  {len(la)} paragraphs aligned; marker counts agree')
            continue
        problems += len(mismatches)
        print(f'  {len(mismatches)} paragraph(s) disagree '
              f'(§N: english vs latin)')
        for n, en_count, la_count in mismatches:
            verdict = ('english may have dropped a marker'
                       if la_count > en_count
                       else 'english may carry a spurious marker')
            print(f'    §{n:>3}: {en_count} vs {la_count}  — {verdict}')
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
