# Makefile for AI Council Orchestrator
# Run `make help` to see available commands

.PHONY: help install install-dev test lint format type-check clean build docs pre-commit

# Default target
help:
	@echo "AI Council Orchestrator - Development Commands"
	@echo "=============================================="
	@echo ""
	@echo "Setup:"
	@echo "  make install       Install production dependencies"
	@echo "  make install-dev   Install development dependencies"
	@echo "  make pre-commit    Install and setup pre-commit hooks"
	@echo ""
	@echo "Quality:"
	@echo "  make lint          Run linting checks (flake8)"
	@echo "  make format        Format code with black and isort"
	@echo "  make type-check    Run type checking (mypy)"
	@echo "  make check         Run all quality checks"
	@echo ""
	@echo "Testing:"
	@echo "  make test          Run all tests with coverage"
	@echo "  make test-fast     Run tests without coverage"
	@echo "  make test-unit     Run unit tests only"
	@echo ""
	@echo "Build:"
	@echo "  make build         Build distribution packages"
	@echo "  make clean         Remove build artifacts"
	@echo ""

# Setup targets
install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"
	@echo "\n✓ Development dependencies installed"

pre-commit:
	pip install pre-commit
	pre-commit install
	@echo "\n✓ Pre-commit hooks installed"

# Quality targets
lint:
	@echo "Running flake8..."
	flake8 ai_council/ --count --select=E9,F63,F7,F82 --show-source --statistics
	flake8 ai_council/ --count --exit-zero --max-complexity=10 --max-line-length=88 --statistics

format:
	@echo "Running black..."
	black ai_council/ tests/
	@echo "Running isort..."
	isort ai_council/ tests/
	@echo "\n✓ Code formatted"

type-check:
	@echo "Running mypy..."
	mypy ai_council/ --ignore-missing-imports

check: lint type-check
	@echo "\n✓ All quality checks passed"

# Testing targets
test:
	python -m pytest tests/ -v --cov=ai_council --cov-report=term-missing --cov-report=html

test-fast:
	python -m pytest tests/ -v

test-unit:
	python -m pytest tests/ -v -m unit

# Build targets
build: clean
	pip install build
	python -m build
	@echo "\n✓ Package built in dist/"

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf coverage.xml
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@echo "✓ Cleaned build artifacts"

# Run the web app
run-web:
	python -m uvicorn web_app.backend.main:app --reload --port 8000

# Run example
run-example:
	python examples/mode_comparison_example.py
