
.PHONY: install test clean

install:
	python -m pip install -r requirements.txt

test:
	python -m pytest -v

clean:
	python -c "import shutil; from pathlib import Path; [shutil.rmtree(p, ignore_errors=True) for p in Path('.').rglob('__pycache__')]; shutil.rmtree('.pytest_cache', ignore_errors=True)"
