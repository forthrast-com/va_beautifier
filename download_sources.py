#!/usr/bin/env python3
"""Download Vatican HTML source material used or queued by this project.

By default, downloads every manifest entry that is not already present.
Choose individual keys or a category when only part of the collection is
wanted; use `--force` to refresh existing files deliberately.
"""

import argparse
from dataclasses import dataclass
from pathlib import Path
from urllib.request import Request, urlopen

from project import SOURCES


@dataclass(frozen=True)
class Source:
    key: str
    filename: str
    url: str
    category: str
    title: str


SOURCES_MANIFEST = (
    Source(
        'gaudium_et_spes_en',
        'gaudium_et_spes_en.html',
        'https://www.vatican.va/archive/hist_councils/ii_vatican_council/'
        'documents/vat-ii_const_19651207_gaudium-et-spes_en.html',
        'implemented',
        'Gaudium et Spes (English)',
    ),
    Source(
        'gaudium_et_spes_lt',
        'gaudium_et_spes_lt.html',
        'https://www.vatican.va/archive/hist_councils/ii_vatican_council/'
        'documents/vat-ii_const_19651207_gaudium-et-spes_lt.html',
        'implemented',
        'Gaudium et Spes (Latin)',
    ),
    Source(
        'laudato_si_en',
        'laudato_si_en.html',
        'https://www.vatican.va/content/francesco/en/encyclicals/documents/'
        'papa-francesco_20150524_enciclica-laudato-si.html',
        'implemented',
        "Laudato Si' (English)",
    ),
    Source(
        'laudato_si_lt',
        'laudato_si_lt.html',
        'https://www.vatican.va/content/francesco/la/encyclicals/documents/'
        'papa-francesco_20150524_enciclica-laudato-si.html',
        'implemented',
        "Laudato Si' (Latin)",
    ),
    Source(
        'magnifica_humanitas_en',
        'magnifica_humanitas_en.html',
        'https://www.vatican.va/content/leo-xiv/en/encyclicals/documents/'
        '20260515-magnifica-humanitas.html',
        'implemented',
        'Magnifica Humanitas (English)',
    ),
    Source(
        'fides_et_ratio_en',
        'fides_et_ratio_en.html',
        'https://www.vatican.va/content/john-paul-ii/en/encyclicals/documents/'
        'hf_jp-ii_enc_14091998_fides-et-ratio.html',
        'implemented',
        'Fides et Ratio (English)',
    ),
    Source(
        'lumen_fidei_en',
        'lumen_fidei_en.html',
        'https://www.vatican.va/content/francesco/en/encyclicals/documents/'
        'papa-francesco_20130629_enciclica-lumen-fidei.html',
        'implemented',
        'Lumen Fidei (English)',
    ),
    Source(
        'verbum_domini_en',
        'verbum_domini_en.html',
        'https://www.vatican.va/content/benedict-xvi/en/apost_exhortations/'
        'documents/hf_ben-xvi_exh_20100930_verbum-domini.html',
        'implemented',
        'Verbum Domini (English)',
    ),
    Source(
        'deus_caritas_est_en',
        'deus_caritas_est_en.html',
        'https://www.vatican.va/content/benedict-xvi/en/encyclicals/documents/'
        'hf_ben-xvi_enc_20051225_deus-caritas-est.html',
        'implemented',
        'Deus Caritas Est (English)',
    ),
    Source(
        'spe_salvi_en',
        'spe_salvi_en.html',
        'https://www.vatican.va/content/benedict-xvi/en/encyclicals/documents/'
        'hf_ben-xvi_enc_20071130_spe-salvi.html',
        'implemented',
        'Spe Salvi (English)',
    ),
    Source(
        'caritas_in_veritate_en',
        'caritas_in_veritate_en.html',
        'https://www.vatican.va/content/benedict-xvi/en/encyclicals/documents/'
        'hf_ben-xvi_enc_20090629_caritas-in-veritate.html',
        'implemented',
        'Caritas in Veritate (English)',
    ),
    Source(
        'ecclesia_in_oceania_en',
        'ecclesia_in_oceania_en.html',
        'https://www.vatican.va/content/john-paul-ii/en/apost_exhortations/'
        'documents/hf_jp-ii_exh_20011122_ecclesia-in-oceania.html',
        'implemented',
        'Ecclesia in Oceania (English)',
    ),
    Source(
        'fratelli_tutti_en',
        'Fratelli tutti_en.html',
        'https://www.vatican.va/content/francesco/en/encyclicals/documents/'
        'papa-francesco_20201003_enciclica-fratelli-tutti.html',
        'queued',
        'Fratelli tutti (English)',
    ),
    Source(
        'sacrosanctum_concilium_en',
        'Sacrosanctum Concilium_en.html',
        'https://www.vatican.va/archive/hist_councils/ii_vatican_council/'
        'documents/vat-ii_const_19631204_sacrosanctum-concilium_en.html',
        'implemented',
        'Sacrosanctum Concilium (English)',
    ),
    Source(
        'sacrosanctum_concilium_lt',
        'Sacrosanctum Concilium_la.html',
        'https://www.vatican.va/archive/hist_councils/ii_vatican_council/'
        'documents/vat-ii_const_19631204_sacrosanctum-concilium_lt.html',
        'implemented',
        'Sacrosanctum Concilium (Latin)',
    ),
    Source(
        'antiqua_et_nova_en',
        'antiqua_et_nova_en.html',
        'https://www.vatican.va/roman_curia/congregations/cfaith/documents/'
        'rc_ddf_doc_20250128_antiqua-et-nova_en.html',
        'implemented',
        'Antiqua et nova (English)',
    ),
    Source(
        'quo_vadis_humanitas_en',
        'quo_vadis_humanitas_en.html',
        'https://www.vatican.va/roman_curia/congregations/cfaith/'
        'cti_documents/rc_cti_doc_20260304_quo-vadis-humanits_en.html',
        'implemented',
        'Quo vadis, humanitas? (English)',
    ),
    Source(
        'francis_g7_ai_en',
        'francis_g7_ai_en.html',
        'https://www.vatican.va/content/francesco/en/speeches/2024/june/'
        'documents/20240614-g7-intelligenza-artificiale.html',
        'reference',
        'Francis at the G7 on artificial intelligence (English)',
    ),
)

