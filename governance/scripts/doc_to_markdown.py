#!/usr/bin/env python3
"""
Document to Markdown Converter
Converts PDF or HTML documents to normalized Markdown format.
Also detects embedded diagram references (.drawio, .png) for further processing.
"""

import argparse
import sys
import re
from pathlib import Path
from datetime import datetime
from typing import List

# Optional imports - graceful fallback
try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False


def find_diagram_references(content: str, base_path: Path) -> List[str]:
    """Find references to diagram files (.drawio, .png, .jpg) in the content."""
    diagrams = []
    
    # Find .drawio references
    drawio_pattern = r'[\w\-]+\.drawio'
    for match in re.findall(drawio_pattern, content, re.IGNORECASE):
        diagram_path = base_path.parent / match
        if diagram_path.exists():
            diagrams.append(str(diagram_path))
        else:
            # Also check in same directory as input
            diagrams.append(match)
    
    # Find image references that might be diagrams
    img_pattern = r'[\w\-]+(?:diagram|architecture|flow|sequence)[\w\-]*\.(?:png|jpg|jpeg)'
    for match in re.findall(img_pattern, content, re.IGNORECASE):
        diagram_path = base_path.parent / match
        if diagram_path.exists():
            diagrams.append(str(diagram_path))
    
    return list(set(diagrams))


def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract text content from PDF file."""
    if not HAS_PDFPLUMBER:
        return f"[PDF extraction requires pdfplumber. Install with: pip install pdfplumber]\n\nFile: {pdf_path}"
    
    text_parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""
            if text.strip():
                text_parts.append(f"<!-- Page {i} -->\n{text}")
    
    return "\n\n".join(text_parts)


def extract_text_from_html(html_path: Path) -> tuple:
    """Extract text content from HTML file (Confluence export).
    Returns (text, list of diagram references)."""
    diagrams = []
    
    with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
        raw_content = f.read()
    
    # Find diagram references before processing
    diagrams = find_diagram_references(raw_content, html_path)
    
    if not HAS_BS4:
        # Fallback: basic text extraction
        text = re.sub(r'<[^>]+>', ' ', raw_content)
        text = re.sub(r'\s+', ' ', text)
        return text.strip(), diagrams
    
    soup = BeautifulSoup(raw_content, 'html.parser')
    
    # Remove script and style elements
    for element in soup(['script', 'style', 'nav', 'footer']):
        element.decompose()
    
    # Extract text
    text = soup.get_text(separator='\n')
    
    # Clean up whitespace
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return '\n\n'.join(lines), diagrams


def convert_to_markdown(input_path: Path) -> tuple:
    """Convert input document to Markdown format.
    Returns (markdown_content, list of diagram references)."""
    suffix = input_path.suffix.lower()
    diagrams = []
    
    if suffix == '.pdf':
        content = extract_text_from_pdf(input_path)
    elif suffix in ['.html', '.htm']:
        content, diagrams = extract_text_from_html(input_path)
    elif suffix == '.md':
        with open(input_path, 'r', encoding='utf-8') as f:
            content = f.read()
        diagrams = find_diagram_references(content, input_path)
    else:
        # Try as plain text
        with open(input_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    
    # Build normalized Markdown
    md = []
    md.append("# Architecture Document")
    md.append("")
    md.append(f"**Source**: `{input_path.name}`")
    md.append(f"**Converted**: {datetime.now().isoformat()}")
    md.append("")
    md.append("---")
    md.append("")
    md.append("## Content")
    md.append("")
    md.append(content)
    
    return '\n'.join(md), diagrams


def main():
    parser = argparse.ArgumentParser(description="Convert documents to Markdown")
    parser.add_argument("--input", "-i", required=True, help="Input file path")
    parser.add_argument("--output", "-o", required=True, help="Output Markdown file path")
    args = parser.parse_args()
    
    input_path = Path(args.input)
    output_path = Path(args.output)
    
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)
    
    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"Converting {input_path} to Markdown...", file=sys.stderr)
    
    markdown, diagrams = convert_to_markdown(input_path)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(markdown)
    
    print(f"Output written to {output_path}", file=sys.stderr)
    
    # Report diagrams found for further processing
    if diagrams:
        print(f"", file=sys.stderr)
        print(f"📊 Diagrams found that need conversion:", file=sys.stderr)
        for d in diagrams:
            if d.endswith('.drawio'):
                print(f"   • {d} → run drawio_to_mermaid.py", file=sys.stderr)
            else:
                print(f"   • {d} → run image_to_mermaid.py", file=sys.stderr)


if __name__ == "__main__":
    main()
