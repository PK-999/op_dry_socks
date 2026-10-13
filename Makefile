PYTHON ?= .venv/bin/python
NODE ?= node

.PHONY: setup dev demo run monitor check test browser live format

setup:
	python3 -m venv .venv
	$(PYTHON) -m pip install -r requirements.txt

dev:
	$(PYTHON) -m pip install -r requirements-dev.txt
	$(PYTHON) -m playwright install chromium

demo:
	$(PYTHON) server.py --demo

run:
	$(PYTHON) server.py

monitor:
	$(PYTHON) main.py --watch

test:
	$(PYTHON) -m pytest -q
	$(NODE) --test tests/test_*.js

check: test
	$(PYTHON) -m ruff check main.py server.py e2e_test.py services tests
	$(PYTHON) -m ruff format --check main.py server.py e2e_test.py services tests
	$(PYTHON) -m compileall -q main.py server.py services tests
	$(NODE) --check web/app.js
	$(NODE) --check web/api.js
	$(NODE) --check web/map.js
	$(NODE) --check web/ambient.js
	$(NODE) --check web/theme.js
	bash -n install.sh uninstall.sh

browser:
	$(PYTHON) tests/browser/google_places.py
	$(PYTHON) tests/browser/dashboard.py

live:
	$(PYTHON) e2e_test.py --live

format:
	$(PYTHON) -m ruff check --fix main.py server.py e2e_test.py services tests
	$(PYTHON) -m ruff format main.py server.py e2e_test.py services tests
