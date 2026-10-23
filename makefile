.PHONY: all install uninstall test

all: install

# Editable install: changes in this repo take effect without reinstalling.
install:
	uv tool install --force --editable .
	uv tool update-shell

uninstall:
	uv tool uninstall clocktail

test:
	uv run pytest