CATEGORIES = ('implemented', 'queued', 'reference')


def selected_sources(keys, category):
    by_key = {source.key: source for source in SOURCES_MANIFEST}
    if keys:
        return [by_key[key] for key in keys]
    if category:
        return [
            source for source in SOURCES_MANIFEST
            if source.category == category
        ]
    return list(SOURCES_MANIFEST)


def list_sources(sources):
    for source in sources:
        target = SOURCES / source.filename
        present = 'present' if target.exists() else 'missing'
        print(
            f'{source.category:11} {source.key:29} {present:7} '
            f'{source.title} -> {source.filename}'
        )


def download(source, *, force=False, dry_run=False):
    target = SOURCES / source.filename
    if target.exists() and not force:
        print(f'skip  {source.key}: {target.name} already exists')
        return
    if dry_run:
        print(f'fetch {source.key}: {source.url} -> {target.name}')
        return

    request = Request(source.url, headers={'User-Agent': 'va_beautifier/1.0'})
    with urlopen(request, timeout=30) as response:
        content = response.read()

    SOURCES.mkdir(exist_ok=True)
    temporary = target.with_suffix(target.suffix + '.part')
    temporary.write_bytes(content)
    temporary.replace(target)
    print(f'wrote {target}: {len(content)} bytes')


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        'keys', nargs='*',
        metavar='SOURCE',
        help='specific manifest source keys to download',
    )
    parser.add_argument(
        '--category', choices=CATEGORIES,
        help='download only a manifest category when no source keys are given',
    )
    parser.add_argument(
        '--list', action='store_true',
        help='list selected sources and whether their target files exist',
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='show downloads without making network requests or writing files',
    )
    parser.add_argument(
        '--force', action='store_true',
        help='replace target files that already exist',
    )
    args = parser.parse_args()

    if args.keys and args.category:
        parser.error('choose source keys or --category, not both')
    known_keys = {source.key for source in SOURCES_MANIFEST}
    unknown_keys = sorted(set(args.keys) - known_keys)
    if unknown_keys:
        parser.error(f'unknown source key: {", ".join(unknown_keys)}')

    sources = selected_sources(args.keys, args.category)
    if args.list:
        list_sources(sources)
        return
    for source in sources:
        download(source, force=args.force, dry_run=args.dry_run)


if __name__ == '__main__':
    main()
