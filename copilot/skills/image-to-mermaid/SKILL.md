---
name: image-to-mermaid
category: ingestion
description: Convert architecture diagram images (PNG, JPG) to Mermaid syntax by reading the image and reproducing it as a Mermaid code block. Preserve all colors, shapes, labels, and line styles.
---

# Image to Mermaid Conversion

Convert diagram images to Mermaid syntax by reading the image file and reproducing its structure.

**Note:** The ingestion script already converts Draw.io (`.drawio`) and SVG files to Mermaid via XML parsing. This skill handles PNG/JPG images that remain as `![...](...)` references in page.md.

## Optional: Pre-Extraction for Better Accuracy

If Tesseract and OpenCV are installed, run pre-extraction to get OCR labels and colors. This improves accuracy but is **not required** -- skip if it fails:

```bash
python copilot/skills/confluence-ingest/preextract_diagram.py --input <IMAGE_PATH> --format-prompt
```

If successful, include the OCR labels and hex colors in your reasoning. If it fails, proceed with visual inspection only.

## Instructions

1. **Read the image file**
2. If pre-extracted context (`.context.json`) is available, use the exact OCR labels and hex colors
3. **Reproduce the diagram in Mermaid** preserving ALL of the following:

| Property | What to Preserve | Mermaid Feature |
|----------|-----------------|-----------------|
| **Node colors** | Background fill, border, text color | `style` or `classDef` directives |
| **Node shapes** | Rectangles, cylinders, diamonds, circles | Mermaid shape syntax (`[]`, `[()]`, `{}`, `(())`) |
| **Line styles** | Solid, dashed, thick | `-->`, `-.->`, `==>` |
| **Arrow direction** | Forward, bidirectional, reverse, no-arrow | `-->`, `<-->`, `<--`, `---` |
| **Edge labels** | Protocol names, descriptions on lines | `-->\|label\|` syntax |
| **Grouping** | Boxes/boundaries around component clusters | `subgraph` blocks |
| **Layout direction** | Top-to-bottom vs left-to-right | `flowchart TB` vs `flowchart LR` |

3. **Add a visual legend comment** at the bottom documenting color meanings and any line style conventions

**Why this matters**: Downstream agents (rules-extraction, validation) use colors to identify component types (internal vs vendor), line styles to infer coupling and criticality, and arrow directions to determine data flow rules. Stripping ANY visual property loses governance context.

## Example

**Input:** Read `governance/output/123/attachments/architecture.png`

Image shows:
- Dark blue internal services
- Orange external vendor
- Green database
- Solid arrows for synchronous calls with protocol labels
- Dashed arrow for async event
- Thick arrow for primary data path
- Bidirectional arrow between two tightly-coupled services

**Output:**

```mermaid
flowchart TB
    classDef internal fill:#4472C4,stroke:#2F5597,color:#FFFFFF
    classDef external fill:#ED7D31,stroke:#C55A11,color:#FFFFFF
    classDef datastore fill:#70AD47,stroke:#548235,color:#FFFFFF

    subgraph Internal_Zone["Internal Zone"]
        GW[API Gateway]:::internal
        Auth[Auth Service]:::internal
        User[User Service]:::internal
        Notif[Notification Service]:::internal
    end

    Vendor[Vendor API]:::external
    DB[(Database)]:::datastore

    Vendor -->|HTTPS| GW
    GW -->|mTLS| Auth
    GW ==>|REST| User
    User <--> Auth
    User -->|encrypted| DB
    User -.->|event| Notif

    %% Visual Legend:
    %% Colors:
    %%   Dark Blue (#4472C4) = Internal firm applications
    %%   Orange (#ED7D31) = External vendor
    %%   Green (#70AD47) = Database / data store
    %% Line Styles:
    %%   Solid arrow (-->) = Synchronous dependency
    %%   Thick arrow (==>) = Primary / critical data path
    %%   Dashed arrow (-.->) = Async / event-driven
    %%   Bidirectional (<-->) = Tightly coupled, mutual dependency
```

