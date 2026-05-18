.PHONY: help install fmt lint typecheck test test-fast cov run mock-crm clean docker docker-down

PYTHON ?= python3
UV ?= uv

help: ## show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## install deps via uv (preferred) or pip
	@if command -v $(UV) >/dev/null 2>&1; then \
		$(UV) sync --extra dev; \
	else \
		$(PYTHON) -m pip install -e '.[dev]'; \
	fi

fmt: ## format code
	ruff format src tests
	ruff check --fix src tests

lint: ## lint
	ruff check src tests
	ruff format --check src tests

typecheck: ## mypy strict
	mypy src

test: ## run all tests with coverage
	pytest --cov=src --cov-report=term-missing --cov-report=xml

test-fast: ## quick tests, no coverage
	pytest -x -q

cov: ## test + open htmlcov
	pytest --cov=src --cov-report=html
	@command -v open >/dev/null 2>&1 && open htmlcov/index.html || echo "open htmlcov/index.html"

mock-crm: ## start the mock CRM (foreground, port 8765)
	uvicorn mock_crm.server:app --host 127.0.0.1 --port 8765 --reload

run: ## end-to-end demo: ingest samples, parse, push to mock CRM
	agentic-onboard run samples/

run-mock-llm: ## end-to-end demo with the deterministic mock LLM (no API key needed)
	LLM_PROVIDER=mock agentic-onboard run samples/

dlq: ## show DLQ entries from the last run
	agentic-onboard dlq

dlq-replay: ## replay everything in the DLQ
	agentic-onboard dlq replay

clean: ## delete generated artifacts
	rm -rf data/ runs/ .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage coverage.xml
	find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true

docker: ## docker compose up (mock CRM in container)
	docker compose up --build -d

docker-down:
	docker compose down -v
