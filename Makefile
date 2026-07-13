# DOCS, the per-source fetch rules, and the per-document TOML rules are all
# generated from the download_sources.py manifest (slug + source files) and
# each extractor's dialect import — see gen_doc_rules.py. The explicit default
# goal keeps the generated include's own build/docs.mk rule from hijacking it.
.DEFAULT_GOAL := all

.PHONY: all fetch books site qa check clean help list test

# Fetch template used by the generated include: one target per source snapshot,
# so a build can pull missing Vatican HTML on demand rather than failing at the
# first absent prerequisite. Must be defined before the include expands it.
define FETCH_SOURCE
$1: download_sources.py
	python3 download_sources.py $2
endef

# Generated from the manifest + extractors; make remakes this include when any
# of them changes, then re-execs to read the fresh DOCS / rules. Steady state
# (nothing changed) does not regenerate, so no double run.
build/docs.mk: gen_doc_rules.py download_sources.py project.py $(wildcard extract/*.py)
	@mkdir -p build
	python3 gen_doc_rules.py $@

include build/docs.mk

HTMLS := $(DOCS:%=site/%.html)
TOMLS := $(DOCS:%=build/%.toml)
EPUBS := $(DOCS:%=site/downloads/%.epub)
PDFS  := $(DOCS:%=site/downloads/%-a4.pdf) \
         $(DOCS:%=site/downloads/%-a5.pdf) \
         $(DOCS:%=site/downloads/%-a6.pdf)
BOOKS := $(EPUBS) $(PDFS)

# `all` builds the books first so the landing page can report current
# PDF/EPUB sizes; the index target depends on every HTML rendered too.
all: books site/index.html

fetch:
	python3 download_sources.py --category implemented

qa: all
	VA_REQUIRE_SITE_ARTIFACTS=1 python3 -m unittest tests.test_site_artifacts -v

# The local commit gate: populate source snapshots, run the generic suite,
# then rebuild incrementally and inspect the finished site artefacts.
check: fetch
	$(MAKE) test
	$(MAKE) -j8 qa

# --- HTML targets ---

site/%.html: build/%.toml make_html.py assets/styles.css assets/scripts.js
	python3 make_html.py $*

site/index.html: $(HTMLS) $(BOOKS) make_index.py
	python3 make_index.py $(DOCS)

# --- Books (requires pandoc + typst) ---

# All four artefacts (EPUB plus A4, A5, and A6 PDFs) come from one grouped
# make_book.py invocation. If any sibling artefact is missing or stale, GNU
# make rebuilds the whole group once.
books: $(BOOKS)

site/downloads/%.epub site/downloads/%-a4.pdf \
site/downloads/%-a5.pdf site/downloads/%-a6.pdf &: build/%.toml make_book.py templates/book.typ templates/epub.css templates/strip_fn_backlink.lua
	python3 make_book.py $*

# --- Housekeeping ---

help:
	@echo "Targets (run inside the dev shell: direnv, or nix develop --command make ...):"
	@echo "  make               build everything: books, readers, catalogue"
	@echo "  make books         EPUB + A4/A5/A6 PDFs for every document"
	@echo "  make <slug>        one reader page (site/<slug>.html)"
	@echo "  make <slug>-books  one document's EPUB + PDFs"
	@echo "  make list          the document slugs <slug> accepts"
	@echo "  make fetch         download missing Vatican HTML snapshots"
	@echo "  make test          unit + extractor regression tests"
	@echo "  make qa            full build, then the site-artifact smoke check"
	@echo "  make check         complete pre-commit gate: test + build + artefact QA"
	@echo "  make clean         drop generated TOML, HTML, and books"

list:
	@printf '%s\n' $(DOCS)

test:
	python3 -m unittest discover -s tests

clean:
	rm -f $(TOMLS) $(HTMLS) site/index.html
	rm -rf build/ site/downloads/
