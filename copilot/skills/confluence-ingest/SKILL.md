---
name: confluence-ingest
category: ingestion
description: Ingest Confluence pages by page ID, downloading content and all attachments, converting diagrams to Mermaid via deterministic parsing. All sources flow through a canonical DiagramAST; converters emit .ast.json and .mmd. Validates with mmdc, caches results by SHA256.
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
- **All diagram sources flow through AST** — `.ast.json` files are written alongside `.mmd` files

## Conversion Cascade: All Sources → AST → Mermaid

All diagram converters produce a canonical `DiagramAST` (defined in `diagram_ast.py`). The pipeline is: **source → AST → Mermaid**. Use `--ast-output` on converters to persist the AST.

| Source Type | Converter | Output | `--ast-output` |
|-------------|-----------|--------|----------------|
| Draw.io (`.drawio`) | `drawio_to_mermaid.py` | `.mmd` | Persists `.ast.json` |
| SVG (`.svg`) | `svg_to_mermaid.py` | `.mmd` | Persists `.ast.json` |
| PlantUML | `plantuml_to_mermaid.py` | `.mmd` | Persists `.ast.json` |
| PNG/JPG (image) | `image_to_ast.py` → LLM repair → `ast_to_mermaid.py` | `.mmd` | Partial AST → repaired AST |
| Mermaid macro | Extract CDATA as-is | `.mmd` | N/A |
| Markdown / Code Block / No Format / Excerpt | built-in | N/A | N/A |
| Cached result | SHA256 lookup | `.mmd` | From cache |

## Key Scripts

| Script | Purpose |
|--------|---------|
| `diagram_ast.py` | Canonical AST schema (`DiagramAST`, `DiagramNode`, `DiagramEdge`, `DiagramGroup`). Shared by all converters. Serializes to `.ast.json`; `generate_mermaid()` renders to Mermaid. |
| `ast_to_mermaid.py` | Converts any `.ast.json` to Mermaid. Usage: `python ast_to_mermaid.py --input diagram.ast.json [--output diagram.mmd]` |
| `image_to_ast.py` | Deterministic CV + OCR extraction from raster images. Produces **partial** AST with confidence scores. Output must be repaired by LLM before `ast_to_mermaid.py`. Usage: `python image_to_ast.py --input diagram.png [--output diagram.ast.json]` |
| `drawio_to_mermaid.py` | Draw.io XML → AST → Mermaid |
| `svg_to_mermaid.py` | SVG XML → AST → Mermaid |
| `plantuml_to_mermaid.py` | PlantUML → AST → Mermaid |
| `replace_diagrams.py` | Post-repair tool: auto-converts PlantUML, replaces image refs with Mermaid from `.mmd` files, and auto-fixes common Mermaid syntax errors. Runs AFTER LLM repair. Usage: `python replace_diagrams.py --page-dir governance/output/<PAGE_ID>` |
| `validate_mermaid.py` | Validates Mermaid syntax via `mmdc`. Usage: `python validate_mermaid.py --input diagram.mmd --json` |

## Setup (First Run Only)

