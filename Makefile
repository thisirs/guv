test:
	uv run pytest -v -rA --cache-clear

doc:
	uv run --group doc sphinx-build --builder html --fail-on-warning docs public
