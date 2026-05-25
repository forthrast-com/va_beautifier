"""Shared repository paths for project entrypoints."""

from pathlib import Path


ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / 'assets'
BUILD = ROOT / 'build'
SITE = ROOT / 'site'
SOURCES = ROOT / 'sources'
