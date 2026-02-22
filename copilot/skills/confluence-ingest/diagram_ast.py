#!/usr/bin/env python3
"""
Diagram AST — Canonical Intermediate Representation for Architecture Diagrams

Shared schema used by all diagram converters (Draw.io, SVG, PlantUML, image CV).
Every diagram source produces a DiagramAST, which is then serialized to .ast.json
and/or converted to Mermaid via generate_mermaid().

The AST is the primary artifact — Mermaid is a derived rendering.
"""

import json
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


MERMAID_RESERVED = {
    'end', 'graph', 'flowchart', 'subgraph', 'direction',
    'click', 'style', 'classDef', 'class',
}

AST_SCHEMA_VERSION = "1.0.0"


# ──────────────────────────────────────────────────────────────────
# Dataclasses
# ──────────────────────────────────────────────────────────────────

@dataclass
class DiagramNode:
    id: str
    label: str
    shape: str = "rectangle"
    x: float = 0
    y: float = 0
    width: float = 0
    height: float = 0
    fill_color: Optional[str] = None
    stroke_color: Optional[str] = None
    font_color: Optional[str] = None
    parent_group: Optional[str] = None
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DiagramEdge:
    id: str
    source: str
    target: str
    label: str = ""
    style: str = "solid"
    arrow_start: bool = False
    arrow_end: bool = True
    color: Optional[str] = None
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DiagramGroup:
    id: str
    label: str
    children: List[str] = field(default_factory=list)
    parent_group: Optional[str] = None
    style: str = "solid"
    fill_color: Optional[str] = None


@dataclass
class DiagramAST:
    nodes: List[DiagramNode] = field(default_factory=list)
    edges: List[DiagramEdge] = field(default_factory=list)
    groups: List[DiagramGroup] = field(default_factory=list)
    diagram_type: str = "flowchart"
    direction: str = "TB"
    metadata: Dict[str, Any] = field(default_factory=dict)


# ──────────────────────────────────────────────────────────────────
# JSON Serialization
# ──────────────────────────────────────────────────────────────────

def to_json(ast: DiagramAST) -> dict:
    """Serialize a DiagramAST to a JSON-compatible dict."""
    data = asdict(ast)
    data['schema_version'] = AST_SCHEMA_VERSION
    return data


def from_json(data: dict) -> DiagramAST:
    """Deserialize a dict (from JSON) into a DiagramAST."""
    nodes = [DiagramNode(**n) for n in data.get('nodes', [])]
    edges = [DiagramEdge(**e) for e in data.get('edges', [])]
    groups = [DiagramGroup(**g) for g in data.get('groups', [])]
    return DiagramAST(
        nodes=nodes,
        edges=edges,
        groups=groups,
        diagram_type=data.get('diagram_type', 'flowchart'),
        direction=data.get('direction', 'TB'),
        metadata=data.get('metadata', {}),
    )


