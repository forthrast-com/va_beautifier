DOCS  := gaudium_et_spes laudato_si magnifica_humanitas
HTMLS := $(DOCS:%=site/%.html)
TOMLS := $(DOCS:%=build/%.toml)

.PHONY: all fetch books clean

all: site/index.html

fetch:
	python3 download_sources.py --category implemented

# --- TOML targets (explicit: each doc has distinct source deps) ---

build/gaudium_et_spes.toml: sources/gaudium_et_spes_en.html sources/gaudium_et_spes_lt.html \
                             extract/gaudium_et_spes.py core.py
	python3 parse.py gaudium_et_spes

build/laudato_si.toml: sources/laudato_si_en.html \
                       extract/laudato_si.py core.py
	python3 parse.py laudato_si

build/magnifica_humanitas.toml: sources/magnifica_humanitas_en.html \
                                extract/magnifica_humanitas.py core.py
	python3 parse.py magnifica_humanitas

# --- HTML targets ---

site/%.html: build/%.toml make_html.py assets/styles.css assets/scripts.js
	python3 make_html.py $*

site/index.html: $(HTMLS) make_index.py
	python3 make_index.py $(DOCS)

# --- Books (requires pandoc + typst) ---

books: $(DOCS:%=build/%.epub) $(DOCS:%=build/%.pdf)

build/%.epub build/%.pdf &: build/%.toml make_book.py templates/book.typ
	python3 make_book.py $*

# --- Housekeeping ---

clean:
	rm -f $(HTMLS) site/index.html
	rm -rf build/
