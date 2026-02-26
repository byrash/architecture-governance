# Architecture Governance Makefile

.PHONY: help serve stop ingest validate clean release add-skill update-skills remove-skill list-skills check-rules check-rules-all refresh-rules extract-rules extract-rules-all

.DEFAULT_GOAL := help

DOCKER_IMAGE := architecture-governance
VERSION := $(shell date +%Y%m%d-%H%M%S)

help:
	@echo "Architecture Governance"
	@echo ""
	@echo "Governance Commands:"
	@echo "  make serve                                     Start watcher UI (Ctrl+C to stop)"
	@echo "  make stop                                      Kill any running governance server"
	@echo "  make ingest PAGE_ID=123456789                  Ingest Confluence page"
	@echo "  make ingest PAGE_ID=123456789 INDEX=patterns   Ingest to governance/indexes/<index>/<PAGE_ID>/"
	@echo "  make validate PAGE_ID=123456789                Validate via @governance-agent"
	@echo "  make clean                                     Clear output folder"
	@echo "  make release                                   Build and release Docker image"
	@echo ""
	@echo "Skill Management Commands:"
	@echo "  make add-skill REPO=<url> NAME=<name>                    Add external skill (SKILL.md at repo root)"
	@echo "  make add-skill REPO=<url> NAME=<name> SKILL_PATH=<path> Add external skill (nested SKILL.md)"
	@echo "  make update-skills                                       Update all external skills"
	@echo "  make remove-skill NAME=<name>                            Remove an external skill"
	@echo "  make list-skills                                         List all skills (local + external)"
	@echo ""
	@echo "Rules Management:"
	@echo "  make extract-rules FOLDER=governance/indexes/security/   Extract rules for all pages in an index"
	@echo "  make extract-rules-all                                   Extract rules across all indexes"
	@echo "  make check-rules FOLDER=governance/indexes/security/     Check page.md vs rules.md staleness"
	@echo "  make check-rules-all                                     Check all index folders"
	@echo "  make refresh-rules FOLDER=governance/indexes/security/   Re-extract only stale/missing rules"
	@echo ""
	@echo "Validation runs via GitHub Copilot agents in VS Code Chat."

serve:
	@if [ ! -f .env ]; then echo "Error: .env not found. Run: cp .env.example .env"; exit 1; fi
	@echo "Starting Architecture Governance server..."
	@echo "Server will run at http://localhost:8000"
	@echo "Press Ctrl+C to stop."
	@echo ""
	@(sleep 2 && (open http://localhost:8000 2>/dev/null || xdg-open http://localhost:8000 2>/dev/null || true)) &
	@python3 -m server.app

stop:
	@echo "Stopping any running governance servers..."
	@pkill -f 'python.*server\.app' 2>/dev/null && echo "Server stopped." || echo "No server running."

ingest:
	@if [ ! -f .env ]; then echo "Error: .env not found. Run: cp .env.example .env"; exit 1; fi
ifndef PAGE_ID
	@echo "Error: PAGE_ID required. Usage: make ingest PAGE_ID=123456789"
	@exit 1
endif
	@echo "Building Docker image..."
	@docker build -t $(DOCKER_IMAGE) .
	@echo "Triggering ingestion pipeline..."
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

# ─── Skill Management ────────────────────────────────────────────────

add-skill:
ifndef REPO
	@echo "Error: REPO required."
	@echo "Usage: make add-skill REPO=<url> NAME=<name> [SKILL_PATH=<path>]"
	@exit 1
endif
ifndef NAME
	@echo "Error: NAME required."
	@echo "Usage: make add-skill REPO=<url> NAME=<name> [SKILL_PATH=<path>]"
	@exit 1
endif
	@echo "Adding external skill: $(NAME)"
	@mkdir -p governance/external
	@git submodule add $(REPO) governance/external/$(NAME)
ifdef SKILL_PATH
	@ln -s ../../governance/external/$(NAME)/$(SKILL_PATH) copilot/skills/$(NAME)
else
	@ln -s ../../governance/external/$(NAME) copilot/skills/$(NAME)
endif
	@echo ""
	@echo "Done. Skill available at: copilot/skills/$(NAME)/"
	@echo "Verify: ls -la copilot/skills/$(NAME)/SKILL.md"
	@echo ""
	@echo "Ensure the SKILL.md has a 'category' field in its frontmatter."
	@echo "Available categories: security, patterns, standards, ingestion, reporting, utility"

update-skills:
	@echo "Updating all external skills..."
	@if [ -f .gitmodules ]; then \
		git submodule update --remote governance/external/; \
		echo "Done. All external skills updated."; \
	else \
		echo "No external skills found (no .gitmodules file)."; \
	fi

remove-skill:
ifndef NAME
	@echo "Error: NAME required. Usage: make remove-skill NAME=<name>"
	@exit 1
endif
	@echo "Removing external skill: $(NAME)"
	@rm -f copilot/skills/$(NAME)
	@git submodule deinit -f governance/external/$(NAME) 2>/dev/null || true
	@git rm -f governance/external/$(NAME) 2>/dev/null || true
	@rm -rf .git/modules/governance/external/$(NAME)
	@echo "Done. Skill '$(NAME)' removed."

extract-rules:
ifndef FOLDER
	@echo "Error: FOLDER required."
	@echo "Usage: make extract-rules FOLDER=governance/indexes/security/"
	@exit 1
endif
	@python3 -m ingest.extract_rules --folder $(FOLDER)

extract-rules-all:
	@python3 -m ingest.extract_rules --all

check-rules:
ifndef FOLDER
	@echo "Error: FOLDER required."
	@echo "Usage: make check-rules FOLDER=governance/indexes/security/"
	@exit 1
endif
	@python3 copilot/skills/rules-extract/rules_check.py --folder $(FOLDER) --fix

check-rules-all:
	@python3 copilot/skills/rules-extract/rules_check.py --all --fix

refresh-rules:
ifndef FOLDER
	@echo "Error: FOLDER required."
	@echo "Usage: make refresh-rules FOLDER=governance/indexes/security/"
	@exit 1
endif
	@python3 -m ingest.extract_rules --folder $(FOLDER) --refresh

list-skills:
	@echo "Skills:"
	@echo ""
	@for dir in copilot/skills/*/; do \
		name=$$(basename "$$dir"); \
		if [ -L "copilot/skills/$$name" ]; then \
			target=$$(readlink "copilot/skills/$$name"); \
			echo "  $$name (external -> $$target)"; \
		else \
			echo "  $$name (local)"; \
		fi; \
	done
