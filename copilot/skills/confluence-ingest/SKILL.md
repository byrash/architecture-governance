---
name: confluence-ingest
description: Ingest Confluence pages by page ID, downloading content and all attachments, converting Draw.io diagrams to Mermaid via XML parsing (free). Produces a Markdown file ready for validation.
---

# Confluence Page Ingestion

Fetch Confluence pages and produce a self-contained Markdown file with:
- All content including tabs, linked images, and embedded content
- **Draw.io diagrams converted to Mermaid via XML parsing (FREE - no model cost)**
- Remaining images listed for agent to convert using vision (only when no .drawio source)

## Cost-Efficient Approach

| Diagram Type | Conversion Method | Cost |
|--------------|-------------------|------|
| Draw.io (has `.drawio` file) | XML parsing | **FREE** |
| PNG/JPG (no `.drawio` source) | Agent vision | $$$ |

## Setup (First Run Only)

```bash
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install -r requirements.txt
```

## Environment Variables

Create `.env` file in workspace root:
```
CONFLUENCE_URL=https://your-company.atlassian.net
CONFLUENCE_API_TOKEN=your-personal-access-token
```

## Usage

```bash
source .venv/bin/activate
python copilot/skills/confluence-ingest/confluence_ingest.py --page-id <PAGE_ID>
```

## What Gets Produced

| Content | Location |
|---------|----------|
| Markdown | `governance/output/<PAGE_ID>/page.md` |
| Metadata | `governance/output/<PAGE_ID>/metadata.json` |
| Attachments | `governance/output/<PAGE_ID>/attachments/` |

## Script Output Example

```
📊 DRAW.IO → MERMAID (XML parsing - FREE, no model cost)
   Found 3 Draw.io file(s)
   📄 architecture.drawio → parsing XML...
   ✅ architecture.drawio → Mermaid (success)
   📄 data-flow.drawio → parsing XML...
   ✅ data-flow.drawio → Mermaid (success)

🔄 Replacing 2 diagram reference(s) with Mermaid...

============================================================
✅ INGESTION COMPLETE
============================================================
   Output: governance/output/123456/page.md

   📊 Draw.io → Mermaid: 2 diagram(s) converted (FREE via XML parsing)

   🖼️  IMAGES NEED VISION: 1 image(s) (costs $$ - no .drawio source)
      → attachments/screenshot.png

   📋 Agent: Read each image and convert to Mermaid
```

## Next Steps

After running this script, the ingestion-agent should:

1. **Check if any images remain** - only those without `.drawio` source need vision
2. **Convert remaining images** using vision (costs money, but unavoidable)
3. **Replace image references** in page.md with Mermaid blocks

## Why XML Parsing for Draw.io?

- **FREE** - runs locally, no model API calls
- **Fast** - no network latency
- **Deterministic** - same input always produces same output
- **Accurate** - parses actual diagram structure, not image interpretation
