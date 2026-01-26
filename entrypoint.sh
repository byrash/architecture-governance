#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Banner
print_banner() {
    echo ""
    echo -e "${PURPLE}═══════════════════════════════════════════════════════${NC}"
    echo -e "${PURPLE}  🏛️  Architecture Governance System${NC}"
    echo -e "${PURPLE}═══════════════════════════════════════════════════════${NC}"
    echo ""
}

# Step logging
log_step() {
    local step=$1
    local total=$2
    local title=$3
    echo ""
    echo -e "${CYAN}───────────────────────────────────────────────────${NC}"
    echo -e "${CYAN}  [${step}/${total}] ${title}${NC}"
    echo -e "${CYAN}───────────────────────────────────────────────────${NC}"
}

# Success message
log_success() {
    echo -e "${GREEN}  ✓ $1${NC}"
}

# Error message
log_error() {
    echo -e "${RED}  ✗ $1${NC}"
}

# Info message
log_info() {
    echo -e "${BLUE}  → $1${NC}"
}

# Warning message
log_warn() {
    echo -e "${YELLOW}  ⚠ $1${NC}"
}

# Setup .github structure from copilot/
setup_github_structure() {
    log_step 1 5 "Setting up .github structure"
    
    # Create .github directories
    mkdir -p .github/agents
    mkdir -p .github/skills
    
    # Copy agents
    if [ -d "copilot/agents" ]; then
        cp -r copilot/agents/* .github/agents/
        agent_count=$(ls -1 .github/agents/*.agent.md 2>/dev/null | wc -l)
        log_success "Copied ${agent_count} agents to .github/agents/"
    else
        log_error "copilot/agents/ not found"
        exit 1
    fi
    
    # Copy skills
    if [ -d "copilot/skills" ]; then
        cp -r copilot/skills/* .github/skills/
        skill_count=$(ls -1d .github/skills/*/ 2>/dev/null | wc -l)
        log_success "Copied ${skill_count} skills to .github/skills/"
    else
        log_error "copilot/skills/ not found"
        exit 1
    fi
    
    # List what was copied
    if [ "$VERBOSE" = "true" ]; then
        echo ""
        log_info "Agents:"
        for agent in .github/agents/*.agent.md; do
            echo "      - $(basename $agent)"
        done
        echo ""
        log_info "Skills:"
        for skill in .github/skills/*/; do
            echo "      - $(basename $skill)"
        done
    fi
}

# Validate Copilot token
validate_token() {
    log_step 2 5 "Validating Copilot authentication"
    
    if [ -z "$COPILOT_TOKEN" ]; then
        log_error "COPILOT_TOKEN environment variable is not set"
        log_info "Please set COPILOT_TOKEN in your .env file"
        exit 1
    fi
    
    # Export for Copilot CLI
    export GITHUB_TOKEN="$COPILOT_TOKEN"
    
    log_success "Copilot token configured"
    log_info "Model: ${MODEL:-claude-opus-4.5}"
}

