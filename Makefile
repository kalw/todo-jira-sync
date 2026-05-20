.PHONY: help install lint format typecheck test check run docker docker-run clean

help:
	@echo "Targets:"
	@echo "  install    Create the venv and install in editable mode (uv)"
	@echo "  lint       Run ruff"
	@echo "  format     Auto-fix with ruff"
	@echo "  typecheck  Run mypy"
	@echo "  test       Run the test suite (pytest)"
	@echo "  check      lint + typecheck + test"
	@echo "  run        Run the CLI (pass ARGS=...)"
	@echo "  docker     Build the container image"
	@echo "  clean      Remove caches and build artifacts"

install:
	uv venv
	uv pip install -e ".[dev]"

lint:
	uv run ruff check .

format:
	uv run ruff check --fix .
	uv run ruff format .

typecheck:
	uv run mypy todo_jira_sync

test:
	uv run pytest

check: lint typecheck test

run:
	uv run todo-jira-sync $(ARGS)

VERSION ?= 0.0.0
docker:
	docker build --build-arg VERSION=$(VERSION) -t todo-jira-sync:local .

docker-run:
	docker run --rm --env-file .env -v "$(PWD):/work" todo-jira-sync:local $(ARGS)

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache build dist *.egg-info
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
