# Plexus Development Makefile

# Check Python version
PYTHON_VERSION := $(shell python --version 2>&1)
REQUIRED_PYTHON := 3.11

.PHONY: check-python
check-python:
	@echo "Current Python version: $(PYTHON_VERSION)"
	@if ! echo "$(PYTHON_VERSION)" | grep -q "Python $(REQUIRED_PYTHON)"; then \
		echo "❌ ERROR: This project requires Python 3.11"; \
		echo "Current version: $(PYTHON_VERSION)"; \
		echo ""; \
		echo "To fix this:"; \
		echo "  1. Install pyenv: curl https://pyenv.run | bash"; \
		echo "  2. Install Python 3.11: pyenv install 3.11.13"; \
		echo "  3. Set local version: pyenv local 3.11.13"; \
		echo "  4. Verify: python --version"; \
		exit 1; \
	else \
		echo "✅ Python version is correct"; \
	fi

.PHONY: setup
setup: check-python
	@echo "Setting up development environment..."
	pip install --upgrade pip
	pip install -e .
	@echo "✅ Setup complete!"

.PHONY: test
test: check-python
	@echo "Running all tests..."
	python -m pytest -v

.PHONY: test-coverage
test-coverage: check-python
	@echo "Running tests with coverage..."
	python -m pytest --cov=. --cov-report=term --cov-report=html -v
	@echo "📊 Coverage report generated in htmlcov/"

.PHONY: test-mcp
test-mcp: check-python
	@echo "Running MCP server tests..."
	cd MCP && python -m pytest plexus_fastmcp_server_test.py --cov=plexus_fastmcp_server --cov-report=term -v

.PHONY: serve-coverage
serve-coverage:
	@echo "Serving coverage report at http://localhost:8000"
	cd htmlcov && python -m http.server 8000

.PHONY: clean
clean:
	@echo "Cleaning up..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf htmlcov/ .coverage .pytest_cache/ 2>/dev/null || true
	@echo "✅ Cleanup complete!"

.PHONY: help
help:
	@echo "Plexus Development Commands:"
	@echo ""
	@echo "  make check-python     - Verify Python 3.11 is being used"
	@echo "  make setup           - Set up development environment"
	@echo "  make test            - Run all tests"
	@echo "  make test-coverage   - Run tests with coverage report"
	@echo "  make test-mcp        - Run MCP server tests specifically"
	@echo "  make serve-coverage  - Serve coverage report on localhost:8000"
	@echo "  make clean           - Clean up generated files"
	@echo "  make help            - Show this help message"
	@echo ""
	@echo "Quick start:"
	@echo "  make setup && make test-coverage"

# Default target
.DEFAULT_GOAL := help