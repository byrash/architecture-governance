---
name: rules-extract
category: utility
description: Extract structured governance rules from raw indexed documents into compact markdown-table format. Supports single-file and batch-folder extraction. Use when asked to extract rules, build rule index, or create .rules.md files from architecture documents.
---

# Rules Extraction

Extract structured governance rules from raw architecture documents and save as compact `.rules.md` files for efficient validation.

## Input

### Single-file mode

- **Document path**: `governance/indexes/<category>/<filename>.md` (provided by caller)
- **Category**: `patterns`, `standards`, `security`, or `general` (provided by caller)

### Batch-folder mode

- **Folder path**: any directory containing `.md` files
- **Category**: auto-detected from folder name or specified by caller
- Process ALL `.md` files in the folder (excluding existing `.rules.md` files)

## Output

### Single-file mode

Write to `<filename>.rules.md` alongside the source (same directory, `.rules.md` extension).

### Batch-folder mode

1. **Per-file**: `<filename>.rules.md` for each source `.md` file
2. **Consolidated**: `_all.rules.md` in the folder root -- merged, deduplicated, sorted by severity

## What to Extract

### Explicit Rules (stated in text)
- Requirements, standards, controls, guidelines
- Must/must-not statements
- Compliance requirements
- Technology mandates (e.g., "must use REST", "no GraphQL")
- Security controls (e.g., "encryption at rest required")

### Implicit Rules (from diagrams and architecture)
- Architectural constraints implied by Mermaid diagrams
- Integration patterns (e.g., all external calls go through API gateway)
- Technology choices shown in diagrams
- Data flow restrictions
- Component boundaries and isolation patterns

### Conventions (from visual patterns)
- Color coding conventions (e.g., dark blue = firm applications, green = application in context, orange = external vendors)
- Node shape conventions (e.g., cylinders for databases, rectangles for services)
- Naming conventions visible in diagrams
- Layer/tier boundaries shown in subgraphs

## Diagram Interpretation Guide

When reading Mermaid diagrams, extract governance rules from:

| Diagram Element | What to Infer |
|-----------------|---------------|
| Subgraph boundaries | Isolation requirements, trust zones, network segments |
| Edge labels | Protocol requirements (HTTPS, gRPC, REST), data flow rules |
| Node shapes | Component types, technology mandates |
| Color/style annotations | Classification (internal, external, vendor), sensitivity levels |
| Missing connections | Forbidden communication paths (e.g., no direct DB access from frontend) |
| Gateway/proxy nodes | All traffic must route through specific components |
| Encryption labels (TLS, mTLS) | Encryption requirements between components |

### Example: Inferring rules from a diagram

Given this Mermaid diagram in the document:

```mermaid
flowchart TB
    subgraph External [External - Orange]
        Vendor[Vendor API]
    end
    subgraph Internal [Internal - Blue]
        GW[API Gateway]
        Auth[Auth Service]
        App[Application]
    end
    Vendor -->|HTTPS| GW
    GW -->|mTLS| Auth
    GW -->|mTLS| App
    App -->|encrypted| DB[(Database)]
```

Extract these rules:

| ID | Rule | Sev | Req | Keywords | Condition |
|----|------|-----|-----|----------|-----------|
| R-001 | External vendor isolation | C | Y | vendor,gateway,external | All external vendor traffic must route through API gateway |
| R-002 | Internal mTLS | H | Y | mTLS,internal,service | Internal service-to-service communication must use mTLS |
| R-003 | Database encryption | C | Y | database,encrypted,storage | Database connections must be encrypted |
| R-004 | No direct vendor access | C | Y | vendor,direct,forbidden | Vendors must not directly access internal services |

## Extraction Process

1. **Read the full document** including all Mermaid code blocks
2. **Scan text sections** for explicit rules, requirements, and standards
3. **Parse each Mermaid diagram** for architectural constraints and conventions
4. **Deduplicate** rules that appear in both text and diagrams
5. **Classify** each rule with severity and required/recommended
6. **Generate keywords** for each rule (used by validation agents for quick matching)
7. **Write** the compact markdown table output

## Severity Classification

| Code | Severity | Criteria |
|------|----------|----------|
| C | Critical | Security controls, data protection, auth requirements |
| H | High | Architectural patterns, integration standards, performance |
| M | Medium | Naming conventions, documentation standards, best practices |
| L | Low | Style preferences, optional enhancements |

## Output Format

```markdown
# Rules - <source-filename>

> Source: <path> | Extracted: <timestamp> | Model: <actual model> | Category: <category> | Fingerprint: <md5-first-12-chars>

| ID | Rule | Sev | Req | Keywords | Condition |
|----|------|-----|-----|----------|-----------|
| R-001 | <rule name> | C/H/M/L | Y/N | <comma-separated keywords> | <one-line condition> |
```

### Fingerprint

The `Fingerprint` field contains the first 12 characters of the MD5 hash of the source `.md` file's first 64KB. This allows the staleness checker (`rules_check.py`) to detect when a source file has changed without relying only on file timestamps.

**To compute the fingerprint** before writing the `.rules.md`:

```bash
python3 -c "import hashlib; print(hashlib.md5(open('<source-path>','rb').read(65536)).hexdigest()[:12])"
```

Or let the rules-extraction-agent compute it using the execute tool.

Rules:
- **ID**: Sequential `R-001`, `R-002`, etc.
- **Rule**: Short descriptive name (max 5 words)
- **Sev**: C=Critical, H=High, M=Medium, L=Low
- **Req**: Y=Required, N=Recommended
- **Keywords**: Comma-separated, lowercase, for quick matching
- **Condition**: One-line description of what must be true

## Consolidation (Batch Mode)

When processing multiple files, after generating per-file `.rules.md` files:

1. **Merge** all per-file rule tables into one unified table
2. **Deduplicate** rules with overlapping keywords AND similar conditions:
   - If rule A (from file1) and rule B (from file2) share 3+ keywords AND describe the same constraint → keep the more specific one
   - Note both sources in the `Source` column
3. **Re-number** IDs sequentially: `R-001`, `R-002`, etc.
4. **Sort** by severity: Critical first, then High, Medium, Low
5. **Identify cross-document patterns**: rules that appear in 2+ source files represent widely-agreed governance principles and should be called out

### Consolidated output adds a `Source` column

```markdown
| ID | Rule | Sev | Req | Keywords | Condition | Source |
|----|------|-----|-----|----------|-----------|--------|
| R-001 | External vendor isolation | C | Y | vendor,gateway | Must route through gateway | auth-standards.md, api-guidelines.md |
```

### Cross-document patterns section

After the main table, add a summary of rules found across multiple sources:

```markdown
## Cross-Document Patterns

| Rule Pattern | Appears In | Severity |
|-------------|-----------|----------|
| mTLS for internal services | auth-standards.md, microservices.md, api-guidelines.md | Critical |
| API gateway routing | auth-standards.md, vendor-integration.md | Critical |
```

These cross-document patterns are the highest-confidence rules and should be prioritized by validation agents.

## Important

- Extract ALL rules, not just obvious ones -- diagrams often contain implicit rules
- Keep the table compact -- every token saved here saves tokens across every future validation run
- Preserve the raw `.md` files unchanged -- `.rules.md` files are derived artifacts
- If a document has no extractable rules, write a `.rules.md` with an empty table and a note
- In batch mode, continue processing remaining files if one file fails
