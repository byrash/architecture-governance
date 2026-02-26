#!/usr/bin/env python3
"""
Draw.io to AST Converter

Based on research from FlowForge (https://github.com/genkinsforge/FlowForge)
and the Draw.io shape mapping guide.

Parses Draw.io XML diagrams into a canonical DiagramAST with:
- Multi-page diagram support
- Enhanced style parsing for shapes and arrows
- Recursive group/subgraph handling
- Multiple decompression methods
- Semantic enrichment (roles, protocols, zones)
"""

import argparse
import sys
import re
import base64
import zlib
import gzip
import html
import urllib.parse
from pathlib import Path
from xml.etree import ElementTree as ET
from typing import List, Dict, Tuple, Optional, Set

from ingest.diagram_ast import (
    DiagramAST, DiagramNode, DiagramEdge, DiagramGroup,
    detect_direction, save_ast, enrich_ast,
)


# ──────────────────────────────────────────────────────────────────
# Draw.io specific parsing helpers
# ──────────────────────────────────────────────────────────────────

def parse_style_string(style: str) -> Dict[str, str]:
    """Parse Draw.io style string into dictionary."""
    result = {}
    if not style:
        return result
    for token in style.split(';'):
        token = token.strip()
        if '=' in token:
            key, value = token.split('=', 1)
            result[key.strip()] = value.strip()
        elif token:
            result[token] = "true"
    return result


def clean_label(value: str) -> str:
    """Clean HTML and special chars from label."""
    if not value:
        return ""
    value = html.unescape(value)
    value = re.sub(r'<br\s*/?>', ' ', value, flags=re.IGNORECASE)
    value = re.sub(r'<[^>]+>', '', value)
    value = value.replace('&nbsp;', ' ')
    value = value.replace('\n', ' ')
    value = value.replace('\r', '')
    value = ' '.join(value.split())
    value = value.replace('"', "'")
    return value.strip()


def detect_shape(style: Dict[str, str]) -> str:
    """Detect canonical shape from Draw.io style (FlowForge mapping)."""
    shape = style.get('shape', '').lower()
    shape_mappings = {
        'cylinder': 'database', 'database': 'database', 'datastore': 'database',
        'rhombus': 'diamond', 'diamond': 'diamond',
        'mxgraph.flowchart.decision': 'diamond',
        'ellipse': 'circle', 'doubleellipse': 'circle',
        'mxgraph.flowchart.terminator': 'stadium',
        'mxgraph.flowchart.start': 'circle',
        'parallelogram': 'parallelogram',
        'mxgraph.flowchart.data': 'parallelogram',
        'hexagon': 'hexagon',
        'process': 'rectangle', 'mxgraph.flowchart.process': 'rectangle',
    }
    for key, canonical_shape in shape_mappings.items():
        if key in shape:
            return canonical_shape
    if style.get('rounded') == '1':
        return 'stadium'
    if 'ellipse' in style:
        return 'circle'
    if 'swimlane' in style or style.get('swimlane') == '1':
        return 'group'
    if 'group' in style or style.get('group') == '1':
        return 'group'
    return 'rectangle'


def detect_edge_style(style: Dict[str, str]) -> str:
    """Detect canonical edge style from Draw.io style."""
    if style.get('dashed') == '1' or 'dashed' in style:
        return 'dashed'
    if style.get('dotted') == '1':
        return 'dotted'
    stroke_width = style.get('strokeWidth', '1')
    try:
        if int(stroke_width) >= 3:
            return 'thick'
    except ValueError:
        pass
    return 'solid'


def has_arrow(style: Dict[str, str], end: str = 'end') -> bool:
    """Check if edge has arrow at specified end."""
    key = f'{end}Arrow'
    arrow = style.get(key, 'classic')
    return arrow.lower() not in ('none', 'open', '')


