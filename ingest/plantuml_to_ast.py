#!/usr/bin/env python3
"""
PlantUML to AST Converter

Parses PlantUML diagram blocks into canonical DiagramAST with:
- Sequence diagram support (participants, messages)
- Component/deployment diagram support (packages, components, connections)
- Class diagram support (classes, interfaces, inheritance, composition)
- State diagram support
- Color preservation (inline #hex, skinparam, named colors)
- Line style preservation (solid, dashed, dotted, thick, bidirectional)
- Semantic enrichment (roles, protocols, zones)
"""

import argparse
import re
import sys
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

from ingest.diagram_ast import (
    DiagramAST, DiagramNode, DiagramEdge, DiagramGroup,
    save_ast, enrich_ast,
)


# ─── Named color mapping ───────────────────────────────────────────

NAMED_COLORS = {
    'red': '#FF0000', 'blue': '#0000FF', 'green': '#008000',
    'orange': '#FFA500', 'yellow': '#FFFF00', 'purple': '#800080',
    'pink': '#FFC0CB', 'black': '#000000', 'white': '#FFFFFF',
    'gray': '#808080', 'grey': '#808080',
    'lightblue': '#ADD8E6', 'darkblue': '#00008B',
    'lightgreen': '#90EE90', 'darkgreen': '#006400',
    'lightgray': '#D3D3D3', 'lightgrey': '#D3D3D3',
    'darkgray': '#A9A9A9', 'darkgrey': '#A9A9A9',
    'cyan': '#00FFFF', 'magenta': '#FF00FF',
    'brown': '#A52A2A', 'navy': '#000080',
    'teal': '#008080', 'maroon': '#800000',
    'olive': '#808000', 'aqua': '#00FFFF',
    'coral': '#FF7F50', 'salmon': '#FA8072',
    'gold': '#FFD700', 'silver': '#C0C0C0',
    'skyblue': '#87CEEB', 'tomato': '#FF6347',
    'wheat': '#F5DEB3', 'beige': '#F5F5DC',
    'ivory': '#FFFFF0', 'linen': '#FAF0E6',
    'crimson': '#DC143C', 'indigo': '#4B0082',
}


def resolve_color(color_str: str) -> Optional[str]:
    """Resolve a PlantUML color to hex. Handles #hex, #NamedColor, and bare names."""
    if not color_str:
        return None
    color_str = color_str.strip().lstrip('#')
    if re.match(r'^[0-9a-fA-F]{3,8}$', color_str):
        return f'#{color_str}'
    return NAMED_COLORS.get(color_str.lower())


# ─── Data structures ───────────────────────────────────────────────

@dataclass
class PumlNode:
    id: str
    label: str
    shape: str = "rectangle"
    color: Optional[str] = None
    parent_group: Optional[str] = None


@dataclass
class PumlEdge:
    src: str
    dst: str
    label: str = ""
    line_style: str = "solid"
    arrow_end: bool = True
    arrow_start: bool = False


@dataclass
class PumlGroup:
    id: str
    label: str
    children: List[str] = field(default_factory=list)


@dataclass
class PumlClass:
    name: str
    stereotype: str = ""
    members: List[str] = field(default_factory=list)
    methods: List[str] = field(default_factory=list)


@dataclass
class PumlRelation:
    src: str
    dst: str
    rel_type: str = "association"
    label: str = ""


# ─── Diagram type detection ───────────────────────────────────────

def detect_diagram_type(content: str) -> str:
    """Detect PlantUML diagram type from content."""
    text = content.lower()

    seq_patterns = [r'participant\s', r'actor\s+\w+\s', r'\w+\s*-+>+\s*\w+\s*:']
    if any(re.search(p, content, re.IGNORECASE) for p in seq_patterns):
        if 'class ' not in text and 'package ' not in text:
            return 'sequence'

    if re.search(r'\bclass\s+\w+', content, re.IGNORECASE) or re.search(r'\binterface\s+\w+', content, re.IGNORECASE):
        return 'class'

    if '[*] -->' in content or 'state ' in text:
        return 'state'

    if any(kw in text for kw in ['package ', 'component ', 'node ', 'folder ', 'cloud ', 'database ']):
        return 'component'

    if re.search(r':[\w\s]+;', content) or ('start' in text and 'stop' in text):
        return 'activity'

    return 'component'


# ─── Arrow parsing ────────────────────────────────────────────────

