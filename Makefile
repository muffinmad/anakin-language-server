SHELL = /bin/bash
PYTHON = python


.PHONY: clean
clean:
	find . -path "*/__pycache__/*" -delete
	find . -type d -empty -delete


.PHONY: install
install: clean
	$(PYTHON) -m pip install -r requirements.txt


.PHONY: check
check:
	ruff format --check .
	ruff check .

.PHONY: test
test:
	$(PYTHON) -m pytest
