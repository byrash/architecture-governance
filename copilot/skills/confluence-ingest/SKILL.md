---
name: confluence-ingest
description: Ingest Confluence pages by page ID, downloading content and all attachments, converting Draw.io diagrams to Mermaid, and producing a self-contained Markdown file. Use when asked to fetch, import, or ingest Confluence pages or documentation.
---

# Confluence Page Ingestion

Fetch Confluence pages and produce a self-contained Markdown file with:
- All content including tabs, linked images, and embedded content
- Draw.io diagrams automatically converted to Mermaid code blocks
- All attachments downloaded locally with correct path references

## Setup (First Run Only)

```bash
# 1. Create virtual environment if not exists
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi

# 2. Activate virtual environment
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
```

## Environment Variables

Create `.env` file in workspace root (auto-loaded by script):
```
CONFLUENCE_URL=https://your-company.atlassian.net
CONFLUENCE_API_TOKEN=your-personal-access-token
```

## Usage

### Ingest a page by ID

```bash
# Activate venv and run
source .venv/bin/activate
python .github/skills/confluence-ingest/confluence_ingest.py --page-id <PAGE_ID>
```

Output is saved to `governance/output/`

### Page ID Location

Find the page ID:
- From URL: `https://company.atlassian.net/wiki/spaces/SPACE/pages/123456789/Page+Title` → ID is `123456789`
- Or from page menu: "..." → "Page Information" → Page ID shown

## What Gets Produced

| Content | Location | Description |
|---------|----------|-------------|
| Final Markdown | `governance/output/<PAGE_ID>/page.md` | Self-contained with Mermaid diagrams inlined |
| Metadata | `governance/output/<PAGE_ID>/metadata.json` | Page info, attachments list |
| Attachments | `governance/output/<PAGE_ID>/attachments/` | PNG, JPG, drawio, PDF, etc. |
| Debug HTML | `governance/output/<PAGE_ID>/<Title>.html` | Intermediate HTML for debugging |

## Key Features

### Automatic Draw.io Conversion
- Detects `.drawio` files by extension AND content (`<mxfile>` markers)
- Automatically converts Draw.io diagrams to Mermaid (built-in)
- Replaces image references with Mermaid code blocks inline

### Confluence Tabs Support
- Extracts all tab content (aui-tabs containers)
- Converts hidden tabs to visible sections with headers
- All tab content included in final Markdown

### Image Embedding
- Downloads PNG preview images for Draw.io macros
- Parses base64 metadata from drawio-macro-data divs
- Replaces Confluence URLs with local paths

### HTML Processing
- Uses `body.view` format for better rendering quality
- Falls back to `body.storage` if view unavailable
- Uses `markdownify` library for high-quality conversion

## Example

```bash
# Set credentials (PAT only)
export CONFLUENCE_URL="https://mycompany.atlassian.net"
export CONFLUENCE_API_TOKEN="your-personal-access-token"

# Ingest page with automatic diagram conversion
source .venv/bin/activate
python .github/skills/confluence-ingest/confluence_ingest.py --page-id 123456789

# Output:
#   governance/output/123456789/page.md         <- Self-contained Markdown
#   governance/output/123456789/attachments/    <- All attachments
#   governance/output/123456789/metadata.json   <- Metadata
```

## Output Structure

```
governance/output/<PAGE_ID>/        # Page folder
├── page.md                         # Self-contained Markdown (main output)
├── metadata.json                   # Page metadata and attachment list
├── <Title>.html                    # Intermediate HTML (debug)
└── attachments/                    # All attachments
    ├── architecture.drawio         # Original Draw.io file
    ├── architecture.png            # PNG preview (if downloaded)
    ├── screenshot.png              # Other images
    └── data.xlsx                   # Other attachments
```

## Options

| Flag | Description |
|------|-------------|
| `--page-id`, `-p` | Required. Confluence page ID |
| `--output-dir`, `-o` | Output directory (default: `governance/output`) |
| `--no-convert` | Skip Draw.io to Mermaid conversion |
| `--mode`, `-m` | Mode: `governance` or `index` (default: `governance`) |

## Output Markdown Quality

The final `page.md` file is:
- **Self-contained**: No external dependencies or broken links
- **Mermaid-ready**: Draw.io diagrams converted to Mermaid code blocks
- **Image paths fixed**: References point to `attachments/` folder
- **Tabs flattened**: All tab content visible as sections

## Next Steps (MANDATORY)

After running this script, the ingestion-agent MUST:
1. **Convert ALL remaining images to Mermaid** using `image-to-mermaid` skill
2. **Replace image references** in page.md with inline Mermaid blocks
3. **Validate** that page.md has ZERO image references

**WHY**: Validation agents compare page.md against index rules using text analysis. They cannot read image files. For validation to work, ALL diagrams must be Mermaid text.

Final `page.md` requirements:
- ✅ Draw.io → Mermaid (automatic by this script)
- ⚠️ PNG/JPG/SVG → Mermaid (requires `image-to-mermaid` skill)
- ✅ ZERO image references remaining
- ✅ 100% text/Mermaid content
