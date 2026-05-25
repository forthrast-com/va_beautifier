#!/bin/sh
# Parse sources → TOML → HTML. Run from project root.
set -e
nix-shell --run "python parse.py && python make_html.py"
