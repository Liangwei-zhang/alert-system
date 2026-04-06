.PHONY: help run-local docker-build docker-up docker-down k8s-apply k8s-delete logs logs-worker test test-all mutation-test property-test chaos-test benchmark

help:
	@echo "Stock Python Deployment Makefile"
	@echo ""
	@echo "Available targets:"
	@echo "  run-local       - Run application locally (without Docker)"
	@echo "  docker-build    - Build Docker images"
	@echo "  docker-up       - Start all services with docker-compose"
	@echo "  docker-down     - Stop all services"
	@echo "  docker-logs     - View logs (specify SERVICE=public_api, etc.)"
	@echo "  k8s-apply       - Apply Kubernetes manifests"
	@echo "  k8s-delete      - Delete all Kubernetes resources"
	@echo "  k8s-logs        - View K8s logs (specify COMPONENT=public-api, etc.)"
	@echo "  test            - Run unit tests"
	@echo "  test-all        - Run all tests"
	@echo "  mutation-test   - Run mutation tests"
	@echo "  property-test   - Run property-based tests"
	@echo "  chaos-test      - Run chaos resilience tests"
	@echo "  benchmark       - Run performance benchmarks"

# Local development (requires dependencies installed)
run-local:
	@echo "Starting local development..."
	@echo "Prerequisites: PostgreSQL, Redis, Kafka running locally"
	@echo "Install: pip install -r requirements.txt"
	@echo "Run: uvicorn apps.public_api.main:app --reload"

# Docker build
docker-build:
	@echo "Building Docker images..."
	docker-compose build

# Docker up
docker-up:
	@echo "Starting all services..."
	docker-compose up -d
	@echo ""
	@echo "Services started:"
	@echo "  Public API:  http://localhost:8000"
	@echo "  Admin API:   http://localhost:8001"
	@echo "  Flower:      http://localhost:5555"
	@echo "  PostgreSQL:  localhost:5432"
	@echo "  Redis:       localhost:6379"
	@echo "  Kafka:       localhost:9092"

# Docker down
docker-down:
	@echo "Stopping all services..."
	docker-compose down

# Docker logs
docker-logs:
ifneq ($(SERVICE),)
	docker-compose logs -f $(SERVICE)
else
	docker-compose logs -f
endif

# Kubernetes apply
k8s-apply:
	@echo "Applying Kubernetes manifests..."
	kubectl apply -f k8s/
	@echo ""
	@echo "Verify: kubectl get pods -l app=stock-python"

# Kubernetes delete
k8s-delete:
	@echo "Deleting Kubernetes resources..."
	kubectl delete -f k8s/ --ignore-not-found

# Kubernetes logs
k8s-logs:
ifneq ($(COMPONENT),)
	kubectl logs -l app=stock-python,component=$(COMPONENT) -f
else
	@echo "Usage: make k8s-logs COMPONENT=public-api"
endif

# Test targets
test:
	pytest tests/unit/ -v

test-all:
	pytest tests/ -v

mutation-test:
	pytest tests/mutation/ -v

property-test:
	pytest tests/property/ -v --hypothesis-show-statistics

chaos-test:
	pytest tests/chaos/ -v

benchmark:
	pytest tests/benchmark/ -v --benchmark-only
