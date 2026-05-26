DOCS  := gaudium_et_spes laudato_si magnifica_humanitas antiqua_et_nova \
         quo_vadis_humanitas sacrosanctum_concilium
HTMLS := $(DOCS:%=site/%.html)
TOMLS := $(DOCS:%=build/%.toml)
EPUBS := $(DOCS:%=build/%.epub)
PDFS  := $(DOCS:%=build/%.pdf)

.PHONY: all fetch books site clean

# `all` builds the books first so the landing page can report current
# PDF/EPUB sizes; the index target depends on every HTML rendered too.
all: books site/index.html

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

build/antiqua_et_nova.toml: sources/antiqua_et_nova_en.html \
                            extract/antiqua_et_nova.py curia.py core.py
	python3 parse.py antiqua_et_nova

build/quo_vadis_humanitas.toml: sources/quo_vadis_humanitas_en.html \
                                extract/quo_vadis_humanitas.py curia.py core.py
	python3 parse.py quo_vadis_humanitas

build/sacrosanctum_concilium.toml: sources/Sacrosanctum\ Concilium_en.html \
                                    extract/sacrosanctum_concilium.py core.py
	python3 parse.py sacrosanctum_concilium

# --- HTML targets ---

site/%.html: build/%.toml make_html.py assets/styles.css assets/scripts.js
	python3 make_html.py $*

site/index.html: $(HTMLS) $(EPUBS) make_index.py
	python3 make_index.py $(DOCS)

# --- Books (requires pandoc + typst) ---

books: $(EPUBS)

build/%.epub: build/%.toml make_book.py templates/book.typ
	python3 make_book.py $*

# `make books` emits an .epub and a .pdf in one shot; declare the pdf as
# a side-effect of its epub sibling so explicit `make build/foo.pdf` works.
build/%.pdf: build/%.epub
	@:

# --- Housekeeping ---

clean:
	rm -f $(TOMLS) $(HTMLS) site/index.html
	rm -rf build/
