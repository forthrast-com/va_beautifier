DOCS  := gaudium_et_spes laudato_si magnifica_humanitas antiqua_et_nova \
         quo_vadis_humanitas sacrosanctum_concilium fides_et_ratio \
         lumen_fidei verbum_domini deus_caritas_est spe_salvi \
         caritas_in_veritate ecclesia_in_oceania
HTMLS := $(DOCS:%=site/%.html)
TOMLS := $(DOCS:%=build/%.toml)
EPUBS := $(DOCS:%=site/downloads/%.epub)
PDFS  := $(DOCS:%=site/downloads/%-a4.pdf) \
         $(DOCS:%=site/downloads/%-a5.pdf) \
         $(DOCS:%=site/downloads/%-a6.pdf)
BOOKS := $(EPUBS) $(PDFS)

.PHONY: all fetch books site qa clean

# `all` builds the books first so the landing page can report current
# PDF/EPUB sizes; the index target depends on every HTML rendered too.
all: books site/index.html

fetch:
	python3 download_sources.py --category implemented

# Source snapshots are fetched on demand too, so a build target can pull the
# missing Vatican HTML rather than failing at the first absent prerequisite.
define FETCH_SOURCE
$1: download_sources.py
	python3 download_sources.py $2
endef

$(eval $(call FETCH_SOURCE,sources/gaudium_et_spes_en.html,gaudium_et_spes_en))
$(eval $(call FETCH_SOURCE,sources/gaudium_et_spes_lt.html,gaudium_et_spes_lt))
$(eval $(call FETCH_SOURCE,sources/laudato_si_en.html,laudato_si_en))
$(eval $(call FETCH_SOURCE,sources/laudato_si_lt.html,laudato_si_lt))
$(eval $(call FETCH_SOURCE,sources/magnifica_humanitas_en.html,magnifica_humanitas_en))
$(eval $(call FETCH_SOURCE,sources/fides_et_ratio_en.html,fides_et_ratio_en))
$(eval $(call FETCH_SOURCE,sources/lumen_fidei_en.html,lumen_fidei_en))
$(eval $(call FETCH_SOURCE,sources/verbum_domini_en.html,verbum_domini_en))
$(eval $(call FETCH_SOURCE,sources/deus_caritas_est_en.html,deus_caritas_est_en))
$(eval $(call FETCH_SOURCE,sources/spe_salvi_en.html,spe_salvi_en))
$(eval $(call FETCH_SOURCE,sources/caritas_in_veritate_en.html,caritas_in_veritate_en))
$(eval $(call FETCH_SOURCE,sources/ecclesia_in_oceania_en.html,ecclesia_in_oceania_en))
$(eval $(call FETCH_SOURCE,sources/Fratelli\ tutti_en.html,fratelli_tutti_en))
$(eval $(call FETCH_SOURCE,sources/Sacrosanctum\ Concilium_en.html,sacrosanctum_concilium_en))
$(eval $(call FETCH_SOURCE,sources/Sacrosanctum\ Concilium_la.html,sacrosanctum_concilium_lt))
$(eval $(call FETCH_SOURCE,sources/antiqua_et_nova_en.html,antiqua_et_nova_en))
$(eval $(call FETCH_SOURCE,sources/quo_vadis_humanitas_en.html,quo_vadis_humanitas_en))
$(eval $(call FETCH_SOURCE,sources/Participation\ of\ the\ Holy\ Father\ Francis\ at\ the\ G7\ in\ Borgo\ Egnazia\ \(Puglia\)\ \(14\ June\ 2024\).html,francis_g7_ai_en))

qa: all
	VA_REQUIRE_SITE_ARTIFACTS=1 python3 -m unittest tests.test_site_artifacts -v

# --- TOML targets (explicit: each doc has distinct source deps) ---

build/gaudium_et_spes.toml: sources/gaudium_et_spes_en.html sources/gaudium_et_spes_lt.html \
                             extract/gaudium_et_spes.py extract/_oldflat.py core.py
	python3 parse.py gaudium_et_spes

build/laudato_si.toml: sources/laudato_si_en.html \
                       extract/laudato_si.py extract/_modern.py core.py
	python3 parse.py laudato_si

build/magnifica_humanitas.toml: sources/magnifica_humanitas_en.html \
                                extract/magnifica_humanitas.py extract/_modern.py core.py
	python3 parse.py magnifica_humanitas

build/antiqua_et_nova.toml: sources/antiqua_et_nova_en.html \
                            extract/antiqua_et_nova.py extract/_curia.py core.py
	python3 parse.py antiqua_et_nova

build/quo_vadis_humanitas.toml: sources/quo_vadis_humanitas_en.html \
                                extract/quo_vadis_humanitas.py extract/_curia.py core.py
	python3 parse.py quo_vadis_humanitas

build/sacrosanctum_concilium.toml: sources/Sacrosanctum\ Concilium_en.html \
                                    extract/sacrosanctum_concilium.py extract/_oldflat.py core.py
	python3 parse.py sacrosanctum_concilium

build/fides_et_ratio.toml: sources/fides_et_ratio_en.html \
                           extract/fides_et_ratio.py extract/_modern.py core.py
	python3 parse.py fides_et_ratio

build/lumen_fidei.toml: sources/lumen_fidei_en.html \
                        extract/lumen_fidei.py extract/_modern.py core.py
	python3 parse.py lumen_fidei

build/verbum_domini.toml: sources/verbum_domini_en.html \
                          extract/verbum_domini.py extract/_modern.py core.py
	python3 parse.py verbum_domini

build/deus_caritas_est.toml: sources/deus_caritas_est_en.html \
                             extract/deus_caritas_est.py extract/_modern.py core.py
	python3 parse.py deus_caritas_est

build/spe_salvi.toml: sources/spe_salvi_en.html \
                      extract/spe_salvi.py extract/_modern.py core.py
	python3 parse.py spe_salvi

build/caritas_in_veritate.toml: sources/caritas_in_veritate_en.html \
                                extract/caritas_in_veritate.py extract/_modern.py core.py
	python3 parse.py caritas_in_veritate

build/ecclesia_in_oceania.toml: sources/ecclesia_in_oceania_en.html \
                                extract/ecclesia_in_oceania.py extract/_modern.py core.py
	python3 parse.py ecclesia_in_oceania

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

clean:
	rm -f $(TOMLS) $(HTMLS) site/index.html
	rm -rf build/ site/downloads/
