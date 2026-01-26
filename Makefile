# Architecture Governance Makefile

.PHONY: validate ingest release

.DEFAULT_GOAL := validate

DOCKER_IMAGE := architecture-governance
VERSION := $(shell date +%Y%m%d-%H%M%S)

validate:
	@if [ ! -f .env ]; then echo "Error: .env not found. Run: cp .env.example .env"; exit 1; fi
	@docker build -t $(DOCKER_IMAGE) .
	@rm -f governance/output/*.md governance/output/*.html 2>/dev/null || true
ifdef FILE
	@INPUT_FILE=$(FILE) docker-compose run --rm governance
else
	@docker-compose run --rm governance
endif
	@docker-compose down --volumes --remove-orphans 2>/dev/null || true
	@open governance/output/governance-report.html 2>/dev/null || xdg-open governance/output/governance-report.html 2>/dev/null || true

ingest:
	@if [ ! -f .env ]; then echo "Error: .env not found. Run: cp .env.example .env"; exit 1; fi
	@docker build -t $(DOCKER_IMAGE) .
	@rm -f governance/output/*.md governance/output/*.html 2>/dev/null || true
ifdef FILE
	@INPUT_FILE=$(FILE) docker-compose run --rm governance ingest
else
	@docker-compose run --rm governance ingest
endif
	@docker-compose down --volumes --remove-orphans 2>/dev/null || true
	@echo "Output: governance/output/architecture.md"

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
		--notes "Docker image for architecture governance validation. Import with: gunzip -c $(DOCKER_IMAGE)-$(VERSION).tar.gz | docker load"
	@echo ""
	@echo "Released: v$(VERSION)"
	@echo "To import: gunzip -c $(DOCKER_IMAGE)-$(VERSION).tar.gz | docker load"
