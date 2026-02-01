# Architecture Governance

AI-powered validation of Confluence architecture documents against patterns, standards, and security rules.

## Quick Start

```bash
# 1. Setup
cp .env.example .env
# Edit .env with your Confluence URL, PAT, and Copilot token

# 2. Run full validation (Docker)
make validate PAGE_ID=123456789

# 3. Or use agents in IDE
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
        CI[confluence-ingest]
        DM[drawio-to-mermaid]
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
    IA --> DM
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
| **ingestion-agent** | Downloads Confluence pages, converts diagrams to Mermaid | confluence-ingest, drawio-to-mermaid, image-to-mermaid |
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
    IA->>IA: Convert diagrams → Mermaid
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
    IA->>IA: Convert diagrams to Mermaid
    IA-->>GA: page.md ready

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

All outputs saved to `governance/output/<PAGE_ID>/`:

| File | Description |
|------|-------------|
| `page.md` | Clean markdown with Mermaid diagrams |
| `metadata.json` | Page metadata from Confluence |
| `attachments/` | Original downloaded files |
| `patterns-report.md` | Pattern validation results |
| `standards-report.md` | Standards validation results |
| `security-report.md` | Security validation results |
| `governance-report.md` | Merged final report |
| `governance-report.html` | HTML dashboard |

## Project Structure

```
copilot/
├── agents/                     # AI agents
│   ├── governance-agent.agent.md
│   ├── ingestion-agent.agent.md
│   ├── patterns-agent.agent.md
│   ├── standards-agent.agent.md
│   └── security-agent.agent.md
│
└── skills/                     # Reusable skills
    ├── confluence-ingest/      # Download pages
    ├── drawio-to-mermaid/      # Convert diagrams
    ├── image-to-mermaid/       # Convert images (vision)
    ├── index-query/            # Read from indexes
    ├── pattern-validate/       # Validate patterns
    ├── standards-validate/     # Validate standards
    ├── security-validate/      # Validate security
    ├── merge-reports/          # Combine reports
    └── markdown-to-html/       # Generate dashboard

governance/
├── indexes/                    # Knowledge base (add .md files here)
│   ├── patterns/
│   ├── standards/
│   └── security/
│
└── output/                     # Generated reports
    └── <PAGE_ID>/
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
