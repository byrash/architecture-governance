---
name: confluence-ingest
category: ingestion
description: Ingest Confluence pages by page ID, downloading content and all attachments, converting diagrams to Mermaid via deterministic parsing (Draw.io XML, SVG XML, PlantUML, Markdown/Mermaid macros). Validates with mmdc, caches results by SHA256, and pre-extracts OCR/CV context for vision fallback.
---

# Confluence Page Ingestion

Fetch Confluence pages and produce a self-contained Markdown file with:
- All content including tabs, linked images, and embedded content
- **All CDATA macros extracted from storage HTML (no lossy HTML round-trip)**:
  - Markdown macros -- raw markdown preserved exactly as authored
  - Mermaid macros -- extracted and preserved directly
  - Code Block macros -- language tag and exact indentation preserved
  - No Format macros -- exact whitespace preserved
  - Excerpt macros -- boundary markers added, content flows through normally
- **Draw.io diagrams converted to Mermaid via XML parsing (FREE)**
- **SVG diagrams converted to Mermaid via XML parsing (FREE)**
- **PlantUML diagrams converted to Mermaid via Python parsing (FREE)**
- **All Mermaid output validated via `mmdc --parse`**
- **Results cached by SHA256 content hash for deterministic re-ingestion**
- Remaining raster images pre-extracted (OCR + CV) for vision fallback

## Conversion Priority Cascade

The script tries every deterministic method first, falling back to vision only as a last resort:

| Priority | Source Type | Method | Tool | Cost | Deterministic |
|----------|------------|--------|------|------|--------------|
| 1 | Draw.io (`.drawio` file) | XML parsing | `drawio_to_mermaid.py` | **FREE** | Yes |
| 2 | SVG (`.svg` file or inline) | XML parsing | `svg_to_mermaid.py` | **FREE** | Yes |
| 3 | Mermaid macro | Extract CDATA as-is | built-in | **FREE** | Yes |
| 4 | Markdown macro | Extract CDATA raw MD | built-in | **FREE** | Yes |
| 5 | Code Block macro | Extract CDATA + language | built-in | **FREE** | Yes |
| 6 | No Format macro | Extract CDATA preformatted | built-in | **FREE** | Yes |
| 7 | Excerpt macro | Mark boundaries in HTML | built-in | **FREE** | Yes |
| 8 | PlantUML | Python parsing | `plantuml_to_mermaid.py` | **FREE** | Yes |
| 9 | Cached result | SHA256 lookup | built-in | **FREE** | Yes |
| 10 | PNG/JPG (last resort) | Pre-extract + vision | `preextract_diagram.py` + LLM | $$$ | No |

## Setup (First Run Only)

```bash
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install -r requirements.txt

# Install Mermaid CLI for syntax validation
npm install

# Install Tesseract OCR (for image pre-extraction)
# macOS: brew install tesseract
# Ubuntu: sudo apt-get install tesseract-ocr
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
| Conversion manifest | `governance/output/<PAGE_ID>/conversion-manifest.json` |
| Attachments | `governance/output/<PAGE_ID>/attachments/` |
| Pre-extract context | `governance/output/<PAGE_ID>/attachments/<image>.context.json` |
| Cache | `governance/output/.cache/mermaid/<sha256>.mmd` |

## Validation

All generated Mermaid is validated using `mmdc --parse` via `validate_mermaid.py`. Invalid output:
- From deterministic paths (Draw.io, SVG): logged and falls through to next method
- From vision: retried up to 3 times with error feedback, then kept as image ref

```bash
# Validate a Mermaid file manually
python copilot/skills/confluence-ingest/validate_mermaid.py --input diagram.mmd --json
```

## SVG to Mermaid Conversion

SVG files (vector XML) are parsed deterministically -- no LLM needed:

```bash
python copilot/skills/confluence-ingest/svg_to_mermaid.py --input diagram.svg
```

Handles:
- `<text>` elements as node labels
- `<rect>`, `<circle>`, `<ellipse>` as node shapes
- `<path>`, `<line>` with arrowheads as edges
- CSS `fill`, `stroke`, `stroke-dasharray` as colors and line styles
- Detects embedded raster images (falls back to vision)

## Image Pre-Extraction

For images that require vision, deterministic features are extracted first:

```bash
python copilot/skills/confluence-ingest/preextract_diagram.py --input diagram.png --format-prompt
```

Extracts:
- **Text labels** via Tesseract OCR (exact strings)
- **Colors** via Pillow (exact hex values)
- **Shape counts** via OpenCV (rectangles, circles, diamonds)
- **Line counts** via OpenCV Hough transform

The agent includes this context in the LLM prompt to constrain output.

## PlantUML to Mermaid Conversion

PlantUML blocks (`@startuml`/`@enduml`, `` ```plantuml ``/`` ```puml ``) don't render natively in Markdown. This tool converts them to Mermaid automatically.

```bash
python copilot/skills/confluence-ingest/plantuml_to_mermaid.py --input <PAGE_MD> --output <PAGE_MD>
```

### Supported Diagram Types

| Type | Preserves Colors | Preserves Line Styles |
|------|------------------|-----------------------|
| Sequence (participants, messages, alt/opt/loop/par/break/critical) | Legend comments | Solid/dashed/dotted `->` `-->` `..>` |
| Component/Deployment (packages, subgraphs) | `classDef` directives | Solid/dashed/thick `-->` `-.->` `==>` |
| Class (inheritance, composition, interfaces) | N/A | All relation arrows |
| State (transitions) | N/A | Transitions |

**Zero external dependencies** -- uses only Python 3 standard library.

## Next Steps

After running the script, the ingestion-agent should:

1. **Check `conversion-manifest.json`** for any `"method": "vision_llm"` entries
2. **Run `preextract_diagram.py`** on those images (already done by script if deps available)
3. **Include pre-extracted context** in the LLM vision prompt
4. **Validate output** with `validate_mermaid.py` and retry up to 3 times
5. **Flag for manual review** -- vision outputs are non-deterministic

## Why Deterministic Parsing?

- **FREE** -- runs locally, no model API calls
- **Fast** -- no network latency
- **Deterministic** -- same input always produces same output
- **Cached** -- SHA256 content-addressed cache for instant re-ingestion
- **Validated** -- `mmdc --parse` catches syntax errors before they reach downstream agents
- **Accurate** -- parses actual diagram structure, not image interpretation
