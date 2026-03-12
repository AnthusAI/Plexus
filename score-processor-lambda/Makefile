.PHONY: help test test-unit test-smoke build clean

# Configuration
IMAGE_NAME := score-processor-lambda
IMAGE_TAG := latest

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

test: test-unit test-smoke ## Run all tests (unit + smoke)

test-unit: ## Run pytest unit tests
	@echo "Running unit tests..."
	cd .. && PYTHONPATH=score-processor-lambda pytest score-processor-lambda/tests/test_*.py -v

test-smoke: build ## Run smoke test in container
	@echo "Running smoke test in container..."
	docker run --rm \
		-v $(PWD)/tests/smoke_test.py:/var/task/smoke_test.py \
		--entrypoint python \
		$(IMAGE_NAME):$(IMAGE_TAG) \
		smoke_test.py

build: ## Build Docker image locally for testing
	@echo "Building Docker image..."
	cd .. && docker buildx build \
		--platform linux/amd64 \
		--load \
		-f score-processor-lambda/Dockerfile \
		-t $(IMAGE_NAME):$(IMAGE_TAG) \
		.
	@echo "✓ Image built: $(IMAGE_NAME):$(IMAGE_TAG)"

build-and-test: build test-smoke ## Build image and run smoke test

clean: ## Remove local Docker images
	@echo "Cleaning up..."
	docker rmi $(IMAGE_NAME):$(IMAGE_TAG) 2>/dev/null || true
	@echo "✓ Cleanup complete"

info: ## Show current configuration
	@echo "Configuration:"
	@echo "  Image: $(IMAGE_NAME):$(IMAGE_TAG)"
	@echo "  Platform: linux/amd64"
	@echo ""
	@echo "Local images:"
	@docker images $(IMAGE_NAME) 2>/dev/null || echo "  No local images found"