## Color Preservation

**CRITICAL**: Always preserve the color scheme from the original diagram.

### How to Capture Colors

| What to Look For | Mermaid Syntax |
|-------------------|----------------|
| Node background color | `style NodeID fill:#hex` |
| Node border color | `style NodeID stroke:#hex` |
| Node text color | `style NodeID color:#hex` |
| Multiple properties | `style NodeID fill:#hex,stroke:#hex,color:#hex` |

### Using classDef for Repeated Colors

When multiple nodes share the same color, use `classDef` for efficiency:

```mermaid
flowchart TB
    classDef internal fill:#4472C4,stroke:#2F5597,color:#FFFFFF
    classDef external fill:#ED7D31,stroke:#C55A11,color:#FFFFFF
    classDef datastore fill:#70AD47,stroke:#548235,color:#FFFFFF

    A[Auth Service]:::internal
    B[User Service]:::internal
    C[Vendor API]:::external
    D[(Database)]:::datastore
```

## Line Style Preservation

**CRITICAL**: Preserve the exact line style and arrow direction from the original diagram. Each combination carries different architectural meaning.

### Line Styles

| Visual in Image | Mermaid Syntax | Governance Meaning |
|----------------|----------------|-------------------|
| Solid line with arrow | `A --> B` | Confirmed, required dependency |
| Dashed/dotted line with arrow | `A -.-> B` | Optional, async, or event-driven |
| Thick/bold line with arrow | `A ==> B` | Critical path, high throughput, primary flow |

### Arrow Directions

| Visual in Image | Solid | Dashed | Thick |
|----------------|-------|--------|-------|
| Single arrow (A to B) | `A --> B` | `A -.-> B` | `A ==> B` |
| Double arrow (both ways) | `A <--> B` | `A <-.-> B` | `A <==> B` |
| Reverse arrow (B to A) | `A <-- B` | `A <-.- B` | `A <== B` |
| No arrow (plain line) | `A --- B` | `A -.- B` | `A === B` |

### With Labels

| Direction | Solid | Dashed | Thick |
|-----------|-------|--------|-------|
| Forward | `A -->\|label\| B` | `A -.->\|label\| B` | `A ==>\|label\| B` |
| Bidirectional | `A <-->\|label\| B` | `A <-.->\|label\| B` | `A <==>\|label\| B` |

## Mermaid Types

| Diagram Type      | Use                                      |
| ----------------- | ---------------------------------------- |
| `flowchart TB`    | Architecture, components (top-to-bottom) |
| `flowchart LR`    | Processes, pipelines (left-to-right)     |
| `sequenceDiagram` | Request/response flows                   |
| `classDiagram`    | Class relationships                      |
| `erDiagram`       | Database schemas                         |
| `stateDiagram-v2` | State machines                           |

## Node Shapes

| Type        | Syntax      |
| ----------- | ----------- |
| Service/Box | `A[Name]`   |
| Database    | `A[(Name)]` |
| Decision    | `A{Name}`   |
| Process     | `A([Name])` |
| Circle      | `A((Name))` |
| Hexagon     | `A{{Name}}`  |

## Visual Legend Comment

Always add a `%% Visual Legend` comment block at the end of every Mermaid diagram documenting:

```
%% Visual Legend:
%% Colors:
%%   <hex> = <what it represents>
%% Line Styles:
%%   <style> = <what it represents>
%% Subgraphs:
%%   <name> = <boundary meaning>
```

This helps downstream validation and rules-extraction agents interpret the full diagram semantics without needing the original image.

## Post-Conversion Validation

After generating Mermaid, optionally validate syntax if the tool is available:

```bash
python copilot/skills/confluence-ingest/validate_mermaid.py --code "<MERMAID_CODE>" --json
```

If validation fails, read the error, fix the syntax, and retry (max 3 attempts). If the validator is not available, proceed without it.
