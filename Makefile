ifeq ($(OS),Windows_NT)
  PY := .venv/Scripts/python
else
  PY := .venv/bin/python
endif

.PHONY: setup validate features train test app

setup:
	python -m venv .venv
	$(PY) -m pip install -r requirements.txt

validate:
	$(PY) -m src.validate

features:
	$(PY) -m src.features

train:
	$(PY) -m src.train

test:
	$(PY) -m pytest -q

app:
	$(PY) -m streamlit run app.py