def save_ast(ast: DiagramAST, path: str) -> None:
    """Write a DiagramAST to a .ast.json file."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(to_json(ast), f, indent=2, default=str)


def load_ast(path: str) -> DiagramAST:
    """Read a .ast.json file and return a DiagramAST."""
    with open(path, 'r', encoding='utf-8') as f:
        return from_json(json.load(f))


# ──────────────────────────────────────────────────────────────────
# Mermaid helpers (extracted from drawio_to_mermaid.py)
# ──────────────────────────────────────────────────────────────────

def make_safe_id(label: str, used_ids: Set[str], cell_id: str = "") -> str:
    """Generate a unique, Mermaid-safe node ID from a label."""
    if not label:
        suffix = cell_id[-6:] if len(cell_id) > 6 else cell_id
        base_id = f"node_{suffix}" if suffix else "node_0"
    else:
        base_id = re.sub(r'[^a-zA-Z0-9]', '_', label)
        base_id = re.sub(r'_+', '_', base_id).strip('_')[:20]
        if not base_id or base_id[0].isdigit():
            base_id = f"n_{base_id}"

    if base_id.lower() in MERMAID_RESERVED:
        base_id = f"{base_id}_node"

    final_id = base_id
    counter = 1
    while final_id in used_ids:
        final_id = f"{base_id}_{counter}"
        counter += 1

    used_ids.add(final_id)
    return final_id


def detect_direction(nodes: List[DiagramNode]) -> str:
    """Infer flow direction (TB or LR) from node positions."""
    if len(nodes) < 2:
        return "TB"
    xs = [n.x for n in nodes if n.x != 0]
    ys = [n.y for n in nodes if n.y != 0]
    if not xs or not ys:
        return "TB"
    x_spread = max(xs) - min(xs)
    y_spread = max(ys) - min(ys)
    return "LR" if x_spread > y_spread * 1.5 else "TB"


def _format_node(label: str, node_id: str, shape: str) -> str:
    """Return Mermaid node declaration for a given shape."""
    shape_formats = {
        'rectangle':     f'{node_id}["{label}"]',
        'stadium':       f'{node_id}(["{label}"])',
        'database':      f'{node_id}[("{label}")]',
        'diamond':       f'{node_id}{{"{label}"}}',
        'circle':        f'{node_id}(("{label}"))',
        'parallelogram': f'{node_id}[/"{label}"/]',
        'hexagon':       f'{node_id}{{{{"{label}"}}}}',
    }
    return shape_formats.get(shape, shape_formats['rectangle'])


def _format_edge(source_id: str, target_id: str, edge: DiagramEdge) -> str:
    """Return Mermaid edge declaration with correct arrow style."""
    has_start = edge.arrow_start
    has_end = edge.arrow_end

    if edge.style in ('dashed', 'dotted'):
        if has_start and has_end:    arrow = '<-.->'
        elif has_start:              arrow = '<-.-'
        elif has_end:                arrow = '-.->'
        else:                        arrow = '-.-'
    elif edge.style == 'thick':
        if has_start and has_end:    arrow = '<==>'
        elif has_start:              arrow = '<=='
        elif has_end:                arrow = '==>'
        else:                        arrow = '==='
    else:
        if has_start and has_end:    arrow = '<-->'
        elif has_start:              arrow = '<--'
        elif has_end:                arrow = '-->'
        else:                        arrow = '---'

    if edge.label:
        return f'    {source_id} {arrow}|"{edge.label}"| {target_id}'
    return f'    {source_id} {arrow} {target_id}'


# ──────────────────────────────────────────────────────────────────
# Mermaid Generation — flowchart
# ──────────────────────────────────────────────────────────────────

def _generate_flowchart(ast: DiagramAST) -> str:
    """Generate a Mermaid flowchart from a DiagramAST."""
    if not ast.nodes and not ast.edges:
        return "```mermaid\nflowchart TB\n    A[No diagram data extracted]\n```"

    direction = ast.direction if ast.direction != "TB" else detect_direction(ast.nodes)
    lines: List[str] = ["```mermaid", f"flowchart {direction}"]

    used_ids: Set[str] = set()
    id_map: Dict[str, str] = {}
    for node in ast.nodes:
        safe_id = make_safe_id(node.label, used_ids, node.id)
        id_map[node.id] = safe_id

    group_map: Dict[str, DiagramGroup] = {g.id: g for g in ast.groups}
    grouped_node_ids: Set[str] = set()
    for g in ast.groups:
        grouped_node_ids.update(g.children)

    for g in ast.groups:
        child_nodes = [n for n in ast.nodes if n.id in g.children]
        if child_nodes:
            safe_label = re.sub(r'[^a-zA-Z0-9_]', '_', g.label)
            lines.append(f'    subgraph {safe_label}["{g.label}"]')
            for node in child_nodes:
                nid = id_map.get(node.id, node.id)
                lines.append(f'        {_format_node(node.label, nid, node.shape)}')
            lines.append('    end')

    for node in ast.nodes:
        if node.id not in grouped_node_ids:
            nid = id_map.get(node.id, node.id)
            lines.append(f'    {_format_node(node.label, nid, node.shape)}')

    for edge in ast.edges:
        src = id_map.get(edge.source)
        tgt = id_map.get(edge.target)
        if src and tgt:
            lines.append(_format_edge(src, tgt, edge))

    for node in ast.nodes:
        nid = id_map.get(node.id)
        if not nid:
            continue
        parts = []
        if node.fill_color:
            parts.append(f"fill:{node.fill_color}")
        if node.stroke_color:
            parts.append(f"stroke:{node.stroke_color}")
        if node.font_color:
            parts.append(f"color:{node.font_color}")
        if parts:
            lines.append(f'    style {nid} {",".join(parts)}')

    for g in ast.groups:
        safe_label = re.sub(r'[^a-zA-Z0-9_]', '_', g.label)
        parts = []
        if g.fill_color:
            parts.append(f"fill:{g.fill_color}")
            parts.append(f"fill-opacity:0.15")
        if g.style == 'dashed':
            parts.append("stroke-dasharray:5 5")
        if parts:
            lines.append(f'    style {safe_label} {",".join(parts)}')

    edge_idx = 0
    for edge in ast.edges:
        src = id_map.get(edge.source)
        tgt = id_map.get(edge.target)
        if src and tgt:
            parts = []
            if edge.color:
                parts.append(f"stroke:{edge.color}")
            if edge.style == 'dashed':
                parts.append("stroke-dasharray:5 5")
            if parts:
                lines.append(f'    linkStyle {edge_idx} {",".join(parts)}')
            edge_idx += 1

    lines.append("```")
    return '\n'.join(lines)


# ──────────────────────────────────────────────────────────────────
# Mermaid Generation — sequence diagram
# ──────────────────────────────────────────────────────────────────

def _generate_sequence(ast: DiagramAST) -> str:
    """Generate a Mermaid sequence diagram from a DiagramAST."""
    lines: List[str] = ["```mermaid", "sequenceDiagram"]

    for node in ast.nodes:
        role = node.metadata.get('role', 'participant')
        if role == 'actor':
            lines.append(f'    actor {node.id} as {node.label}')
        else:
            lines.append(f'    participant {node.id} as {node.label}')

    for edge in ast.edges:
        if edge.style in ('dashed', 'dotted'):
            arrow = '-->>'
        else:
            arrow = '->>'
        label = edge.label or ""
        lines.append(f'    {edge.source}{arrow}{edge.target}: {label}')

    lines.append("```")
    return '\n'.join(lines)


# ──────────────────────────────────────────────────────────────────
# Mermaid Generation — class diagram
# ──────────────────────────────────────────────────────────────────

def _generate_class(ast: DiagramAST) -> str:
    """Generate a Mermaid class diagram from a DiagramAST."""
    lines: List[str] = ["```mermaid", "classDiagram"]

    for node in ast.nodes:
        stereotype = node.metadata.get('stereotype', '')
        if stereotype:
            lines.append(f'    class {node.id} {{')
            lines.append(f'        <<{stereotype}>>')
        else:
            lines.append(f'    class {node.id} {{')
        for member in node.metadata.get('members', []):
            lines.append(f'        {member}')
        for method in node.metadata.get('methods', []):
            lines.append(f'        {method}')
        lines.append('    }')

    rel_map = {
        'extends': '<|--',
        'implements': '<|..',
        'composition': '*--',
        'aggregation': 'o--',
        'dependency': '<..',
        'association': '--',
    }
    for edge in ast.edges:
        rel_type = edge.metadata.get('rel_type', 'association')
        arrow = rel_map.get(rel_type, '--')
        label_part = f' : {edge.label}' if edge.label else ''
        lines.append(f'    {edge.source} {arrow} {edge.target}{label_part}')

    lines.append("```")
    return '\n'.join(lines)


# ──────────────────────────────────────────────────────────────────
# Mermaid Generation — state diagram
# ──────────────────────────────────────────────────────────────────

def _generate_state(ast: DiagramAST) -> str:
    """Generate a Mermaid state diagram from a DiagramAST."""
    lines: List[str] = ["```mermaid", "stateDiagram-v2"]

    for node in ast.nodes:
        if node.label and node.label not in ('[*]',):
            lines.append(f'    {node.id} : {node.label}')

    for edge in ast.edges:
        label_part = f' : {edge.label}' if edge.label else ''
        lines.append(f'    {edge.source} --> {edge.target}{label_part}')

    lines.append("```")
    return '\n'.join(lines)


# ──────────────────────────────────────────────────────────────────
# Mermaid Generation — ER diagram
# ──────────────────────────────────────────────────────────────────

def _generate_er(ast: DiagramAST) -> str:
    """Generate a Mermaid ER diagram from a DiagramAST."""
    lines: List[str] = ["```mermaid", "erDiagram"]

    for edge in ast.edges:
        label_part = f' : "{edge.label}"' if edge.label else ' : ""'
        lines.append(f'    {edge.source} ||--o{{ {edge.target}{label_part}')

    lines.append("```")
    return '\n'.join(lines)


# ──────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────

_GENERATORS = {
    'flowchart': _generate_flowchart,
    'sequence':  _generate_sequence,
    'class':     _generate_class,
    'state':     _generate_state,
    'er':        _generate_er,
}


def generate_mermaid(ast: DiagramAST) -> str:
    """Convert a DiagramAST to fenced Mermaid text.

    Dispatches to the appropriate generator based on ``ast.diagram_type``.
    Falls back to flowchart for unknown types.
    """
    gen = _GENERATORS.get(ast.diagram_type, _generate_flowchart)
    return gen(ast)


# ──────────────────────────────────────────────────────────────────
# CLI (for quick inspection)
# ──────────────────────────────────────────────────────────────────

def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description='Diagram AST utilities')
    sub = parser.add_subparsers(dest='command')

    show = sub.add_parser('show', help='Pretty-print an .ast.json file')
    show.add_argument('file', help='Path to .ast.json')

    mermaid_cmd = sub.add_parser('mermaid', help='Generate Mermaid from .ast.json')
    mermaid_cmd.add_argument('file', help='Path to .ast.json')

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 0

    ast = load_ast(args.file)
    if args.command == 'show':
        print(json.dumps(to_json(ast), indent=2))
    elif args.command == 'mermaid':
        print(generate_mermaid(ast))
    return 0


if __name__ == '__main__':
    sys.exit(main())
