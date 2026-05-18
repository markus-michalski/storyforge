VENV := $(HOME)/.storyforge/venv
PYTHON := $(VENV)/bin/python

.PHONY: test lint format check

test:
	$(PYTHON) -m pytest tests/ -v

lint:
	$(PYTHON) -m ruff check .

format:
	$(PYTHON) -m ruff format .

check: lint test
