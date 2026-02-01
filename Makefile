# Architecture Governance Makefile

.PHONY: help ingest validate clean release

.DEFAULT_GOAL := help

DOCKER_IMAGE := architecture-governance
VERSION := $(shell date +%Y%m%d-%H%M%S)

help:
	@echo "Architecture Governance"
	@echo ""
	@echo "Commands:"
	@echo "  make ingest PAGE_ID=123456789              Ingest via @ingestion-agent"
	@echo "  make ingest PAGE_ID=123456789 INDEX=patterns   Ingest to index"
	@echo "  make validate PAGE_ID=123456789            Validate via @governance-agent"
	@echo "  make clean                                 Clear output folder"
	@echo "  make release                               Build and release Docker image"
	@echo ""
	@echo "All commands trigger agents via Copilot CLI in Docker."

ingest:
	@if [ ! -f .env ]; then echo "Error: .env not found. Run: cp .env.example .env"; exit 1; fi
ifndef PAGE_ID
	@echo "Error: PAGE_ID required. Usage: make ingest PAGE_ID=123456789"
	@exit 1
endif
	@echo "Building Docker image..."
	@docker build -t $(DOCKER_IMAGE) .
	@echo "Triggering @ingestion-agent..."
ifdef INDEX
	@PAGE_ID=$(PAGE_ID) docker-compose run --rm governance ingest $(INDEX)
else
	@PAGE_ID=$(PAGE_ID) docker-compose run --rm governance ingest
endif
	@docker-compose down --volumes --remove-orphans 2>/dev/null || true

validate:
	@if [ ! -f .env ]; then echo "Error: .env not found. Run: cp .env.example .env"; exit 1; fi
ifndef PAGE_ID
	@echo "Error: PAGE_ID required. Usage: make validate PAGE_ID=123456789"
	@exit 1
endif
	@echo "Building Docker image..."
	@docker build -t $(DOCKER_IMAGE) .
	@echo "Triggering @governance-agent..."
	@PAGE_ID=$(PAGE_ID) docker-compose run --rm governance validate
	@docker-compose down --volumes --remove-orphans 2>/dev/null || true

clean:
	@rm -rf governance/output/*/
	@echo "Cleaned governance/output/"

release:
	@echo "Building and releasing version: $(VERSION)"
	@docker build -t $(DOCKER_IMAGE):$(VERSION) -t $(DOCKER_IMAGE):latest .
	@echo "Exporting image..."
	@docker save $(DOCKER_IMAGE):$(VERSION) | gzip > $(DOCKER_IMAGE)-$(VERSION).tar.gz
	@ls -lh $(DOCKER_IMAGE)-$(VERSION).tar.gz
	@echo ""
	@echo "Creating GitHub release v$(VERSION)..."
	@if ! command -v gh &> /dev/null; then \
		echo "Error: GitHub CLI (gh) not installed. Install with: brew install gh"; \
		exit 1; \
	fi
	@if ! gh auth status &> /dev/null; then \
		echo "Error: Not logged in to GitHub. Run: gh auth login"; \
		exit 1; \
	fi
	@gh release create v$(VERSION) \
		$(DOCKER_IMAGE)-$(VERSION).tar.gz \
		--title "Architecture Governance v$(VERSION)" \
		--notes "Docker image for architecture governance validation."
	@echo ""
	@echo "Released: v$(VERSION)"
