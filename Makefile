test:
	uv run pytest -v -rA --cache-clear

doc:
	uv run --with '.[doc]' sphinx-build --builder html --fail-on-warning docs public
