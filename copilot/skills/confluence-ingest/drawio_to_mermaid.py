#!/usr/bin/env python3
"""
Draw.io to Mermaid Converter (Enhanced)

Based on research from FlowForge (https://github.com/genkinsforge/FlowForge)
and the Draw.io to Mermaid mapping guide.

Converts Draw.io XML diagrams to Mermaid syntax with:
- Multi-page diagram support
- Enhanced style parsing for shapes and arrows
- Recursive group/subgraph handling
- Multiple decompression methods
- Reserved word escaping
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
from dataclasses import dataclass, field


# Mermaid reserved words that need escaping
MERMAID_RESERVED = {'end', 'graph', 'flowchart', 'subgraph', 'direction', 'click', 'style', 'classDef', 'class'}


@dataclass
class Node:
    """Represents a diagram node/shape."""
    id: str
    label: str
    shape: str = "rectangle"
    parent: Optional[str] = None
    is_group: bool = False
    x: float = 0
    y: float = 0
    fill_color: Optional[str] = None
    stroke_color: Optional[str] = None
    font_color: Optional[str] = None


@dataclass
class Edge:
    """Represents a connection between nodes."""
    source: str
    target: str
    label: str = ""
    style: str = "solid"  # solid, dashed, dotted, thick
    arrow_start: bool = False  # arrow at source end (for bidirectional)
    arrow_end: bool = True     # arrow at target end (default)


@dataclass  
class Group:
    """Represents a subgraph/container."""
    id: str
    label: str
    children: List[str] = field(default_factory=list)


def parse_style_string(style: str) -> Dict[str, str]:
    """
    Parse Draw.io style string into dictionary.
    Style format: "key1=value1;key2=value2;flag1;flag2"
    """
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
    
    # Decode HTML entities
    value = html.unescape(value)
    # Remove HTML tags
    value = re.sub(r'<br\s*/?>', ' ', value, flags=re.IGNORECASE)
    value = re.sub(r'<[^>]+>', '', value)
    # Clean special chars
    value = value.replace('&nbsp;', ' ')
    value = value.replace('\n', ' ')
    value = value.replace('\r', '')
    # Normalize whitespace
    value = ' '.join(value.split())
    # Escape quotes for Mermaid
    value = value.replace('"', "'")
    
    return value.strip()


def make_safe_id(label: str, used_ids: Set[str], cell_id: str) -> str:
    """Generate a safe Mermaid node ID from label."""
    if not label:
        base_id = f"node_{cell_id[-6:]}" if len(cell_id) > 6 else f"node_{cell_id}"
    else:
        # Convert to safe identifier
        base_id = re.sub(r'[^a-zA-Z0-9]', '_', label)
        base_id = re.sub(r'_+', '_', base_id)
        base_id = base_id.strip('_')[:20]  # Limit length
        
        if not base_id or base_id[0].isdigit():
            base_id = f"n_{base_id}"
    
    # Avoid reserved words
    if base_id.lower() in MERMAID_RESERVED:
        base_id = f"{base_id}_node"
    
    # Ensure uniqueness
    final_id = base_id
    counter = 1
    while final_id in used_ids:
        final_id = f"{base_id}_{counter}"
        counter += 1
    
    used_ids.add(final_id)
    return final_id


def detect_shape(style: Dict[str, str]) -> str:
    """
    Detect Mermaid shape from Draw.io style.
    Based on FlowForge mapping table.
    """
    shape = style.get('shape', '').lower()
    
    # Check for specific shapes
    shape_mappings = {
        # Database/cylinder
        'cylinder': 'database',
        'database': 'database',
        'datastore': 'database',
        
        # Diamond/decision
        'rhombus': 'diamond',
        'diamond': 'diamond',
        'mxgraph.flowchart.decision': 'diamond',
        
        # Circle/ellipse (start/end)
        'ellipse': 'circle',
        'doubleellipse': 'circle',
        'mxgraph.flowchart.terminator': 'stadium',
        'mxgraph.flowchart.start': 'circle',
        
        # Parallelogram (input/output)
        'parallelogram': 'parallelogram',
        'mxgraph.flowchart.data': 'parallelogram',
        
        # Hexagon
        'hexagon': 'hexagon',
        
        # Process
        'process': 'rectangle',
        'mxgraph.flowchart.process': 'rectangle',
    }
    
    for key, mermaid_shape in shape_mappings.items():
        if key in shape:
            return mermaid_shape
    
    # Check style flags
    if style.get('rounded') == '1':
        return 'stadium'
    
    if 'ellipse' in style:
        return 'circle'
    
    # Swimlane/group detection
    if 'swimlane' in style or style.get('swimlane') == '1':
        return 'group'
    
    if 'group' in style or style.get('group') == '1':
        return 'group'
    
    return 'rectangle'


def detect_edge_style(style: Dict[str, str]) -> str:
    """Detect Mermaid edge style from Draw.io style."""
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
    """
    Extract fill, stroke, and font colors from Draw.io style.
    Returns (fill_color, stroke_color, font_color) as hex strings or None.
    Skips default/white/none colors.
    """
    skip_values = {'none', 'default', '', '#ffffff', '#FFFFFF', 'white'}

    fill = style.get('fillColor', '').strip()
    stroke = style.get('strokeColor', '').strip()
    font = style.get('fontColor', '').strip()

    fill_color = fill if fill and fill.lower() not in skip_values else None
    stroke_color = stroke if stroke and stroke.lower() not in skip_values else None
    font_color = font if font and font.lower() not in skip_values else None

    return fill_color, stroke_color, font_color


def decompress_diagram_data(data: str) -> Optional[str]:
    """
    Decompress Draw.io diagram data using multiple methods.
    Draw.io uses URL encoding + Base64 + Deflate compression.
    """
    if not data or data.strip().startswith('<'):
        return data
    
    data = data.strip()
    
    # Try URL decode first
    try:
        decoded_str = urllib.parse.unquote(data)
    except Exception:
        decoded_str = data
    
    # Try Base64 decode
    try:
        decoded_bytes = base64.b64decode(decoded_str)
    except Exception:
        return None
    
    # Try multiple decompression methods (from FlowForge)
    decompression_methods = [
        # Raw deflate (most common for Draw.io)
        lambda d: zlib.decompress(d, -15),
        lambda d: zlib.decompress(d, -zlib.MAX_WBITS),
        # Zlib with header
        lambda d: zlib.decompress(d),
        lambda d: zlib.decompress(d, zlib.MAX_WBITS),
        # Gzip
        lambda d: gzip.decompress(d),
        # Gzip via zlib
        lambda d: zlib.decompress(d, 16 + zlib.MAX_WBITS),
    ]
    
    for method in decompression_methods:
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
    pages = []
    
    # First check if it's already uncompressed XML
    if '<mxGraphModel' in content:
        pages.append(content)
        return pages
    
    # Find all <diagram> tags
    diagram_matches = re.findall(r'<diagram[^>]*>(.*?)</diagram>', content, re.DOTALL)
    
    if diagram_matches:
        for diagram_data in diagram_matches:
            diagram_data = diagram_data.strip()
            if not diagram_data:
                continue
            
            # If already XML, use directly
            if diagram_data.startswith('<'):
                pages.append(diagram_data)
            else:
                # Try to decompress
                decompressed = decompress_diagram_data(diagram_data)
                if decompressed:
                    pages.append(decompressed)
    else:
        # Try parsing as mxfile directly
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
        # Try to extract mxGraphModel
        match = re.search(r'<mxGraphModel[^>]*>.*?</mxGraphModel>', xml_content, re.DOTALL)
        if match:
            try:
                return ET.fromstring(match.group(0))
            except ET.ParseError:
                pass
    return None


def extract_graph_elements(root: ET.Element) -> Tuple[List[Node], List[Edge], Dict[str, Group]]:
    """Extract nodes, edges, and groups from parsed XML."""
    nodes = []
    edges = []
    groups: Dict[str, Group] = {}
    
    # Track parent-child relationships
    cell_parents: Dict[str, str] = {}
    parent_children: Dict[str, List[str]] = {}
    
    # First pass: collect parent relationships
    for cell in root.iter('mxCell'):
        cell_id = cell.get('id', '')
        parent_id = cell.get('parent', '')
        if cell_id and parent_id:
            cell_parents[cell_id] = parent_id
            if parent_id not in parent_children:
                parent_children[parent_id] = []
            parent_children[parent_id].append(cell_id)
    
    # Second pass: extract nodes and edges
    for cell in root.iter('mxCell'):
        cell_id = cell.get('id', '')
        value = cell.get('value', '')
        source = cell.get('source')
        target = cell.get('target')
        style_str = cell.get('style', '')
        parent_id = cell.get('parent', '')
        vertex = cell.get('vertex', '')
        edge_attr = cell.get('edge', '')
        
        # Skip root cells
        if cell_id in ['0', '1', '']:
            continue
        
        style = parse_style_string(style_str)
        label = clean_label(value)
        shape = detect_shape(style)
        
        # Get geometry for positioning hints
        x, y = 0.0, 0.0
        geometry = cell.find('mxGeometry')
        if geometry is not None:
            try:
                x = float(geometry.get('x', 0))
                y = float(geometry.get('y', 0))
            except ValueError:
                pass
        
        # Check if this is an edge
        if edge_attr == '1' or (source and target):
            edge_style = detect_edge_style(style)
            arrow_at_end = has_arrow(style, 'end')
            arrow_at_start = has_arrow(style, 'start')
            edges.append(Edge(
                source=source or '',
                target=target or '',
                label=label,
                style=edge_style,
                arrow_start=arrow_at_start,
                arrow_end=arrow_at_end,
            ))
        # Check if this is a group/container
        elif shape == 'group' or cell_id in parent_children:
            if label or cell_id in parent_children:
                groups[cell_id] = Group(
                    id=cell_id,
                    label=label or f"Group_{cell_id[-4:]}",
                    children=parent_children.get(cell_id, [])
                )
        # Regular vertex/node
        elif vertex == '1' or (label and edge_attr != '1'):
            # Skip if this is a group container style
            if shape == 'group':
                groups[cell_id] = Group(id=cell_id, label=label, children=[])
                continue
            
            fill_color, stroke_color, font_color = extract_colors(style)
            
            nodes.append(Node(
                id=cell_id,
                label=label if label else f"Node_{cell_id[-4:]}",
                shape=shape,
                parent=parent_id if parent_id not in ['0', '1'] else None,
                x=x,
                y=y,
                fill_color=fill_color,
                stroke_color=stroke_color,
                font_color=font_color,
            ))
    
    # Assign children to groups
    for node in nodes:
        if node.parent and node.parent in groups:
            groups[node.parent].children.append(node.id)
    
    return nodes, edges, groups


def detect_direction(nodes: List[Node]) -> str:
    """Detect flow direction from node positions (TB vs LR)."""
    if len(nodes) < 2:
        return "TB"
    
    # Calculate spread in x and y
    xs = [n.x for n in nodes if n.x != 0]
    ys = [n.y for n in nodes if n.y != 0]
    
    if not xs or not ys:
        return "TB"
    
    x_spread = max(xs) - min(xs) if xs else 0
    y_spread = max(ys) - min(ys) if ys else 0
    
    # If wider than tall, use left-to-right
    if x_spread > y_spread * 1.5:
        return "LR"
    
    return "TB"


def format_node_mermaid(node: Node, node_id: str) -> str:
    """Format a node for Mermaid syntax with appropriate shape."""
    label = node.label
    
    # Shape syntax based on FlowForge mapping
    shape_formats = {
        'rectangle': f'{node_id}["{label}"]',
        'stadium': f'{node_id}(["{label}"])',  # Rounded/stadium
        'database': f'{node_id}[("{label}")]',  # Cylinder
        'diamond': f'{node_id}{{"{label}"}}',   # Decision
        'circle': f'{node_id}(("{label}"))',    # Circle/ellipse
        'parallelogram': f'{node_id}[/"{label}"/]',  # Parallelogram
        'hexagon': f'{node_id}{{{{"{label}"}}}}',    # Hexagon
    }
    
    return shape_formats.get(node.shape, shape_formats['rectangle'])


def format_edge_mermaid(edge: Edge, source_id: str, target_id: str) -> str:
    """
    Format an edge for Mermaid syntax with correct arrow direction and line style.
    
    Mermaid arrow combinations:
      Solid:   -->  (forward)  <-->  (bidirectional)  ---  (no arrow)  <--  (reverse)
      Dashed:  -.-> (forward)  <-.-> (bidirectional)  -.-  (no arrow)  <-.- (reverse)
      Thick:   ==>  (forward)  <==> (bidirectional)   ===  (no arrow)  <==  (reverse)
    """
    has_start = edge.arrow_start
    has_end = edge.arrow_end

    if edge.style == 'dashed' or edge.style == 'dotted':
        if has_start and has_end:
            arrow = '<-.->'
        elif has_start and not has_end:
            arrow = '<-.-'
        elif has_end:
            arrow = '-.->'
        else:
            arrow = '-.-'
    elif edge.style == 'thick':
        if has_start and has_end:
            arrow = '<==>'
        elif has_start and not has_end:
            arrow = '<=='
        elif has_end:
            arrow = '==>'
        else:
            arrow = '==='
    else:  # solid (default)
        if has_start and has_end:
            arrow = '<-->'
        elif has_start and not has_end:
            arrow = '<--'
        elif has_end:
            arrow = '-->'
        else:
            arrow = '---'
    
    if edge.label:
        return f'    {source_id} {arrow}|"{edge.label}"| {target_id}'
    else:
        return f'    {source_id} {arrow} {target_id}'


def generate_mermaid(nodes: List[Node], edges: List[Edge], groups: Dict[str, Group]) -> str:
    """Generate Mermaid flowchart from extracted elements."""
    if not nodes and not edges:
        return "```mermaid\nflowchart TB\n    A[No diagram data extracted]\n```"
    
    # Detect direction
    direction = detect_direction(nodes)
    
    lines = ["```mermaid", f"flowchart {direction}"]
    
    # Create ID mapping
    used_ids: Set[str] = set()
    id_map: Dict[str, str] = {}
    
    for node in nodes:
        safe_id = make_safe_id(node.label, used_ids, node.id)
        id_map[node.id] = safe_id
    
    # Track nodes in groups
    grouped_node_ids: Set[str] = set()
    for group in groups.values():
        grouped_node_ids.update(group.children)
    
    # Output subgraphs for groups with children
    for group_id, group in groups.items():
        group_nodes = [n for n in nodes if n.id in group.children]
        if group_nodes:
            safe_label = re.sub(r'[^a-zA-Z0-9_]', '_', group.label)
            lines.append(f'    subgraph {safe_label}["{group.label}"]')
            for node in group_nodes:
                node_id = id_map.get(node.id, node.id)
                lines.append(f'        {format_node_mermaid(node, node_id)}')
            lines.append('    end')
    
    # Output ungrouped nodes
    for node in nodes:
        if node.id not in grouped_node_ids:
            node_id = id_map.get(node.id, node.id)
            lines.append(f'    {format_node_mermaid(node, node_id)}')
    
    # Output edges
    for edge in edges:
        source_id = id_map.get(edge.source)
        target_id = id_map.get(edge.target)
        
        # Skip edges with missing endpoints
        if not source_id or not target_id:
            continue
        
        lines.append(format_edge_mermaid(edge, source_id, target_id))
    
    # Output style directives for colored nodes
    # This preserves the original diagram's color semantics
    for node in nodes:
        node_id = id_map.get(node.id)
        if not node_id:
            continue
        
        style_parts = []
        if node.fill_color:
            style_parts.append(f"fill:{node.fill_color}")
        if node.stroke_color:
            style_parts.append(f"stroke:{node.stroke_color}")
        if node.font_color:
            style_parts.append(f"color:{node.font_color}")
        
        if style_parts:
            lines.append(f'    style {node_id} {",".join(style_parts)}')
    
    lines.append("```")
    return '\n'.join(lines)


def convert_drawio_to_mermaid(input_path: Path, page_index: int = 0) -> str:
    """
    Main conversion function.
    
    Args:
        input_path: Path to .drawio file
        page_index: Which diagram page to convert (0-based)
    
    Returns:
        Mermaid diagram code
    """
    with open(input_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    # Extract diagram pages
    pages = extract_diagram_pages(content)
    
    if not pages:
        print(f"  ⚠ No diagram pages found in file", file=sys.stderr)
        return "```mermaid\nflowchart TB\n    A[Could not parse diagram]\n```"
    
    if page_index >= len(pages):
        print(f"  ⚠ Page index {page_index} out of range (found {len(pages)} pages)", file=sys.stderr)
        page_index = 0
    
    # Parse selected page
    xml_content = pages[page_index]
    root = parse_diagram_xml(xml_content)
    
    if root is None:
        print(f"  ⚠ Could not parse XML structure", file=sys.stderr)
        return "```mermaid\nflowchart TB\n    A[Could not parse diagram]\n```"
    
    # Extract elements
    nodes, edges, groups = extract_graph_elements(root)
    
    print(f"  📊 Extracted: {len(nodes)} nodes, {len(edges)} edges, {len(groups)} groups", file=sys.stderr)
    
    if len(pages) > 1:
        print(f"  📄 Multi-page file: converted page {page_index + 1} of {len(pages)}", file=sys.stderr)
    
    return generate_mermaid(nodes, edges, groups)


def main():
    parser = argparse.ArgumentParser(
        description="Convert Draw.io diagrams to Mermaid",
        epilog="Based on FlowForge research (https://github.com/genkinsforge/FlowForge)"
    )
    parser.add_argument("--input", "-i", required=True, help="Input .drawio file")
    parser.add_argument("--output", "-o", help="Output file (optional)")
    parser.add_argument("--page", "-p", type=int, default=0, help="Page index for multi-page files (0-based)")
    args = parser.parse_args()
    
    input_path = Path(args.input)
    
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)
    
    mermaid = convert_drawio_to_mermaid(input_path, args.page)
    
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(mermaid)
        print(f"  ✅ Output written to {output_path}", file=sys.stderr)
    
    print(mermaid)


if __name__ == "__main__":
    main()
