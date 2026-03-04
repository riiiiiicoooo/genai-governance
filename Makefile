.PHONY: help install test lint format clean run demo docker-build docker-up docker-down

help:
	@echo "GenAI Governance Platform - Commands"
	@echo "===================================="
	@echo "make install       - Install dependencies"
	@echo "make test          - Run test suite"
	@echo "make test-guardrails - Run guardrail tests only"
	@echo "make test-registry - Run prompt registry tests only"
	@echo "make test-coverage - Run tests with coverage report"
	@echo "make lint          - Run code quality checks"
	@echo "make format        - Auto-format code"
	@echo "make clean         - Remove build artifacts"
	@echo "make run           - Run FastAPI server"
	@echo "make demo          - Run demonstration script"
	@echo "make docker-build  - Build Docker image"
	@echo "make docker-up     - Start Docker containers (docker-compose)"
	@echo "make docker-down   - Stop Docker containers"

install:
	pip install -r requirements.txt

test:
	pytest tests/ -v --tb=short

test-guardrails:
	pytest tests/test_guardrails.py -v

test-registry:
	pytest tests/test_prompt_registry.py -v

test-coverage:
	pytest tests/ --cov=src --cov-report=html --cov-report=term-missing

lint:
	black --check src/ tests/ demo/
	flake8 src/ tests/ demo/ --max-line-length=100
	mypy src/ --ignore-missing-imports

format:
	black src/ tests/ demo/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	rm -f .coverage

run:
	uvicorn api.app:app --reload --host 0.0.0.0 --port 8000

demo:
	python demo/run_governance_pipeline.py

docker-build:
	docker build -t genai-governance:latest .

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

.DEFAULT_GOAL := help
