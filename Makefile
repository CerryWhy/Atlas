# Wrapper sottile: la logica vive negli script npm, che funzionano anche senza make (Windows).
.PHONY: dev pipeline types check test

dev:
	npm run dev

pipeline:
	npm run pipeline

types:
	npm run gen:types

check:
	.venv/bin/ruff check api pipeline tests && .venv/bin/mypy api pipeline
	npm --prefix web run typecheck && npm --prefix web run lint

test:
	.venv/bin/pytest
	npm --prefix web test
