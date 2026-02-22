# Architecture Governance Makefile

.PHONY: help ingest validate clean release add-skill update-skills remove-skill list-skills check-rules check-rules-all refresh-rules extract-rules convert-plantuml

.DEFAULT_GOAL := help

DOCKER_IMAGE := architecture-governance
VERSION := $(shell date +%Y%m%d-%H%M%S)

help:
	@echo "Architecture Governance"
	@echo ""
	@echo "Governance Commands:"
	@echo "  make ingest PAGE_ID=123456789                  Ingest via @ingestion-agent"
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
	@echo "  make check-rules FOLDER=governance/indexes/security/   Check <PAGE_ID>/page.md vs rules.md staleness"
	@echo "  make check-rules-all                                   Check all index folders"
	@echo "  make refresh-rules FOLDER=governance/indexes/security/  Show refresh instructions"
	@echo "  make extract-rules                                      Show extraction usage"
	@echo ""
	@echo "Conversion Tools:"
	@echo "  make convert-plantuml FILE=path/to/file.md              Convert PlantUML to Mermaid"
	@echo ""
	@echo "All governance commands trigger agents via Copilot CLI in Docker."

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

convert-plantuml:
	@if [ -z "$(FILE)" ]; then \
		echo "Usage: make convert-plantuml FILE=path/to/file.md"; \
		echo "  Converts all PlantUML blocks in a Markdown or .puml file to Mermaid."; \
		exit 1; \
	fi
	python3 copilot/skills/confluence-ingest/plantuml_to_mermaid.py --input $(FILE) --output $(FILE)

extract-rules:
	@echo "═══════════════════════════════════════════"
	@echo " Rules Extraction"
	@echo "═══════════════════════════════════════════"
	@echo ""
	@echo "Use the rules-extraction-agent in Copilot Chat:"
	@echo ""
	@echo "  Batch mode (entire index folder):"
	@echo "    @rules-extraction-agent Extract rules from governance/indexes/security/"
	@echo "    @rules-extraction-agent Extract rules from governance/indexes/patterns/"
	@echo "    @rules-extraction-agent Extract rules from governance/indexes/standards/"
	@echo ""
	@echo "  Single page mode:"
	@echo "    @rules-extraction-agent Extract rules from governance/indexes/security/<PAGE_ID>/page.md for category security"
	@echo ""
	@echo "  Output (per-page folder layout):"
	@echo "    Per-page:      <PAGE_ID>/rules.md  (one per page.md in subfolder)"
	@echo "    Consolidated:  _all.rules.md       (merged, deduplicated)"
	@echo ""
	@if ls governance/indexes/*/_all.rules.md 2>/dev/null; then \
		echo "  Existing consolidated rules:"; \
		for f in governance/indexes/*/_all.rules.md; do \
			lines=$$(wc -l < "$$f" 2>/dev/null || echo 0); \
			echo "    $$f ($$lines lines)"; \
		done; \
	else \
		echo "  No consolidated rules files found yet."; \
	fi

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
	@echo "Checking staleness in $(FOLDER)..."
	@python3 copilot/skills/rules-extract/rules_check.py --folder $(FOLDER) --fix || true
	@echo ""
	@echo "To refresh stale rules, run in Copilot Chat:"
	@echo "  @rules-extraction-agent Refresh rules in $(FOLDER)"

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
