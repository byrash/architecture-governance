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

log_info() {
    echo -e "${BLUE}  → $1${NC}"
}

log_error() {
    echo -e "${RED}  ✗ $1${NC}"
}

log_success() {
    echo -e "${GREEN}  ✓ $1${NC}"
}

# Check required environment variables
check_env() {
    local errors=0
    
    if [ -z "$COPILOT_TOKEN" ]; then
        log_error "COPILOT_TOKEN not set"
        log_info "Get token from: https://github.com/settings/tokens"
        errors=1
    fi
    if [ -z "$CONFLUENCE_URL" ]; then
        log_error "CONFLUENCE_URL not set"
        errors=1
    fi
    if [ -z "$CONFLUENCE_API_TOKEN" ]; then
        log_error "CONFLUENCE_API_TOKEN not set"
        errors=1
    fi
    if [ -z "$PAGE_ID" ]; then
        log_error "PAGE_ID not set"
        errors=1
    fi
    
    if [ $errors -eq 1 ]; then
        exit 1
    fi
    
    log_success "Environment configured"
    log_info "Page ID: $PAGE_ID"
    log_info "Confluence: $CONFLUENCE_URL"
}

# Run agent via GitHub Copilot
run_agent() {
    local agent=$1
    local prompt=$2
    
    echo ""
    echo -e "${CYAN}───────────────────────────────────────────────────${NC}"
    echo -e "${CYAN}  Triggering: @${agent}${NC}"
    echo -e "${CYAN}  Prompt: ${prompt}${NC}"
    echo -e "${CYAN}───────────────────────────────────────────────────${NC}"
    echo ""
    
    if command -v github-copilot-cli &> /dev/null; then
        GITHUB_TOKEN="$COPILOT_TOKEN" github-copilot-cli "@${agent} ${prompt}"
    else
        log_error "GitHub Copilot CLI not found"
        log_info "Fallback: Run manually in VS Code Chat: @${agent} ${prompt}"
        return 1
    fi
}

# Main
main() {
    local cmd="${1:-ingest}"
    local index="${2:-}"
    
    print_banner
    check_env
    
    case "$cmd" in
        ingest)
            if [ -n "$index" ]; then
                python -c "from ingest import ingest_page; ingest_page(page_id='$PAGE_ID', index='$index')"
            else
                python -c "from ingest import ingest_page; ingest_page(page_id='$PAGE_ID')"
            fi
            ;;
        validate)
            run_agent "governance-agent" "Validate Confluence page $PAGE_ID"
            ;;
        *)
            echo "Usage: $0 {ingest|validate} [index]"
            echo ""
            echo "Commands:"
            echo "  ingest              Ingest page (deterministic pipeline)"
            echo "  ingest <index>      Ingest page to index (patterns/standards/security)"
            echo "  validate            Full validation via @governance-agent"
            echo ""
            echo "Examples:"
            echo "  $0 ingest"
            echo "  $0 ingest patterns"
            echo "  $0 validate"
            exit 1
            ;;
    esac
    
    echo ""
    echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  ✅ Complete${NC}"
    echo -e "${GREEN}  Output: governance/output/$PAGE_ID/${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
    echo ""
}

main "$@"
