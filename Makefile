PYTHON ?= python3

.PHONY: data render preview all check

data:
	$(PYTHON) scripts/build_data.py

render:
	quarto render

preview:
	quarto preview --no-browser

check:
	$(PYTHON) -m unittest discover -s tests -v

all: check data render

