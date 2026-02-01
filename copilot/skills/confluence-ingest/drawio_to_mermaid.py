#!/usr/bin/env python3
"""
Draw.io to Mermaid Converter
Converts draw.io XML diagrams to Mermaid syntax.
"""

import argparse
import sys
import re
import base64
import zlib
import urllib.parse
from pathlib import Path
from xml.etree import ElementTree as ET
from typing import List, Dict, Tuple


def decode_drawio_data(data: str) -> str:
    """Decode draw.io compressed/encoded data."""
    try:
        # URL decode
        decoded = urllib.parse.unquote(data)
        # Base64 decode
        decoded = base64.b64decode(decoded)
        # Inflate (decompress)
        decoded = zlib.decompress(decoded, -15)
        return decoded.decode('utf-8')
    except Exception:
        return data


def parse_drawio_xml(xml_content: str) -> Tuple[List[Dict], List[Dict]]:
    """Parse draw.io XML and extract nodes and edges."""
    nodes = []
    edges = []
    
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError:
        # Try to find embedded diagram data
        match = re.search(r'<diagram[^>]*>(.*?)</diagram>', xml_content, re.DOTALL)
        if match:
            diagram_data = match.group(1)
            decoded = decode_drawio_data(diagram_data)
            try:
                root = ET.fromstring(decoded)
            except Exception:
                return nodes, edges
        else:
            return nodes, edges
    
    # Find all mxCell elements
    for cell in root.iter():
        if cell.tag == 'mxCell':
            cell_id = cell.get('id', '')
            value = cell.get('value', '').strip()
            source = cell.get('source')
            target = cell.get('target')
            
            # Skip root and layer cells
            if cell_id in ['0', '1'] or not value:
                if source and target:
                    # Edge without label
                    edges.append({
                        'source': source,
                        'target': target,
                        'label': ''
                    })
                continue
            
            if source and target:
                # This is an edge
                edges.append({
                    'source': source,
                    'target': target,
                    'label': value
                })
            else:
                # This is a node
                nodes.append({
                    'id': cell_id,
                    'label': re.sub(r'<[^>]+>', '', value)  # Strip HTML
                })
    
    return nodes, edges


def generate_mermaid(nodes: List[Dict], edges: List[Dict]) -> str:
    """Generate Mermaid flowchart from nodes and edges."""
    if not nodes and not edges:
        return "```mermaid\nflowchart TB\n    A[No diagram data extracted]\n```"
    
    lines = ["```mermaid", "flowchart TB"]
    
    # Create ID mapping for cleaner Mermaid IDs
    id_map = {}
    for i, node in enumerate(nodes):
        clean_id = f"N{i}"
        id_map[node['id']] = clean_id
        label = node['label'].replace('"', "'")
        lines.append(f'    {clean_id}["{label}"]')
    
    # Add edges
    for edge in edges:
        source = id_map.get(edge['source'], edge['source'])
        target = id_map.get(edge['target'], edge['target'])
        label = edge.get('label', '')
        
        if label:
            label = label.replace('"', "'")
            lines.append(f'    {source} -->|"{label}"| {target}')
        else:
            lines.append(f'    {source} --> {target}')
    
    lines.append("```")
    return '\n'.join(lines)


def convert_drawio_to_mermaid(input_path: Path) -> str:
    """Main conversion function."""
    with open(input_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    nodes, edges = parse_drawio_xml(content)
    return generate_mermaid(nodes, edges)


def main():
    parser = argparse.ArgumentParser(description="Convert draw.io to Mermaid")
    parser.add_argument("--input", "-i", required=True, help="Input .drawio file")
    parser.add_argument("--output", "-o", help="Output .mmd file (optional, prints to stdout if not provided)")
    args = parser.parse_args()
    
    input_path = Path(args.input)
    
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)
    
    mermaid = convert_drawio_to_mermaid(input_path)
    
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(mermaid)
        print(f"Output written to {output_path}", file=sys.stderr)
    
    # Always print to stdout for programmatic use
    print(mermaid)


if __name__ == "__main__":
    main()
