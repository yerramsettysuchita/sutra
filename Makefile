# SUTRA
#
# Written for GNU make on a POSIX shell. It is not executed in the authoring
# environment, which has no make, so every recipe is a single portable command
# with no shell builtins, no pipelines and no bashisms. `make -n` and
# `scripts/check_makefile.py` verify the syntax and that every referenced entry
# point imports.

PYTHON  ?= python3
CASES   ?= 5000
FULL    ?= 150000
CORPUS  ?= data/corpus
CO      ?= moderate

.DEFAULT_GOAL := help
.PHONY: help all deps gen gen-full stats block resolve downstream reconcile persons eval questions db validate-sql docs vocab scale export build serve package dev test check clean

help:
	@echo "SUTRA"
	@echo ""
	@echo "  make gen        synthetic corpus, $(CASES) cases, fast development default"
	@echo "  make gen-full   synthetic corpus, $(FULL) cases, the full corpus"
	@echo "  make stats      corpus statistics and the recoverability audit"
	@echo "  make block      Layer 1 normalisation and Layer 2 blocking measurement"
	@echo "  make resolve    Layers 3 to 7, writes the resolved identity table"
	@echo "  make persons    the same engine over Victim and ComplainantDetails"
	@echo "  make downstream Layer 8, graph, communities, profiles, undetected cases"
	@echo "  make reconcile  Layer 9, IPC to BNS counting across July 2024"
	@echo "  make eval       evaluation report into eval/report.json"
	@echo "  make questions  score the 150 question investigator set"
	@echo "  make validate-sql  execute all 150 gold queries against real SQLite"
	@echo "  make docs       regenerate README.md and docs/build-status.md"
	@echo "  make export     refresh the web client data feeds"
	@echo "  make test       unit tests"
	@echo "  make check      verify the Makefile, its entry points, and source encoding"
	@echo "  make dev        web client on http://localhost:5173"
	@echo "  make build      static bundle into web/dist, verified for Catalyst"
	@echo "  make serve      serve web/dist with no backend, as Catalyst does"
	@echo "  make package    Catalyst deploy zip into catalyst/sutra.zip"
	@echo ""
	@echo "  make all        the whole chain from an empty corpus"
	@echo ""
	@echo "  CASES=$(CASES)  FULL=$(FULL)  CO=$(CO)  PYTHON=$(PYTHON)"

## ---------------------------------------------------------------- implemented

gen:
	$(PYTHON) -m data.generator.generate --cases $(CASES) --co-offending $(CO) --out $(CORPUS)

gen-full:
	$(PYTHON) -m data.generator.generate --cases $(FULL) --co-offending $(CO) --out $(CORPUS)

stats:
	$(PYTHON) -m data.generator.audit --corpus $(CORPUS)

block:
	$(PYTHON) -m engine.block.evaluate --corpus $(CORPUS)

test:
	$(PYTHON) -m unittest discover -s tests -t . -v

check:
	$(PYTHON) scripts/check_makefile.py
	$(PYTHON) scripts/check_encoding.py
	$(PYTHON) scripts/check_freshness.py

dev:
	npm --prefix web install
	npm --prefix web run dev

build:
	npm --prefix web install
	npm --prefix web run build

serve:
	npm --prefix web run serve:static

## ------------------------------------------------------------ not implemented
## These fail rather than succeeding quietly, so an evaluator is never handed a
## stale artefact and told it is current.

resolve:
	$(PYTHON) -m engine.resolve --corpus $(CORPUS)

persons:
	$(PYTHON) -m engine.resolve_other --corpus $(CORPUS)

downstream:
	$(PYTHON) -m engine.downstream.run --corpus $(CORPUS)

reconcile:
	$(PYTHON) -m engine.reconcile.run --corpus $(CORPUS)

eval:
	$(PYTHON) -m eval.report --corpus $(CORPUS)

questions:
	$(PYTHON) -m eval.questions

db:
	$(PYTHON) -m eval.build_db

validate-sql:
	$(PYTHON) -m eval.build_db --quiet
	$(PYTHON) -m eval.validate_sql

docs:
	$(PYTHON) scripts/build_readme.py
	$(PYTHON) scripts/build_status_md.py
	$(PYTHON) scripts/build_leaderboard.py

vocab:
	$(PYTHON) scripts/vocabulary_study.py

scale:
	$(PYTHON) scripts/scale_study.py

export:
	$(PYTHON) scripts/export_web.py --force

deps:
	$(PYTHON) -m pip install -r requirements.txt

all:
	$(PYTHON) -m data.generator.generate --cases $(CASES) --co-offending $(CO) --out $(CORPUS)
	$(PYTHON) -m data.generator.audit --corpus $(CORPUS)
	$(PYTHON) -m engine.block.evaluate --corpus $(CORPUS)
	$(PYTHON) -m engine.resolve --corpus $(CORPUS) --quiet
	$(PYTHON) -m engine.resolve_other --corpus $(CORPUS) --quiet
	$(PYTHON) -m engine.downstream.run --corpus $(CORPUS) --quiet
	$(PYTHON) -m engine.reconcile.run --corpus $(CORPUS) --quiet
	$(PYTHON) -m eval.report --corpus $(CORPUS)
	$(PYTHON) -m eval.questions --quiet
	$(PYTHON) -m eval.build_db --quiet
	$(PYTHON) -m eval.validate_sql --quiet
	$(PYTHON) scripts/export_web.py --force
	$(PYTHON) scripts/build_readme.py
	$(PYTHON) scripts/build_status_md.py
	$(PYTHON) scripts/build_leaderboard.py

package:
	$(PYTHON) scripts/package_catalyst.py

clean:
	$(PYTHON) -c "import shutil; shutil.rmtree('$(CORPUS)', ignore_errors=True)"
