ifeq ($(OS),Windows_NT)
  PY := .venv/Scripts/python
else
  PY := .venv/bin/python
endif

.PHONY: setup validate features eda backtest selection train report test app

setup:
	python -m venv .venv
	$(PY) -m pip install -r requirements.txt

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

report:
	$(PY) -m src.report

test:
	$(PY) -m pytest -q

app:
	$(PY) -m streamlit run app.py