@dataclass
class ParsedArrow:
    style: str = "solid"
    has_start: bool = False
    has_end: bool = True
    color: Optional[str] = None
    lost: bool = False
    activate: int = 0


def parse_arrow(arrow: str) -> ParsedArrow:
    """Parse a PlantUML arrow string comprehensively."""
    arrow = arrow.strip()
    result = ParsedArrow()

    color_match = re.search(r'\[#([^\]]+)\]', arrow)
    if color_match:
        result.color = resolve_color(color_match.group(1))
        arrow = re.sub(r'\[#[^\]]+\]', '', arrow)

    if re.search(r'[>x]\+\+$', arrow):
        result.activate = 1
        arrow = arrow[:-2]
    elif re.search(r'[>x]--$', arrow):
        result.activate = -1
        arrow = arrow[:-2]

    if arrow.endswith('x') and re.search(r'[-.>=]x$', arrow):
        result.lost = True
        result.has_end = False
        arrow = arrow[:-1]

    if arrow.endswith('o') and re.search(r'[-.>=]o$', arrow):
        arrow = arrow[:-1]

    result.has_start = arrow.startswith('<')
    if not result.lost:
        result.has_end = arrow.endswith('>')

    core = arrow.lstrip('<').rstrip('>')

    if '==' in core:
        result.style = 'thick'
    elif '..' in core:
        result.style = 'dotted'
    elif len(core) >= 2 and re.match(r'^-+$', core):
        result.style = 'dashed'
    elif '-' in core:
        result.style = 'solid'
    else:
        result.style = 'solid'

    return result


# ─── Data parsers ─────────────────────────────────────────────────

def _parse_component_data(content: str) -> Tuple[Dict[str, PumlNode], List[PumlEdge], Dict[str, PumlGroup]]:
    """Parse component/deployment PlantUML into intermediate structures."""
    nodes: Dict[str, PumlNode] = {}
    edges: List[PumlEdge] = []
    groups: Dict[str, PumlGroup] = {}
    current_group: Optional[str] = None
    group_stack: List[Optional[str]] = []

    def safe_id(name: str) -> str:
        sid = re.sub(r'[^a-zA-Z0-9_]', '_', name).strip('_')[:25]
        if not sid or sid[0].isdigit():
            sid = f'n_{sid}'
        return sid

    for line in content.split('\n'):
        line = line.strip()
        if not line or line.startswith("'") or line.startswith('@'):
            continue

        m = re.match(r'(package|node|folder|cloud|rectangle|frame)\s+"?([^"{]*)"?\s*(?:as\s+(\w+))?\s*(?:#(\w+))?\s*\{', line, re.IGNORECASE)
        if m:
            kind, label, alias, color = m.group(1), m.group(2).strip(), m.group(3), m.group(4)
            gid = alias or safe_id(label)
            groups[gid] = PumlGroup(id=gid, label=label)
            group_stack.append(current_group)
            current_group = gid
            continue

        if line == '}':
            if group_stack:
                current_group = group_stack.pop()
            continue

        m = re.match(r'\[([^\]]+)\]\s*(?:as\s+(\w+))?\s*(?:#(\w+))?\s*$', line)
        if m:
            label, alias, color = m.group(1).strip(), m.group(2), m.group(3)
            nid = alias or safe_id(label)
            node = PumlNode(id=nid, label=label, shape='rectangle', parent_group=current_group)
            if color:
                node.color = resolve_color(color)
            nodes[nid] = node
            if current_group and current_group in groups:
                groups[current_group].children.append(nid)
            continue

        m = re.match(r'(?:component|database|cloud|actor|interface)\s+"?([^"]*?)"?\s*(?:as\s+(\w+))?\s*(?:#(\w+))?$', line, re.IGNORECASE)
        if m:
            kind_match = re.match(r'(\w+)', line, re.IGNORECASE)
            kind = kind_match.group(1).lower() if kind_match else 'rectangle'
            label, alias, color = m.group(1).strip(), m.group(2), m.group(3)
            nid = alias or safe_id(label)
            shape_map = {'database': 'database', 'actor': 'circle', 'interface': 'circle'}
            node = PumlNode(id=nid, label=label, shape=shape_map.get(kind, 'rectangle'), parent_group=current_group)
            if color:
                node.color = resolve_color(color)
            nodes[nid] = node
            if current_group and current_group in groups:
                groups[current_group].children.append(nid)
            continue

        m = re.match(r'(?:\[([^\]]+)\]|(\w+))\s*([<]?[-=.]+[>]?)\s*(?:\[([^\]]+)\]|(\w+))(?:\s*:\s*(.*))?', line)
        if m:
            src_name = m.group(1) or m.group(2)
            dst_name = m.group(4) or m.group(5)
            arrow_str = m.group(3)
            label = (m.group(6) or '').strip()
            if not src_name or not dst_name:
                continue
            src_id = safe_id(src_name)
            dst_id = safe_id(dst_name)
            if src_id not in nodes:
                nodes[src_id] = PumlNode(id=src_id, label=src_name)
            if dst_id not in nodes:
                nodes[dst_id] = PumlNode(id=dst_id, label=dst_name)
            parsed = parse_arrow(arrow_str)
            edges.append(PumlEdge(
                src=src_id, dst=dst_id, label=label,
                line_style=parsed.style, arrow_start=parsed.has_start, arrow_end=parsed.has_end
            ))
            continue

    return nodes, edges, groups


