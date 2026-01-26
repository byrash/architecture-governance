# Architecture Governance Makefile

.PHONY: validate ingest release

.DEFAULT_GOAL := validate

DOCKER_IMAGE := architecture-governance
GITHUB_USER ?= $(shell git config user.name 2>/dev/null || echo "user")
GHCR_IMAGE := ghcr.io/$(GITHUB_USER)/$(DOCKER_IMAGE)
AUTO_TAG := $(shell date +%Y%m%d-%H%M%S)$(shell git rev-parse --short HEAD 2>/dev/null | sed 's/^/-/')

validate:
	@if [ ! -f .env ]; then echo "Error: .env not found. Run: cp .env.example .env"; exit 1; fi
	@docker build -q -t $(DOCKER_IMAGE) . > /dev/null 2>&1 || docker build -t $(DOCKER_IMAGE) .
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
	@docker build -q -t $(DOCKER_IMAGE) . > /dev/null 2>&1 || docker build -t $(DOCKER_IMAGE) .
	@rm -f governance/output/*.md governance/output/*.html 2>/dev/null || true
ifdef FILE
	@INPUT_FILE=$(FILE) docker-compose run --rm governance ingest
else
	@docker-compose run --rm governance ingest
endif
	@docker-compose down --volumes --remove-orphans 2>/dev/null || true
	@echo "Output: governance/output/architecture.md"

release:
	@docker build -t $(DOCKER_IMAGE):$(AUTO_TAG) -t $(DOCKER_IMAGE):latest .
	@docker save $(DOCKER_IMAGE):$(AUTO_TAG) | gzip > $(DOCKER_IMAGE)-$(AUTO_TAG).tar.gz
	@docker tag $(DOCKER_IMAGE):$(AUTO_TAG) $(GHCR_IMAGE):$(AUTO_TAG)
	@docker tag $(DOCKER_IMAGE):$(AUTO_TAG) $(GHCR_IMAGE):latest
	@docker push $(GHCR_IMAGE):$(AUTO_TAG) || echo "Push failed - run: docker login ghcr.io"
	@docker push $(GHCR_IMAGE):latest 2>/dev/null || true
	@echo "Released: $(AUTO_TAG)"
	@ls -lh $(DOCKER_IMAGE)-$(AUTO_TAG).tar.gz
