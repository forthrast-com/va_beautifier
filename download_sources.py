#!/usr/bin/env python3
"""Download Vatican HTML source material used or queued by this project.

By default, downloads every manifest entry that is not already present.
Choose individual keys or a category when only part of the collection is
wanted; use `--force` to refresh existing files deliberately.
"""

import argparse
import hashlib
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
    # sha256 of the snapshot the extractors were written against. `sources/`
    # is gitignored, so without a pin every walker — and every load-time
    # `core.repair` — is matched against an unversioned moving target, and a
    # silently refreshed page looks like a mysterious extractor regression.
    # Blank means unpinned (reference captures, newly queued sources).
    sha256: str = ''


def file_digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def drift(source):
    """`None` when the local snapshot is absent, unpinned, or matches."""
    target = SOURCES / source.filename
    if not source.sha256 or not target.exists():
        return None
    actual = file_digest(target)
    return None if actual == source.sha256 else actual


SOURCES_MANIFEST = (
    Source(
        'gaudium_et_spes_en',
        'gaudium_et_spes_en.html',
        'https://www.vatican.va/archive/hist_councils/ii_vatican_council/'
        'documents/vat-ii_const_19651207_gaudium-et-spes_en.html',
        'implemented',
        'Gaudium et Spes (English)',
            sha256='23b935b99bdaa1cd8bc5ee0951f418672d1d246d008d026ada56e1d01861c12d',
    ),
    Source(
        'gaudium_et_spes_lt',
        'gaudium_et_spes_lt.html',
        'https://www.vatican.va/archive/hist_councils/ii_vatican_council/'
        'documents/vat-ii_const_19651207_gaudium-et-spes_lt.html',
        'implemented',
        'Gaudium et Spes (Latin)',
            sha256='bc2b1022686fb3a6dc6e1afebc244569abe133bd554999dfbe9dfdccf57b73f5',
    ),
    Source(
        'laudato_si_en',
        'laudato_si_en.html',
        'https://www.vatican.va/content/francesco/en/encyclicals/documents/'
        'papa-francesco_20150524_enciclica-laudato-si.html',
        'implemented',
        "Laudato Si' (English)",
            sha256='b16ab3057de6c2ccbcb61481098ac4ece4917ee2aaf1e70181173a631beebe67',
    ),
    Source(
        'laudato_si_lt',
        'laudato_si_lt.html',
        'https://www.vatican.va/content/francesco/la/encyclicals/documents/'
        'papa-francesco_20150524_enciclica-laudato-si.html',
        'implemented',
        "Laudato Si' (Latin)",
            sha256='a4c40e0c30c0c48e829ea82c1ff16d5baba70ffec5bcb06235fb427241dadc11',
    ),
    Source(
        'magnifica_humanitas_en',
        'magnifica_humanitas_en.html',
        'https://www.vatican.va/content/leo-xiv/en/encyclicals/documents/'
        '20260515-magnifica-humanitas.html',
        'implemented',
        'Magnifica Humanitas (English)',
            sha256='819a8464f27b0e9213995ef259022a7266e925e8b4ffa57303128044c2b57c9b',
    ),
    Source(
        'fides_et_ratio_en',
        'fides_et_ratio_en.html',
        'https://www.vatican.va/content/john-paul-ii/en/encyclicals/documents/'
        'hf_jp-ii_enc_14091998_fides-et-ratio.html',
        'implemented',
        'Fides et Ratio (English)',
            sha256='5f36fcbb7826c939a959bcec24d8ee1ce23679d17c22fb78c8fc805f4ddeb6ab',
    ),
    Source(
        'lumen_fidei_en',
        'lumen_fidei_en.html',
        'https://www.vatican.va/content/francesco/en/encyclicals/documents/'
        'papa-francesco_20130629_enciclica-lumen-fidei.html',
        'implemented',
        'Lumen Fidei (English)',
            sha256='71844b9a717be4360a67a3db5aec8cdfc79e3a4137c096884c4530e5bc083a90',
    ),
    Source(
        'verbum_domini_en',
        'verbum_domini_en.html',
        'https://www.vatican.va/content/benedict-xvi/en/apost_exhortations/'
        'documents/hf_ben-xvi_exh_20100930_verbum-domini.html',
        'implemented',
        'Verbum Domini (English)',
            sha256='6b1d2530a907f960ebe15fed48fe7181bed0b664a6f1978f908c0cbc7909d64c',
    ),
    Source(
        'deus_caritas_est_en',
        'deus_caritas_est_en.html',
        'https://www.vatican.va/content/benedict-xvi/en/encyclicals/documents/'
        'hf_ben-xvi_enc_20051225_deus-caritas-est.html',
        'implemented',
        'Deus Caritas Est (English)',
            sha256='0f21533523e1bcdb06482dd3290c470be3e83024de199fbc9ac2cc8de5cdc554',
    ),
    Source(
        'spe_salvi_en',
        'spe_salvi_en.html',
        'https://www.vatican.va/content/benedict-xvi/en/encyclicals/documents/'
        'hf_ben-xvi_enc_20071130_spe-salvi.html',
        'implemented',
        'Spe Salvi (English)',
            sha256='3bca40e81d8ac003c85c749846436e2494fd8425bdc614e9775f8d69fe046f61',
    ),
    Source(
        'caritas_in_veritate_en',
        'caritas_in_veritate_en.html',
        'https://www.vatican.va/content/benedict-xvi/en/encyclicals/documents/'
        'hf_ben-xvi_enc_20090629_caritas-in-veritate.html',
        'implemented',
        'Caritas in Veritate (English)',
            sha256='a04520350793ddac65fbc1bbbc5659c305ccf3aa76dd49a04bff8042924b34fe',
    ),
    Source(
        'ecclesia_in_oceania_en',
        'ecclesia_in_oceania_en.html',
        'https://www.vatican.va/content/john-paul-ii/en/apost_exhortations/'
        'documents/hf_jp-ii_exh_20011122_ecclesia-in-oceania.html',
        'implemented',
        'Ecclesia in Oceania (English)',
            sha256='a19c4871349c7564b081bc9af1a6b726416fa68050403e97a0523a36b4f65f9f',
    ),
    Source(
        'fratelli_tutti_en',
        'Fratelli tutti_en.html',
        'https://www.vatican.va/content/francesco/en/encyclicals/documents/'
        'papa-francesco_20201003_enciclica-fratelli-tutti.html',
        'implemented',
        'Fratelli tutti (English)',
            sha256='f9844c99ee454a5564032a7a29d44d748675f17750065c9b6bb8312f7ae390d3',
    ),
    Source(
        'sacrosanctum_concilium_en',
        'Sacrosanctum Concilium_en.html',
        'https://www.vatican.va/archive/hist_councils/ii_vatican_council/'
        'documents/vat-ii_const_19631204_sacrosanctum-concilium_en.html',
        'implemented',
        'Sacrosanctum Concilium (English)',
            sha256='7a5739ce17bbd35874555c21473e9d82ea10fa2abac424e951d695da60da8443',
    ),
    Source(
        'sacrosanctum_concilium_lt',
        'Sacrosanctum Concilium_la.html',
        'https://www.vatican.va/archive/hist_councils/ii_vatican_council/'
        'documents/vat-ii_const_19631204_sacrosanctum-concilium_lt.html',
        'implemented',
        'Sacrosanctum Concilium (Latin)',
            sha256='a0e7f540d4e55a04840b799386049542906675b0e505a6959e516ecd34568fb3',
    ),
    Source(
        'antiqua_et_nova_en',
        'antiqua_et_nova_en.html',
        'https://www.vatican.va/roman_curia/congregations/cfaith/documents/'
        'rc_ddf_doc_20250128_antiqua-et-nova_en.html',
        'implemented',
        'Antiqua et nova (English)',
            sha256='d5f8fca0f9f39649bef0b648ac24c394167a33f730efc59136b8852e6e335edf',
    ),
    Source(
        'quo_vadis_humanitas_en',
        'quo_vadis_humanitas_en.html',
        'https://www.vatican.va/roman_curia/congregations/cfaith/'
        'cti_documents/rc_cti_doc_20260304_quo-vadis-humanits_en.html',
        'implemented',
        'Quo vadis, humanitas? (English)',
            sha256='14d2e0fc9fbf6b9818b6fd7fd6852b6cd905c6d0952db91f35afd6b60be8d520',
    ),
    Source(
        'libertatis_nuntius_en',
        'theology_of_liberation_en.html',
        'https://www.vatican.va/roman_curia/congregations/cfaith/documents/'
        'rc_con_cfaith_doc_19840806_theology-liberation_en.html',
        'implemented',
        'Libertatis Nuntius (English)',
            sha256='3b6254ed196108a93c2798cf2bebde42efcf82fe39dfcdc4a32c703c0e4e7dd9',
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
        if not target.exists():
            present = 'missing'
        elif drift(source):
            present = 'DRIFTED'
        elif source.sha256:
            present = 'pinned'
        else:
            present = 'present'
        print(
            f'{source.category:11} {source.key:29} {present:7} '
            f'{source.title} -> {source.filename}'
        )


def print_hashes(sources):
    """Emit `key  sha256` for present snapshots, to paste into the manifest."""
    for source in sources:
        target = SOURCES / source.filename
        if target.exists():
            print(f'{source.key:29} {file_digest(target)}')
        else:
            print(f'{source.key:29} (missing)')


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
    if source.sha256:
        actual = hashlib.sha256(content).hexdigest()
        if actual != source.sha256:
            # Not fatal — the fetch is how you *intend* to pick up an
            # upstream change. But say so, because every extractor and every
            # `core.repair` was written against the pinned bytes.
            print(f'      NOTE: {source.key} no longer matches its pin.\n'
                  f'      expected {source.sha256}\n'
                  f'      actual   {actual}\n'
                  f'      Re-check the extractor before updating the pin.')


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
        '--hashes', action='store_true',
        help='print sha256 of present snapshots, to paste into the manifest',
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
    if args.hashes:
        print_hashes(sources)
        return
    if args.list:
        list_sources(sources)
        return
    for source in sources:
        download(source, force=args.force, dry_run=args.dry_run)


if __name__ == '__main__':
    main()
