
all:
	uv tool install --force --reinstall .

test:
	uv run pytest
