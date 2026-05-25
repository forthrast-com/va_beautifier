#!/bin/sh
# Parse all sources → TOML → HTML. Run from project root.
# Add a new doc by dropping `extract/<slug>.py` and adding the slug below.
set -e

DOCS="gaudium_et_spes laudato_si"

nix-shell --run "
set -e
for d in $DOCS; do
    python parse.py \$d
    python make_html.py \$d
done
"
