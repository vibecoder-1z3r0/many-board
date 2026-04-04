.DEFAULT_GOAL := help

.PHONY: help install run dev test lint format typecheck fix check

help:
	@echo "Usage: make <target>"
	@echo ""
	@echo "  install    Install dependencies via uv"
	@echo "  run        Start the server (http://0.0.0.0:8000)"
	@echo "  dev        Start the server with auto-reload"
	@echo "  test       Run test suite"
	@echo "  lint       Check linting (ruff)"
	@echo "  format     Check formatting (ruff format)"
	@echo "  typecheck  Run type checker (mypy)"
	@echo "  fix        Auto-fix lint and format issues"
	@echo "  check      Run all CI checks (lint + format + typecheck + tests)"

install:
	uv sync --all-extras

run:
	uv run uvicorn manyboard.main:app --host 0.0.0.0 --port 8000

dev:
	uv run uvicorn manyboard.main:app --host 0.0.0.0 --port 8000 --reload

test:
	uv run pytest --tb=short -v

lint:
	uv run ruff check .

format:
	uv run ruff format --check .

typecheck:
	uv run mypy src/

fix:
	uv run ruff check --fix .
	uv run ruff format .

check: lint format typecheck test