def extract_colors(style: Dict[str, str]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Extract fill, stroke, and font colors from Draw.io style."""
    skip_values = {'none', 'default', '', '#ffffff', '#FFFFFF', 'white'}
    fill = style.get('fillColor', '').strip()
    stroke = style.get('strokeColor', '').strip()
    font = style.get('fontColor', '').strip()
    fill_color = fill if fill and fill.lower() not in skip_values else None
    stroke_color = stroke if stroke and stroke.lower() not in skip_values else None
    font_color = font if font and font.lower() not in skip_values else None
    return fill_color, stroke_color, font_color


# ──────────────────────────────────────────────────────────────────
# Compression / page extraction
# ──────────────────────────────────────────────────────────────────

def decompress_diagram_data(data: str) -> Optional[str]:
    """Decompress Draw.io diagram data (URL encoding + Base64 + Deflate)."""
    if not data or data.strip().startswith('<'):
        return data
    data = data.strip()
    try:
        decoded_str = urllib.parse.unquote(data)
    except Exception:
        decoded_str = data
    try:
        decoded_bytes = base64.b64decode(decoded_str)
    except Exception:
        return None
    methods = [
        lambda d: zlib.decompress(d, -15),
        lambda d: zlib.decompress(d, -zlib.MAX_WBITS),
        lambda d: zlib.decompress(d),
        lambda d: zlib.decompress(d, zlib.MAX_WBITS),
        lambda d: gzip.decompress(d),
        lambda d: zlib.decompress(d, 16 + zlib.MAX_WBITS),
    ]
    for method in methods:
        try:
            decompressed = method(decoded_bytes)
            xml_text = decompressed.decode('utf-8', errors='replace')
            if '<mxGraphModel' in xml_text or '<mxCell' in xml_text:
                return xml_text
        except Exception:
            continue
    return None


def extract_diagram_pages(content: str) -> List[str]:
    """Extract all diagram pages from Draw.io file."""
    pages: List[str] = []
    if '<mxGraphModel' in content:
        pages.append(content)
        return pages
    diagram_matches = re.findall(r'<diagram[^>]*>(.*?)</diagram>', content, re.DOTALL)
    if diagram_matches:
        for diagram_data in diagram_matches:
            diagram_data = diagram_data.strip()
            if not diagram_data:
                continue
            if diagram_data.startswith('<'):
                pages.append(diagram_data)
            else:
                decompressed = decompress_diagram_data(diagram_data)
                if decompressed:
                    pages.append(decompressed)
    else:
        try:
            root = ET.fromstring(content)
            if root.tag == 'mxfile':
                for diagram in root.findall('diagram'):
                    diagram_content = diagram.text or ""
                    if diagram_content.strip():
                        decompressed = decompress_diagram_data(diagram_content.strip())
                        if decompressed:
                            pages.append(decompressed)
        except ET.ParseError:
            pass
    return pages


def parse_diagram_xml(xml_content: str) -> Optional[ET.Element]:
    """Parse diagram XML and return root element."""
    try:
        return ET.fromstring(xml_content)
    except ET.ParseError:
        match = re.search(r'<mxGraphModel[^>]*>.*?</mxGraphModel>', xml_content, re.DOTALL)
        if match:
            try:
                return ET.fromstring(match.group(0))
            except ET.ParseError:
                pass
    return None


# ──────────────────────────────────────────────────────────────────
# Graph extraction → DiagramAST
# ──────────────────────────────────────────────────────────────────

def extract_graph_elements(root: ET.Element) -> DiagramAST:
    """Extract nodes, edges, and groups from parsed XML into a DiagramAST."""
    nodes: List[DiagramNode] = []
    edges: List[DiagramEdge] = []
    groups: Dict[str, DiagramGroup] = {}

    cell_parents: Dict[str, str] = {}
    parent_children: Dict[str, List[str]] = {}
    edge_counter = 0

    for cell in root.iter('mxCell'):
        cell_id = cell.get('id', '')
        parent_id = cell.get('parent', '')
        if cell_id and parent_id:
            cell_parents[cell_id] = parent_id
            if parent_id not in parent_children:
                parent_children[parent_id] = []
            parent_children[parent_id].append(cell_id)

    for cell in root.iter('mxCell'):
        cell_id = cell.get('id', '')
        value = cell.get('value', '')
        source = cell.get('source')
        target = cell.get('target')
        style_str = cell.get('style', '')
        parent_id = cell.get('parent', '')
        vertex = cell.get('vertex', '')
        edge_attr = cell.get('edge', '')

        if cell_id in ('0', '1', ''):
            continue

        style = parse_style_string(style_str)
        label = clean_label(value)
        shape = detect_shape(style)

        x, y, w, h = 0.0, 0.0, 0.0, 0.0
        geometry = cell.find('mxGeometry')
        if geometry is not None:
            try:
                x = float(geometry.get('x', 0))
                y = float(geometry.get('y', 0))
                w = float(geometry.get('width', 0))
                h = float(geometry.get('height', 0))
            except ValueError:
                pass

        if edge_attr == '1' or (source and target):
            edge_counter += 1
            edge_style = detect_edge_style(style)
            arrow_at_end = has_arrow(style, 'end')
            arrow_at_start = has_arrow(style, 'start')
            edges.append(DiagramEdge(
                id=f"edge_{edge_counter}",
                source=source or '',
                target=target or '',
                label=label,
                style=edge_style,
                arrow_start=arrow_at_start,
                arrow_end=arrow_at_end,
            ))
        elif shape == 'group' or cell_id in parent_children:
            if label or cell_id in parent_children:
                groups[cell_id] = DiagramGroup(
                    id=cell_id,
                    label=label or f"Group_{cell_id[-4:]}",
                    children=parent_children.get(cell_id, []),
                )
        elif vertex == '1' or (label and edge_attr != '1'):
            if shape == 'group':
                groups[cell_id] = DiagramGroup(id=cell_id, label=label, children=[])
                continue

            fill_color, stroke_color, font_color = extract_colors(style)
            nodes.append(DiagramNode(
                id=cell_id,
                label=label if label else f"Node_{cell_id[-4:]}",
                shape=shape,
                x=x, y=y, width=w, height=h,
                parent_group=parent_id if parent_id not in ('0', '1') else None,
                fill_color=fill_color,
                stroke_color=stroke_color,
                font_color=font_color,
            ))

    for node in nodes:
        if node.parent_group and node.parent_group in groups:
            groups[node.parent_group].children.append(node.id)

    direction = detect_direction(nodes)

    return DiagramAST(
        nodes=nodes,
        edges=edges,
        groups=list(groups.values()),
        diagram_type='flowchart',
        direction=direction,
        metadata={'source_format': 'drawio', 'extraction_method': 'xml_parse'},
    )


# ──────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────

def convert_drawio_to_ast(input_path: Path, page_index: int = 0) -> DiagramAST:
    """Parse a .drawio file and return a DiagramAST."""
    with open(input_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    pages = extract_diagram_pages(content)
    if not pages:
        print(f"  Warning: No diagram pages found in file", file=sys.stderr)
        return DiagramAST(metadata={'source_format': 'drawio', 'error': 'no_pages'})

    if page_index >= len(pages):
        print(f"  Warning: Page index {page_index} out of range (found {len(pages)} pages)", file=sys.stderr)
        page_index = 0

    xml_content = pages[page_index]
    root = parse_diagram_xml(xml_content)
    if root is None:
        print(f"  Warning: Could not parse XML structure", file=sys.stderr)
        return DiagramAST(metadata={'source_format': 'drawio', 'error': 'xml_parse_failed'})

    ast = extract_graph_elements(root)
    ast.metadata['source_file'] = str(input_path)
    ast.metadata['page_index'] = page_index
    ast.metadata['total_pages'] = len(pages)

    print(f"  Extracted: {len(ast.nodes)} nodes, {len(ast.edges)} edges, {len(ast.groups)} groups", file=sys.stderr)
    if len(pages) > 1:
        print(f"  Multi-page file: converted page {page_index + 1} of {len(pages)}", file=sys.stderr)

    enrich_ast(ast)
    return ast


# ──────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Convert Draw.io diagrams to AST JSON",
        epilog="Based on FlowForge research (https://github.com/genkinsforge/FlowForge)",
    )
    parser.add_argument("--input", "-i", required=True, help="Input .drawio file")
    parser.add_argument("--output", "-o", required=True, help="Output .ast.json path")
    parser.add_argument("--page", "-p", type=int, default=0, help="Page index (0-based)")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    ast = convert_drawio_to_ast(input_path, args.page)
    save_ast(ast, args.output)
    print(f"  AST written to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
