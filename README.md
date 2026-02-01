# Architecture Governance

AI-powered validation of Confluence architecture documents against patterns, standards, and security rules.

## Quick Start

### Docker (Recommended)
```bash
cp .env.example .env
# Edit .env with your tokens

make validate PAGE_ID=123456789
```

### IDE Agents
```bash
# 1. Setup (first time only)
cp .env.example .env
# Edit .env with CONFLUENCE_URL and CONFLUENCE_API_TOKEN

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Use agents (venv auto-activates, .env auto-loads)
@ingestion-agent Ingest Confluence page 123456789
@governance-agent Validate Confluence page 123456789
```

## Architecture Overview

```mermaid
flowchart TB
    subgraph User[User Entry Points]
        U1["@ingestion-agent<br/>Ingest page to index"]
        U2["@governance-agent<br/>Validate page"]
    end

    subgraph Orchestration[Governance Agent]
        GA[governance-agent]
    end

    subgraph Ingestion[Ingestion Agent]
        IA[ingestion-agent]
        CI[confluence-ingest + drawio conversion]
        IM[image-to-mermaid]
    end

    subgraph Validation[Validation Agents - Parallel]
        PA[patterns-agent]
        SA[standards-agent]
        SEA[security-agent]
    end

    subgraph Skills[Shared Skills]
        IQ[index-query]
        MR[merge-reports]
        MH[markdown-to-html]
    end

    subgraph Storage
        CONF[(Confluence)]
        IDX[(Indexes)]
        OUT[(Output)]
    end

    %% User triggers ingestion directly for indexing
    U1 -->|page-id + index| IA
    
    %% User triggers governance which orchestrates everything
    U2 -->|page-id| GA
    GA -->|step 1| IA
    GA -->|step 2| PA
    GA -->|step 2| SA
    GA -->|step 2| SEA
    GA -->|step 3| MR
    GA -->|step 4| MH

    %% Ingestion flow
    IA --> CI
    IA --> IM
    CI <-->|download| CONF
    IA -->|page.md| OUT
    IA -->|copy| IDX

    %% Validation flow
    PA --> IQ
    SA --> IQ
    SEA --> IQ
    IQ <-->|read rules| IDX
    PA -->|report| OUT
    SA -->|report| OUT
    SEA -->|report| OUT

    %% Final output
    MR -->|merged report| OUT
    MH -->|HTML dashboard| OUT
```

## Agents

| Agent | Purpose | Skills Used |
|-------|---------|-------------|
| **ingestion-agent** | Downloads Confluence pages, converts ALL diagrams/images to Mermaid | confluence-ingest (drawio auto), image-to-mermaid (PNG/JPG mandatory) |
| **governance-agent** | Orchestrates full validation pipeline | merge-reports, markdown-to-html |
| **patterns-agent** | Validates against design patterns | index-query, pattern-validate |
| **standards-agent** | Validates against architectural standards | index-query, standards-validate |
| **security-agent** | Validates against security controls | index-query, security-validate |

## Workflows

### 1. Ingest to Index

Add architecture documents to your knowledge base:

```
@ingestion-agent Ingest Confluence page 123456789 to patterns
@ingestion-agent Ingest Confluence page 123456789 to standards
@ingestion-agent Ingest Confluence page 123456789 to security
```

```mermaid
sequenceDiagram
    participant User
    participant IA as ingestion-agent
    participant Confluence
    participant Index

    User->>IA: Ingest page 123 to patterns
    IA->>Confluence: Download page + attachments
    IA->>IA: Convert Draw.io → Mermaid (auto)
    IA->>IA: Convert images → Mermaid (vision)
    IA->>IA: Validate 100% text/Mermaid
    IA->>Index: Copy page.md to indexes/patterns/
    IA-->>User: Indexed successfully
```

### 2. Validate Architecture

Run full governance validation:

```
@governance-agent Validate Confluence page 123456789
```

