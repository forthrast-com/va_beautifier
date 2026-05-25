"""Parse a Vatican-document HTML source into the canonical TOML intermediate.

Usage: python parse.py <doc>

Where <doc> is the name of any module under extract/ (drop a new module
exposing `extract()` to add a new document — no registry edit needed).
"""

import argparse
import importlib
import pkgutil

import core
import extract


def _available():
    return sorted(m.name for m in pkgutil.iter_modules(extract.__path__))


def main():
    docs = _available()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('doc', choices=docs, metavar='DOC',
                    help=f'one of: {", ".join(docs)}')
    ap.add_argument('-o', '--out',
                    help='Output TOML path (default: {doc}.toml)')
    args = ap.parse_args()

    mod = importlib.import_module(f'extract.{args.doc}')
    result = mod.extract()

    out = args.out or f'{args.doc}.toml'
    core.write_toml(out, **result)
    print(f"Wrote {out}: {len(result['paragraphs'])} paragraphs, "
          f"{len(result['footnotes'])} footnotes")


if __name__ == '__main__':
    main()
