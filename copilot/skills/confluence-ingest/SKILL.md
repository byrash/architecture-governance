---
name: confluence-ingest
category: ingestion
description: Ingest Confluence pages by page ID, downloading content and all attachments, converting Draw.io and PlantUML diagrams to Mermaid via local parsing (free). Produces a Markdown file ready for validation.
---

# Confluence Page Ingestion

Fetch Confluence pages and produce a self-contained Markdown file with:
- All content including tabs, linked images, and embedded content
- **Draw.io diagrams converted to Mermaid via XML parsing (FREE - no model cost)**
- **PlantUML diagrams converted to Mermaid via Python parsing (FREE - no model cost)**
- Remaining images listed for agent to convert using vision (only when no .drawio source)

## Cost-Efficient Approach

| Diagram Type | Conversion Method | Tool | Cost |
|--------------|-------------------|------|------|
| Draw.io (has `.drawio` file) | XML parsing | `drawio_to_mermaid.py` | **FREE** |
| PlantUML (`@startuml`, `` ```plantuml ``) | Python parsing | `plantuml_to_mermaid.py` | **FREE** |
| PNG/JPG (no `.drawio` source) | Agent vision | LLM | $$$ |

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

## PlantUML to Mermaid Conversion

PlantUML blocks (`@startuml`/`@enduml`, `` ```plantuml ``/`` ```puml ``) don't render natively in Markdown. This tool converts them to Mermaid automatically.

```bash
source .venv/bin/activate
python copilot/skills/confluence-ingest/plantuml_to_mermaid.py --input <PAGE_MD> --output <PAGE_MD>
```

### Supported Diagram Types

| Type | Preserves Colors | Preserves Line Styles |
|------|------------------|-----------------------|
| Sequence (participants, messages, alt/opt/loop/par/break/critical) | Legend comments | Solid/dashed/dotted `->` `-->` `..>` |
| Component/Deployment (packages, subgraphs) | `classDef` directives | Solid/dashed/thick `-->` `-.->` `==>` |
| Class (inheritance, composition, interfaces) | N/A | All relation arrows |
| State (transitions) | N/A | Transitions |

### Sequence-Specific Features

- Activation bars: `activate`/`deactivate`, `->++`/`-->--`
- Colored arrows: `-[#red]>` → documented in legend
- Box grouping: `box "Label" #color ... end box`
- All fragments: `alt`/`else`, `opt`, `loop`, `break`, `critical`, `par`/`and`
- Multi-line notes, dividers (`== Section ==`), `autonumber`
- `create`/`destroy`, `return`, `ref over`

**Zero external dependencies** — uses only Python 3 standard library.

## Next Steps

After running these scripts, the ingestion-agent should:

1. **Check if any images remain** - only those without `.drawio` source need vision
2. **Convert remaining images** using vision (costs money, but unavoidable)
3. **Replace image references** in page.md with Mermaid blocks

## Why Local Parsing?

- **FREE** - runs locally, no model API calls
- **Fast** - no network latency
- **Deterministic** - same input always produces same output
- **Accurate** - parses actual diagram structure, not image interpretation