```mermaid
sequenceDiagram
    participant User
    participant GA as governance-agent
    participant IA as ingestion-agent
    participant PA as patterns-agent
    participant SA as standards-agent
    participant SEA as security-agent

    User->>GA: Validate page 123456789
    
    Note over GA,IA: Step 1: Ingestion
    GA->>IA: Ingest page
    IA->>IA: Download from Confluence
    IA->>IA: Convert Draw.io → Mermaid
    IA->>IA: Convert images → Mermaid
    IA->>IA: Validate 100% text
    IA-->>GA: page.md ready (no images)

    Note over GA,SEA: Step 2: Parallel Validation
    par patterns
        GA->>PA: Validate patterns
        PA->>PA: Read indexes/patterns/*.md
        PA->>PA: Check document
        PA-->>GA: patterns-report.md
    and standards
        GA->>SA: Validate standards
        SA->>SA: Read indexes/standards/*.md
        SA->>SA: Check document
        SA-->>GA: standards-report.md
    and security
        GA->>SEA: Validate security
        SEA->>SEA: Read indexes/security/*.md
        SEA->>SEA: Check document
        SEA-->>GA: security-report.md
    end

    Note over GA: Step 3-4: Consolidate
    GA->>GA: Merge reports (30/30/40 weights)
    GA->>GA: Generate HTML dashboard
    GA-->>User: governance-report.html
```

## Setup

### Environment Variables

```bash
cp .env.example .env
```

Edit `.env`:
```
# Required for Docker (Copilot CLI)
COPILOT_TOKEN=your-github-token

# Required for Confluence access
CONFLUENCE_URL=https://your-company.atlassian.net
CONFLUENCE_API_TOKEN=your-personal-access-token
```

Get tokens:
- **COPILOT_TOKEN**: https://github.com/settings/tokens (needs `copilot` scope)
- **CONFLUENCE_API_TOKEN**: https://id.atlassian.com/manage-profile/security/api-tokens

### Finding Page ID

From URL: `https://company.atlassian.net/wiki/spaces/SPACE/pages/123456789/Title`

Page ID = `123456789`

## Usage Examples

### Make Commands (Docker)

| Task | Command |
|------|---------|
| Ingest only | `make ingest PAGE_ID=123456789` |
| Full validation | `make validate PAGE_ID=123456789` |
| Clean outputs | `make clean` |

### IDE Agent Commands

| Task | Command |
|------|---------|
| Ingest page (no index) | `@ingestion-agent Ingest Confluence page 123456789` |
| Ingest to patterns index | `@ingestion-agent Ingest Confluence page 123456789 to patterns` |
| Ingest to standards index | `@ingestion-agent Ingest Confluence page 123456789 to standards` |
| Ingest to security index | `@ingestion-agent Ingest Confluence page 123456789 to security` |
| Full validation | `@governance-agent Validate Confluence page 123456789` |

## Output

All outputs saved to `governance/output/`:

| File | Description |
|------|-------------|
| `<PAGE_ID>/page.md` | Clean markdown with ALL diagrams as Mermaid (100% text) |
| `<PAGE_ID>/metadata.json` | Page metadata from Confluence |
| `<PAGE_ID>/attachments/` | Original downloaded files |
| `<PAGE_ID>-patterns-report.md` | Pattern validation results |
| `<PAGE_ID>-standards-report.md` | Standards validation results |
| `<PAGE_ID>-security-report.md` | Security validation results |
| `<PAGE_ID>-governance-report.md` | Merged final report |
| `<PAGE_ID>-governance-report.html` | HTML dashboard |

## Project Structure

```
copilot/                        # Mounted as .github/ in Docker
├── agents/                     # AI agents
│   ├── governance-agent.agent.md
│   ├── ingestion-agent.agent.md
│   ├── patterns-agent.agent.md
│   ├── standards-agent.agent.md
│   └── security-agent.agent.md
│
└── skills/                     # Reusable skills
    ├── confluence-ingest/      # Download pages + drawio→mermaid conversion
    ├── image-to-mermaid/       # Convert images (vision)
    ├── index-query/            # Read from indexes
    ├── pattern-validate/       # Validate patterns
    ├── standards-validate/     # Validate standards
    ├── security-validate/      # Validate security
    ├── merge-reports/          # Combine reports
    └── markdown-to-html/       # Generate dashboard

governance/
├── indexes/                    # Knowledge base
│   ├── patterns/<PAGE_ID>-<title>.md
│   ├── standards/<PAGE_ID>-<title>.md
│   └── security/<PAGE_ID>-<title>.md
│
└── output/                     # Generated outputs
    ├── <PAGE_ID>/              # Page folder
    │   ├── page.md
    │   ├── metadata.json
    │   └── attachments/
    └── <PAGE_ID>-*-report.md   # Validation reports
```

## Scoring

Governance score calculated as weighted average:

| Category | Weight |
|----------|--------|
| Patterns | 30% |
| Standards | 30% |
| Security | 40% |

**Thresholds:**
- **PASS**: Score ≥ 70
- **WARN**: Score 50-69
- **FAIL**: Score < 50
