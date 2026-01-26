---
name: image-to-mermaid
description: Convert diagram images to Mermaid syntax using OCR. Use when asked to convert image diagrams, extract diagrams from screenshots, or generate mermaid from images.
---

# Image to Mermaid Conversion

Convert diagram images (PNG, JPG) to Mermaid syntax using OCR.

## Usage

Run this Python script:

```bash
python governance/scripts/image_to_mermaid.py \
    --input <diagram.png> \
    --output governance/output/diagrams/
```

## How It Works

1. Uses OCR (Tesseract or Cloud Vision API) to extract text
2. Identifies diagram elements (boxes, arrows, labels)
3. Generates approximate Mermaid diagram syntax
4. May require manual cleanup for complex diagrams

## Example

```bash
python governance/scripts/image_to_mermaid.py \
    --input architecture-diagram.png \
    --output governance/output/diagrams/
```

## Limitations

- OCR accuracy depends on image quality
- Complex diagrams may need manual adjustment
- Works best with clear, high-contrast diagrams
- Flowcharts and sequence diagrams work best

## Output

Mermaid diagram files in `governance/output/diagrams/`