```bash
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install -r requirements.txt

# Install Mermaid CLI for syntax validation
npm install

# Install Tesseract OCR (for image_to_ast.py CV pipeline)
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
| Diagram AST | `governance/output/<PAGE_ID>/attachments/<diagram>.ast.json` (alongside `.mmd`) |
| Cache | `governance/output/.cache/mermaid/<sha256>.mmd` |

## Validation

All generated Mermaid is validated using `mmdc --parse` via `validate_mermaid.py`. Invalid output:
- From deterministic paths (Draw.io, SVG): logged and falls through to next method
- From vision: retried up to 3 times with error feedback, then kept as image ref

```bash
# Validate a Mermaid file manually
python copilot/skills/confluence-ingest/validate_mermaid.py --input diagram.mmd --json
```

## Draw.io to Mermaid Conversion

Draw.io files (`.drawio` XML) are parsed deterministically — no LLM needed:

```bash
python copilot/skills/confluence-ingest/drawio_to_mermaid.py --input diagram.drawio [--ast-output diagram.ast.json]
```

## SVG to Mermaid Conversion

SVG files (vector XML) are parsed deterministically — no LLM needed:

```bash
python copilot/skills/confluence-ingest/svg_to_mermaid.py --input diagram.svg [--ast-output diagram.ast.json]
```

Handles:
- `<text>` elements as node labels
- `<rect>`, `<circle>`, `<ellipse>` as node shapes
- `<path>`, `<line>` with arrowheads as edges
- CSS `fill`, `stroke`, `stroke-dasharray` as colors and line styles
- Detects embedded raster images (falls back to vision)

## Image to Mermaid (PNG/JPG)

Raster images use the AST-first flow. See the `image-to-mermaid` skill for full steps:

1. `image_to_ast.py` — deterministic CV/OCR → partial `.ast.json`
2. LLM repair (mandatory) — correct the AST using the image
3. Save repaired `.ast.json`
4. `ast_to_mermaid.py` — AST → Mermaid

## PlantUML to Mermaid Conversion

PlantUML blocks (`@startuml`/`@enduml`, `` ```plantuml ``/`` ```puml ``) don't render natively in Markdown. This tool converts them to Mermaid automatically.

```bash
python copilot/skills/confluence-ingest/plantuml_to_mermaid.py --input <PAGE_MD> --output <PAGE_MD> [--ast-output diagram.ast.json]
```

### Supported Diagram Types

| Type | Preserves Colors | Preserves Line Styles |
|------|------------------|-----------------------|
| Sequence (participants, messages, alt/opt/loop/par/break/critical) | Legend comments | Solid/dashed/dotted `->` `-->` `..>` |
| Component/Deployment (packages, subgraphs) | `classDef` directives | Solid/dashed/thick `-->` `-.->` `==>` |
| Class (inheritance, composition, interfaces) | N/A | All relation arrows |
| State (transitions) | N/A | Transitions |

**Zero external dependencies** -- uses only Python 3 standard library.

## Post-Repair Diagram Replacement (replace_diagrams.py)

After LLM repair of image ASTs (Step 4 in ingestion-agent), run this **single command** to handle all remaining diagram work with zero LLM cost:

```bash
python copilot/skills/confluence-ingest/replace_diagrams.py --page-dir governance/output/<PAGE_ID>
```

This script runs three phases:

1. **PlantUML auto-detection** — finds and converts any `@startuml`/```plantuml/```puml blocks still in `page.md`
2. **Image-ref replacement** — reads `conversion-manifest.json` and `.mmd` files, replaces all `![](image)` refs with inline Mermaid
3. **Mermaid auto-fix** — patches unicode arrows, unclosed subgraphs, unquoted special-char labels

Use `--dry-run` to preview without writing:

```bash
python copilot/skills/confluence-ingest/replace_diagrams.py --page-dir governance/output/<PAGE_ID> --dry-run
```

The script is idempotent — running it twice produces the same result.

## Next Steps

After running the script and `replace_diagrams.py`, the ingestion-agent should:

1. **Convert remaining images** -- any PNG/JPG images that the script could not convert deterministically need LLM repair via the `image-to-mermaid` skill (Step 4)
2. **Run `replace_diagrams.py`** -- replaces all image references with Mermaid and auto-fixes syntax (Step 5)
3. **Validate** that page.md has zero `![` image references remaining
4. **Save** the final page.md to `governance/output/<PAGE_ID>/page.md`
5. **Copy to index** (if ingest mode) to `governance/indexes/<index>/<PAGE_ID>/`

## Why Deterministic Parsing?

- **FREE** -- runs locally, no model API calls
- **Fast** -- no network latency
- **Deterministic** -- same input always produces same output
- **Cached** -- SHA256 content-addressed cache for instant re-ingestion
- **Validated** -- `mmdc --parse` catches syntax errors before they reach downstream agents
- **Accurate** -- parses actual diagram structure, not image interpretation