def _classify_class_relation(arrow: str) -> str:
    """Classify a PlantUML class relation arrow."""
    if '|>' in arrow or '<|' in arrow:
        if '..' in arrow:
            return 'implements'
        return 'extends'
    if '*' in arrow:
        return 'composition'
    if 'o' in arrow:
        return 'aggregation'
    if '..' in arrow:
        return 'dependency'
    return 'association'


def _parse_class_data(content: str) -> Tuple[Dict[str, PumlClass], List[PumlRelation]]:
    """Parse class-diagram PlantUML into intermediate structures."""
    classes: Dict[str, PumlClass] = {}
    relations: List[PumlRelation] = []
    current_class: Optional[str] = None

    for line in content.split('\n'):
        line = line.strip()
        if not line or line.startswith("'") or line.startswith('@'):
            continue

        m = re.match(r'(?:(abstract)\s+)?(?:class|interface|enum)\s+"?(\w+)"?\s*(?:<<(\w+)>>)?\s*\{', line, re.IGNORECASE)
        if m:
            abstract, name, stereo = m.group(1), m.group(2), m.group(3)
            kind = 'interface' if 'interface' in line.lower() else ('enum' if 'enum' in line.lower() else '')
            if abstract:
                kind = 'abstract'
            if stereo:
                kind = stereo.lower()
            classes[name] = PumlClass(name=name, stereotype=kind)
            current_class = name
            continue

        m = re.match(r'(?:(abstract)\s+)?(?:class|interface|enum)\s+"?(\w+)"?\s*(?:<<(\w+)>>)?$', line, re.IGNORECASE)
        if m:
            abstract, name, stereo = m.group(1), m.group(2), m.group(3)
            kind = 'interface' if 'interface' in line.lower() else ('enum' if 'enum' in line.lower() else '')
            if abstract:
                kind = 'abstract'
            if stereo:
                kind = stereo.lower()
            classes[name] = PumlClass(name=name, stereotype=kind)
            continue

        if line == '}':
            current_class = None
            continue

        if current_class and current_class in classes:
            if '(' in line and ')' in line:
                classes[current_class].methods.append(line)
            elif line not in ('{', '}', '--', '==', '..'):
                classes[current_class].members.append(line)
            continue

        m = re.match(r'(\w+)\s+([<>|.*o#x+\-]+)\s+(\w+)(?:\s*:\s*(.*))?', line)
        if m:
            src, arrow, dst, label = m.group(1), m.group(2), m.group(3), (m.group(4) or '').strip()
            rel = _classify_class_relation(arrow)
            relations.append(PumlRelation(src=src, dst=dst, rel_type=rel, label=label))
            if src not in classes:
                classes[src] = PumlClass(name=src)
            if dst not in classes:
                classes[dst] = PumlClass(name=dst)
            continue

    return classes, relations


