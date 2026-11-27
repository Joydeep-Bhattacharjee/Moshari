ifeq ($(OS),Windows_NT)
  PY := .venv/Scripts/python
else
  PY := .venv/bin/python
endif

.PHONY: setup validate features eda backtest selection train export report test app exports offline-check

setup:
	python -m venv .venv
	$(PY) -m pip install -r requirements.txt
	npm ci

validate:
	$(PY) -m src.validate

features:
	$(PY) -m src.features

eda:
	$(PY) -m src.eda

backtest:
	$(PY) -m src.backtest

selection:
	$(PY) -m src.selection

train:
	$(PY) -m src.train

export:
	$(PY) -m src.export

report:
	$(PY) -m src.report

test:
	$(PY) -m pytest -q
	npm test

app:
	npm run dev

# Phase 2: commissioner pack for the demo scenario (golden files for offline-check)
exports:
	$(PY) -m src.ops.export_pack

# Phase 2: rebuild the committed pack with sockets blocked, then print the banner
offline-check:
	$(PY) -m pytest -q tests/test_offline.py
	$(PY) -m src.ops.selfcheck