# Clean output directory
clean_output() {
    log_info "Cleaning output directory..."
    rm -f governance/output/*.md governance/output/*.html 2>/dev/null || true
    log_success "Output directory cleaned"
}

# Run ingestion agent only
run_ingest() {
    log_step 3 3 "Running Ingestion Agent"
    
    local input_file="${INPUT_FILE:-docs/sample-architecture.html}"
    
    log_info "Input: ${input_file}"
    log_info "Output: governance/output/architecture.md"
    
    echo ""
    echo -e "${YELLOW}Invoking @ingestion-agent...${NC}"
    echo ""
    
    copilot --agent=ingestion-agent \
        --prompt "Ingest ${input_file} to governance/output/architecture.md" \
        --model "${MODEL:-claude-opus-4.5}" \
        --allow-all-paths \
        --allow-all-tools
    
    if [ -f "governance/output/architecture.md" ]; then
        log_success "Created governance/output/architecture.md"
    else
        log_error "Failed to create architecture.md"
        exit 1
    fi
}

# Run full governance validation
run_validate() {
    local input_file="${INPUT_FILE:-docs/sample-architecture.html}"
    
    log_step 3 5 "Running Governance Validation"
    
    log_info "Input: ${input_file}"
    log_info "Model: ${MODEL:-claude-opus-4.5}"
    
    echo ""
    echo -e "${YELLOW}Invoking @governance-agent...${NC}"
    echo ""
    echo -e "${BLUE}This will:${NC}"
    echo "  1. Ingest document → architecture.md"
    echo "  2. Validate patterns → patterns-report.md"
    echo "  3. Validate standards → standards-report.md"
    echo "  4. Validate security → security-report.md"
    echo "  5. Merge reports → governance-report.md"
    echo "  6. Generate dashboard → governance-report.html"
    echo ""
    
    copilot --agent=governance-agent \
        --prompt "Run governance validation on ${input_file}" \
        --model "${MODEL:-claude-opus-4.5}" \
        --allow-all-paths \
        --allow-all-tools
    
    log_step 4 5 "Checking Output Files"
    
    local files=("architecture.md" "patterns-report.md" "standards-report.md" "security-report.md" "governance-report.md" "governance-report.html")
    local missing=0
    
    for file in "${files[@]}"; do
        if [ -f "governance/output/${file}" ]; then
            log_success "Created ${file}"
        else
            log_warn "Missing ${file}"
            ((missing++))
        fi
    done
    
    if [ $missing -gt 0 ]; then
        log_warn "${missing} output file(s) were not created"
    fi
}

# Print summary
print_summary() {
    log_step 5 5 "Summary"
    
    echo ""
    echo -e "${PURPLE}═══════════════════════════════════════════════════════${NC}"
    
    if [ -f "governance/output/governance-report.md" ]; then
        # Try to extract score from report
        local score=$(grep -oP 'Overall Score.*?(\d+)/100' governance/output/governance-report.md 2>/dev/null | grep -oP '\d+' | head -1)
        local status="UNKNOWN"
        
        if [ -n "$score" ]; then
            if [ "$score" -ge 70 ]; then
                status="PASS"
                echo -e "${GREEN}  ✅ RESULT: ${status}${NC}"
            elif [ "$score" -ge 50 ]; then
                status="WARN"
                echo -e "${YELLOW}  ⚠️  RESULT: ${status}${NC}"
            else
                status="FAIL"
                echo -e "${RED}  ❌ RESULT: ${status}${NC}"
            fi
            echo -e "${BLUE}  📊 Score: ${score}/100${NC}"
        else
            echo -e "${BLUE}  📊 Reports generated (check for score)${NC}"
        fi
    else
        echo -e "${YELLOW}  ⚠️  Governance report not generated${NC}"
    fi
    
    echo ""
    echo -e "${BLUE}  📁 Output files in: governance/output/${NC}"
    echo ""
    
    if [ -d "governance/output" ]; then
        for file in governance/output/*; do
            if [ -f "$file" ]; then
                local size=$(du -h "$file" | cut -f1)
                echo "      - $(basename $file) (${size})"
            fi
        done
    fi
    
    echo ""
    echo -e "${PURPLE}═══════════════════════════════════════════════════════${NC}"
    echo ""
}

# Main
main() {
    local command="${1:-validate}"
    
    print_banner
    
    echo -e "${BLUE}  Mode: ${command}${NC}"
    echo -e "${BLUE}  Input: ${INPUT_FILE:-docs/sample-architecture.html}${NC}"
    echo -e "${BLUE}  Verbose: ${VERBOSE:-true}${NC}"
    
    case "$command" in
        validate)
            setup_github_structure
            validate_token
            clean_output
            run_validate
            print_summary
            ;;
        ingest)
            setup_github_structure
            validate_token
            clean_output
            run_ingest
            echo ""
            log_success "Ingestion complete!"
            echo ""
            ;;
        setup)
            setup_github_structure
            log_success "Setup complete!"
            ;;
        *)
            echo "Usage: $0 {validate|ingest|setup}"
            echo ""
            echo "Commands:"
            echo "  validate  - Run full governance validation (default)"
            echo "  ingest    - Only run document ingestion"
            echo "  setup     - Only setup .github structure"
            exit 1
            ;;
    esac
}

main "$@"