def _parse_sequence_data(content: str) -> Tuple[Dict[str, str], List[dict]]:
    """Parse sequence-diagram PlantUML into participants and messages."""
    participants: Dict[str, str] = {}
    messages: List[dict] = []

    for line in content.split('\n'):
        line = line.strip()
        if not line or line.startswith("'") or line.startswith('@'):
            continue

        m = re.match(
            r'(?:participant|actor|entity|boundary|control|database|collections|queue)\s+'
            r'"([^"]+)"\s+as\s+(\w+)', line, re.IGNORECASE)
        if m:
            participants[m.group(2)] = m.group(1)
            continue

        m = re.match(
            r'(?:participant|actor|entity|boundary|control|database|collections|queue)\s+'
            r'"?([^"#]+?)"?\s*(?:#\w+)?\s*$', line, re.IGNORECASE)
        if m:
            name = m.group(1).strip()
            alias = re.sub(r'[^a-zA-Z0-9]', '', name)
            participants[alias] = name
            participants[name] = name
            continue

        m = re.match(
            r'^(\w+)\s+'
            r'(<?(?:-+|\.\.|==)(?:\[#[^\]]+\])?(?:-+|\.\.|==)?(?:[>])?(?:[>])?(?:[xo])?(?:\+\+|--)?)\s+'
            r'(\w+)(?:\s*:\s*(.*))?$', line)
        if m:
            src, arrow_str, dst, label = m.group(1), m.group(2), m.group(3), (m.group(4) or '').strip()
            for p in (src, dst):
                if p not in participants:
                    participants[p] = p
            parsed = parse_arrow(arrow_str)
            messages.append({
                'src': src, 'dst': dst, 'label': label,
                'style': parsed.style,
                'arrow_start': parsed.has_start, 'arrow_end': parsed.has_end,
            })

    return participants, messages


def _parse_state_data(content: str) -> Tuple[Dict[str, str], List[dict]]:
    """Parse state-diagram PlantUML into states and transitions."""
    states: Dict[str, str] = {}
    transitions: List[dict] = []

    for line in content.split('\n'):
        line = line.strip()
        if not line or line.startswith("'") or line.startswith('@'):
            continue

        m = re.match(r'state\s+"?([^"]+?)"?\s+as\s+(\w+)', line, re.IGNORECASE)
        if m:
            states[m.group(2)] = m.group(1)
            continue

        m = re.match(r'(\[?\*?\]?|\w+)\s*-+>\s*(\[?\*?\]?|\w+)(?:\s*:\s*(.*))?', line)
        if m:
            src, dst, label = m.group(1), m.group(2), (m.group(3) or '').strip()
            transitions.append({'src': src, 'dst': dst, 'label': label})
            if src not in states and src != '[*]':
                states[src] = src
            if dst not in states and dst != '[*]':
                states[dst] = dst

    return states, transitions


# ─── Data-to-AST mappers ──────────────────────────────────────────

def _component_data_to_ast(nodes: Dict[str, PumlNode], edges: List[PumlEdge],
                           groups: Dict[str, PumlGroup]) -> DiagramAST:
    ast_nodes = [
        DiagramNode(
            id=n.id, label=n.label, shape=n.shape,
            fill_color=n.color, parent_group=n.parent_group,
        )
        for n in nodes.values()
    ]
    ast_edges = [
        DiagramEdge(
            id=f"edge_{i+1}", source=e.src, target=e.dst,
            label=e.label, style=e.line_style,
            arrow_start=e.arrow_start, arrow_end=e.arrow_end,
        )
        for i, e in enumerate(edges)
    ]
    ast_groups = [
        DiagramGroup(id=g.id, label=g.label, children=list(g.children))
        for g in groups.values()
    ]
    return DiagramAST(
        nodes=ast_nodes, edges=ast_edges, groups=ast_groups,
        diagram_type='flowchart', direction='TB',
        metadata={'source_format': 'plantuml', 'plantuml_type': 'component'},
    )


def _class_data_to_ast(classes: Dict[str, PumlClass],
                       relations: List[PumlRelation]) -> DiagramAST:
    ast_nodes = [
        DiagramNode(
            id=c.name, label=c.name, shape='rectangle',
            metadata={
                'stereotype': c.stereotype,
                'members': list(c.members),
                'methods': list(c.methods),
            },
        )
        for c in classes.values()
    ]
    ast_edges = [
        DiagramEdge(
            id=f"rel_{i+1}", source=r.src, target=r.dst,
            label=r.label,
            metadata={'rel_type': r.rel_type},
        )
        for i, r in enumerate(relations)
    ]
    return DiagramAST(
        nodes=ast_nodes, edges=ast_edges, groups=[],
        diagram_type='class',
        metadata={'source_format': 'plantuml', 'plantuml_type': 'class'},
    )


