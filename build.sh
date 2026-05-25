#!/bin/sh
# Parse all sources → TOML → HTML. Run from project root.
# Add a new doc by dropping `extract/<slug>.py` and adding the slug below.
set -e

DOCS="gaudium_et_spes laudato_si magnifica_humanitas"

if [ -z "${VA_BEAUTIFIER_IN_BUILD:-}" ] && command -v nix >/dev/null 2>&1 && [ -f flake.nix ]; then
    VA_BEAUTIFIER_IN_BUILD=1 exec nix develop --command "$0"
fi

for d in $DOCS; do
    python parse.py "$d"
    python make_html.py "$d"
done

python make_index.py $DOCS
