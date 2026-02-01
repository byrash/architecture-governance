---
name: confluence-ingest
description: Ingest Confluence pages by page ID, downloading content and all attachments including draw.io diagrams. Use when asked to fetch, import, or ingest Confluence pages or documentation.
---

# Confluence Page Ingestion

Fetch Confluence pages and their attachments (including draw.io diagrams) for governance analysis.

## Prerequisites

1. **Dependencies** - Install from project requirements:
   ```bash
   # Create virtual environment (recommended)
   python3 -m venv .venv
   source .venv/bin/activate
   
   # Install dependencies
   pip install -r requirements.txt
   ```

2. **Environment variables** - Create `.env` file in workspace root:
   ```
   CONFLUENCE_URL=https://your-company.atlassian.net
   CONFLUENCE_API_TOKEN=your-personal-access-token
   ```
   
   The script **auto-loads `.env`** from workspace root (no manual export needed).

## Usage

### Ingest a page by ID

```bash
python copilot/skills/confluence-ingest/confluence_ingest.py --page-id <PAGE_ID>
```

Output is saved to `governance/output/<PAGE_ID>/`

### Page ID Location

Find the page ID:
- From URL: `https://company.atlassian.net/wiki/spaces/SPACE/pages/123456789/Page+Title` → ID is `123456789`
- Or from page menu: "..." → "Page Information" → Page ID shown

## What Gets Downloaded

| Content | Location | Format |
|---------|----------|--------|
| Page content | `governance/output/<PAGE_ID>/page.md` | Markdown |
| Page metadata | `governance/output/<PAGE_ID>/metadata.json` | JSON |
| All attachments | `governance/output/<PAGE_ID>/attachments/` | PNG, JPG, drawio, PDF, etc. |

All attachments including images, diagrams, and files from all tabs are downloaded.

## Workflow

1. **Fetch page** - Get page content and convert to Markdown
2. **Download attachments** - Get all files attached to the page
3. **Process diagrams** - Draw.io files ready for `drawio-to-mermaid` skill

## Example

```bash
# Set credentials (PAT only)
export CONFLUENCE_URL="https://mycompany.atlassian.net"
export CONFLUENCE_API_TOKEN="your-personal-access-token"

# Ingest page
python copilot/skills/confluence-ingest/confluence_ingest.py --page-id 123456789

# Output saved to: governance/output/123456789/

# Then convert any draw.io diagrams
python copilot/skills/drawio-to-mermaid/drawio_to_mermaid.py \
    --input governance/output/123456789/attachments/architecture.drawio \
    --output governance/output/123456789/architecture.mermaid.md
```

## Output Structure

```
governance/output/<PAGE_ID>/
├── page.md              # Page content as Markdown (includes all tabs)
├── metadata.json        # Page title, author, last modified, etc.
└── attachments/         # All attachments
    ├── screenshot.png
    ├── architecture.drawio
    └── data.xlsx
```

## Options

| Flag | Description |
|------|-------------|
| `--page-id` | Required. Confluence page ID |
| `--include-children` | Also list child pages (optional) |
| `--skip-attachments` | Skip downloading attachments (optional) |

## Next Steps

The ingestion-agent automatically handles:
- Converting `.drawio` files to Mermaid
- Converting images (PNG, JPG, SVG) to Mermaid
- Updating `page.md` with inline Mermaid diagrams