def _sequence_data_to_ast(participants: Dict[str, str],
                          messages: List[dict]) -> DiagramAST:
    seen = set()
    ast_nodes: List[DiagramNode] = []
    for alias, label in participants.items():
        if alias in seen:
            continue
        seen.add(alias)
        ast_nodes.append(DiagramNode(
            id=alias, label=label, shape='rectangle',
            metadata={'role': 'participant'},
        ))
    ast_edges = [
        DiagramEdge(
            id=f"msg_{i+1}", source=msg['src'], target=msg['dst'],
            label=msg.get('label', ''), style=msg.get('style', 'solid'),
            arrow_start=msg.get('arrow_start', False),
            arrow_end=msg.get('arrow_end', True),
            sequence_order=i + 1,
        )
        for i, msg in enumerate(messages)
    ]
    return DiagramAST(
        nodes=ast_nodes, edges=ast_edges, groups=[],
        diagram_type='sequence',
        metadata={'source_format': 'plantuml', 'plantuml_type': 'sequence'},
    )


def _state_data_to_ast(states: Dict[str, str],
                       transitions: List[dict]) -> DiagramAST:
    ast_nodes = [
        DiagramNode(id=sid, label=label, shape='rectangle')
        for sid, label in states.items()
    ]
    ast_edges = [
        DiagramEdge(
            id=f"trans_{i+1}", source=t['src'], target=t['dst'],
            label=t.get('label', ''),
        )
        for i, t in enumerate(transitions)
    ]
    return DiagramAST(
        nodes=ast_nodes, edges=ast_edges, groups=[],
        diagram_type='state',
        metadata={'source_format': 'plantuml', 'plantuml_type': 'state'},
    )


# ─── Public API ───────────────────────────────────────────────────

def convert_plantuml_to_ast(puml_content: str) -> DiagramAST:
    """Parse a PlantUML block and return a semantically enriched DiagramAST."""
    dtype = detect_diagram_type(puml_content)

    if dtype in ('component', 'activity'):
        nodes, edges, groups = _parse_component_data(puml_content)
        ast = _component_data_to_ast(nodes, edges, groups)
    elif dtype == 'class':
        classes, relations = _parse_class_data(puml_content)
        ast = _class_data_to_ast(classes, relations)
    elif dtype == 'sequence':
        participants, messages = _parse_sequence_data(puml_content)
        ast = _sequence_data_to_ast(participants, messages)
    elif dtype == 'state':
        states, transitions = _parse_state_data(puml_content)
        ast = _state_data_to_ast(states, transitions)
    else:
        nodes, edges, groups = _parse_component_data(puml_content)
        ast = _component_data_to_ast(nodes, edges, groups)

    enrich_ast(ast)
    return ast


def extract_plantuml_blocks(text: str) -> List[str]:
    """Extract PlantUML blocks from text (both @startuml and fenced code blocks)."""
    blocks = []

    for m in re.finditer(r'@startuml\b.*?\n(.*?)@enduml', text, re.DOTALL | re.IGNORECASE):
        blocks.append(m.group(1))

    for m in re.finditer(r'```(?:plantuml|puml)\s*\n(.*?)```', text, re.DOTALL | re.IGNORECASE):
        blocks.append(m.group(1))

    return blocks


# ─── CLI ──────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Convert PlantUML diagrams to AST JSON")
    parser.add_argument("--input", "-i", help="Input .puml file")
    parser.add_argument("--output", "-o", required=True, help="Output .ast.json path")
    parser.add_argument("--stdin", action="store_true", help="Read from stdin")
    args = parser.parse_args()

    if args.stdin:
        content = sys.stdin.read()
    elif args.input:
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"Error: Input file not found: {input_path}", file=sys.stderr)
            sys.exit(1)
        content = input_path.read_text(encoding='utf-8', errors='ignore')
    else:
        parser.error("Either --input or --stdin is required")
        return

    inner = re.sub(r'@startuml\b[^\n]*\n?', '', content, flags=re.IGNORECASE)
    inner = re.sub(r'@enduml\b[^\n]*', '', inner, flags=re.IGNORECASE)
    inner = inner.strip()

    if not inner:
        print("Error: No PlantUML content found", file=sys.stderr)
        sys.exit(1)

    ast = convert_plantuml_to_ast(inner)
    save_ast(ast, args.output)
    print(f"  AST written to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
