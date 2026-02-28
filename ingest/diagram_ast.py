#!/usr/bin/env python3
"""
Diagram AST — Canonical Intermediate Representation for Architecture Diagrams

Shared schema used by all diagram converters (Draw.io, SVG, PlantUML).
Every diagram source produces a DiagramAST, which is serialized to .ast.json
and rendered as markdown tables for embedding in page.md.

The AST is the primary artifact — markdown tables are a derived human-readable view.
"""

import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

AST_SCHEMA_VERSION = "3.0.0"


# ──────────────────────────────────────────────────────────────────
# Shared human-readable ID generator
# ──────────────────────────────────────────────────────────────────

def make_readable_id(label: str, used_ids: Set[str]) -> str:
    """Generate a human-readable ID from a label, ensuring uniqueness.

    Examples: "API Gateway" -> "api_gateway", "PostgreSQL DB" -> "postgresql_db"
    """
    clean = re.sub(r'[^a-zA-Z0-9]', '_', label.lower())
    clean = re.sub(r'_+', '_', clean).strip('_')
    if not clean or clean[0].isdigit():
        clean = 'n_' + clean
    clean = clean[:30]
    uid = clean
    counter = 2
    while uid in used_ids:
        uid = f"{clean}_{counter}"
        counter += 1
    used_ids.add(uid)
    return uid


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
    role: str = ""
    secondary_role: str = ""
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
    protocol: str = ""
    protocols: List[str] = field(default_factory=list)
    sequence_order: int = 0
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
    zone_type: str = ""
    confidence: float = 1.0


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
    node_fields = {f.name for f in DiagramNode.__dataclass_fields__.values()}
    edge_fields = {f.name for f in DiagramEdge.__dataclass_fields__.values()}
    group_fields = {f.name for f in DiagramGroup.__dataclass_fields__.values()}

    nodes = [DiagramNode(**{k: v for k, v in n.items() if k in node_fields}) for n in data.get('nodes', [])]
    edges = [DiagramEdge(**{k: v for k, v in e.items() if k in edge_fields}) for e in data.get('edges', [])]
    groups = [DiagramGroup(**{k: v for k, v in g.items() if k in group_fields}) for g in data.get('groups', [])]
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
# Layout helpers
# ──────────────────────────────────────────────────────────────────

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


# ──────────────────────────────────────────────────────────────────
# Semantic Inference — deterministic, keyword-based
# ──────────────────────────────────────────────────────────────────

_ROLE_PATTERNS = [
    (r'(?i)\b(postgres|mysql|mongo|dynamo|cassandra|redis\s*db|database|data\s*store|aurora|rds)\b', 'datastore'),
    (r'(?i)\b(api\s*gate\s*way|gateway|apigw|api\s*gw|kong|zuul|envoy\s*proxy)\b', 'gateway'),
    (r'(?i)\b(queue|mq|kafka|rabbit\s*mq|sqs|kinesis|pub\s*sub|event\s*bus|topic|nats)\b', 'queue'),
    (r'(?i)\b(cache|redis|memcache[d]?|edge\s*cache|varnish)\b', 'cache'),
    (r'(?i)\b(load\s*balanc|lb|nginx|haproxy|alb|nlb|elb|traefik)\b', 'load_balancer'),
    (r'(?i)\b(user|actor|client|browser|mobile|end.?user|customer)\b', 'actor'),
    (r'(?i)\b(external|third.?party|vendor|partner|saas|3rd)\b', 'external'),
    (r'(?i)\b(interface|api|endpoint|rest\s*api|graphql)\b', 'interface'),
    (r'(?i)\b(auth|identity|oauth|oidc|idp|keycloak|okta|auth0|cognito)\b', 'auth_service'),
    (r'(?i)\b(notification|email|sms|push|sendgrid|ses|twilio)\b', 'notification'),
    (r'(?i)\b(cdn|cloudfront|akamai|fastly|cloud\s*cdn)\b', 'cdn'),
    (r'(?i)\b(waf|firewall|fw|network\s*acl|security\s*group)\b', 'firewall'),
    (r'(?i)\b(monitoring|prometheus|grafana|datadog|new\s*relic|observ|apm)\b', 'monitoring'),
    (r'(?i)\b(ci\s*cd|cicd|jenkins|github\s*actions|pipeline|gitlab\s*ci|circle\s*ci|argo)\b', 'ci_cd'),
    (r'(?i)\b(object\s*stor|s3|blob|gcs|minio|storage\s*bucket)\b', 'object_store'),
]

_PROTOCOL_PATTERNS = [
    (r'(?i)\bmtls\b', 'mTLS'),
    (r'(?i)\bhttps\b', 'HTTPS'),
    (r'(?i)\bhttp\b', 'HTTP'),
    (r'(?i)\bgrpc\b', 'gRPC'),
    (r'(?i)\bamqp\b', 'AMQP'),
    (r'(?i)\bmqtt\b', 'MQTT'),
    (r'(?i)\brest\b', 'REST'),
    (r'(?i)\bgraphql\b', 'GraphQL'),
    (r'(?i)\bwebsocket[s]?\b', 'WebSocket'),
    (r'(?i)\btls\b', 'TLS'),
    (r'(?i)\btcp\b', 'TCP'),
    (r'(?i)\bjdbc\b', 'JDBC'),
    (r'(?i)\bsoap\b', 'SOAP'),
    (r'(?i)\budp\b', 'UDP'),
    (r'(?i)\bkafka\b', 'Kafka'),
]

_ZONE_PATTERNS = [
    (r'(?i)\b(internal|private|intranet)\b', 'internal'),
    (r'(?i)\b(external|public|internet)\b', 'external'),
    (r'(?i)\b(dmz|demilitarized)\b', 'dmz'),
    (r'(?i)\b(aws|azure|gcp|cloud)\b', 'cloud'),
    (r'(?i)\b(trust.?boundar|security.?zone|perimeter)\b', 'trust_boundary'),
]


def infer_node_role(label: str, shape: str) -> str:
    """Deterministically infer a node's primary architectural role from its label and shape."""
    if shape == "database":
        return "datastore"
    if shape == "diamond":
        return "decision"
    if shape == "circle" and re.search(r'(?i)\b(actor|user)\b', label):
        return "actor"

    for pattern, role in _ROLE_PATTERNS:
        if re.search(pattern, label):
            return role

    return "service"


def infer_secondary_role(label: str, primary_role: str) -> str:
    """Return a secondary role if the label matches a second pattern beyond the primary."""
    for pattern, role in _ROLE_PATTERNS:
        if role != primary_role and re.search(pattern, label):
            return role
    return ""


def infer_edge_protocol(label: str) -> str:
    """Extract the primary protocol from an edge label via regex matching."""
    if not label:
        return ""
    for pattern, protocol in _PROTOCOL_PATTERNS:
        if re.search(pattern, label):
            return protocol
    return ""


def infer_edge_protocols(label: str) -> List[str]:
    """Extract ALL matching protocols from an edge label."""
    if not label:
        return []
    found: List[str] = []
    for pattern, protocol in _PROTOCOL_PATTERNS:
        if re.search(pattern, label):
            found.append(protocol)
    return found


def infer_zone_type(label: str) -> str:
    """Infer a group's zone type from its label."""
    if not label:
        return ""
    for pattern, zone in _ZONE_PATTERNS:
        if re.search(pattern, label):
            return zone
    return ""


def infer_color_legend(nodes: List[DiagramNode], groups: List[DiagramGroup]) -> Dict[str, str]:
    """Build a color-to-meaning mapping by grouping nodes by fill color and finding common roles."""
    color_roles: Dict[str, Dict[str, int]] = {}
    for node in nodes:
        if node.fill_color and node.role:
            color = node.fill_color.lower()
            if color not in color_roles:
                color_roles[color] = {}
            color_roles[color][node.role] = color_roles[color].get(node.role, 0) + 1

    legend: Dict[str, str] = {}
    for color, roles in color_roles.items():
        dominant = max(roles, key=roles.get)
        legend[color] = dominant

    for group in groups:
        if group.fill_color and group.zone_type:
            legend[group.fill_color.lower()] = group.zone_type

    return legend


def enrich_ast(ast: DiagramAST) -> DiagramAST:
    """Populate semantic fields on an AST using deterministic inference.
    Mutates the AST in-place and returns it for chaining.
    """
    for node in ast.nodes:
        if not node.role:
            node.role = infer_node_role(node.label, node.shape)
        if not node.secondary_role:
            node.secondary_role = infer_secondary_role(node.label, node.role)

    for edge in ast.edges:
        if not edge.protocol:
            edge.protocol = infer_edge_protocol(edge.label)
        if not edge.protocols:
            edge.protocols = infer_edge_protocols(edge.label)

    for group in ast.groups:
        if not group.zone_type:
            group.zone_type = infer_zone_type(group.label)

    legend = infer_color_legend(ast.nodes, ast.groups)
    if legend:
        ast.metadata.setdefault('color_legend', {}).update(legend)

    return ast


# ──────────────────────────────────────────────────────────────────
# Markdown Table Generation
# ──────────────────────────────────────────────────────────────────

def _esc(text: str) -> str:
    """Escape pipe characters for markdown table cells."""
    if not text:
        return ""
    return str(text).replace("|", "\\|")


def ast_to_markdown_tables(ast: DiagramAST, source_name: str = "") -> str:
    """Convert a DiagramAST into human-readable markdown tables for page.md.

    Tables use labels instead of raw IDs for readability:
    - Node Group column shows the group label
    - Edge From/To columns show node labels
    - Group Contains column shows child node labels
    """
    lines: List[str] = []

    heading = f"#### Diagram: {source_name}" if source_name else "#### Diagram"
    lines.append(heading)
    lines.append("")
    lines.append(f"**Type:** {ast.diagram_type} | **Direction:** {ast.direction}")
    lines.append("")

    legend = ast.metadata.get('color_legend', {})
    if legend:
        lines.append("**Color Legend:**")
        for color, meaning in legend.items():
            lines.append(f"- {color} = {meaning}")
        lines.append("")

    id_to_label: Dict[str, str] = {}
    for n in ast.nodes:
        id_to_label[n.id] = n.label or n.id
    for g in ast.groups:
        id_to_label[g.id] = g.label or g.id

    def _resolve(node_id: str) -> str:
        return id_to_label.get(node_id, node_id)

    if ast.nodes:
        lines.append("##### Nodes")
        lines.append("")
        lines.append("| ID | Label | Role | Shape | Group |")
        lines.append("|----|-------|------|-------|-------|")
        for n in ast.nodes:
            group_label = _resolve(n.parent_group) if n.parent_group else ""
            lines.append(
                f"| {_esc(n.id)} | {_esc(n.label)} | {_esc(n.role)} "
                f"| {_esc(n.shape)} | {_esc(group_label)} |"
            )
        lines.append("")

    if ast.edges:
        lines.append("##### Edges")
        lines.append("")
        lines.append("| From | To | Label | Protocol | Style |")
        lines.append("|------|----|-------|----------|-------|")
        for e in ast.edges:
            arrow = "<->" if e.arrow_start and e.arrow_end else "->" if e.arrow_end else "<-" if e.arrow_start else "--"
            proto = ", ".join(e.protocols) if e.protocols else e.protocol
            lines.append(
                f"| {_esc(_resolve(e.source))} | {_esc(_resolve(e.target))} "
                f"| {_esc(e.label)} | {_esc(proto)} | {_esc(e.style)} {arrow} |"
            )
        lines.append("")

    if ast.groups:
        lines.append("##### Groups")
        lines.append("")
        lines.append("| Group | Zone | Contains |")
        lines.append("|-------|------|----------|")
        for g in ast.groups:
            children_labels = ", ".join(_resolve(c) for c in g.children)
            lines.append(
                f"| {_esc(g.label)} | {_esc(g.zone_type)} "
                f"| {_esc(children_labels)} |"
            )
        lines.append("")

    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────

def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description='Diagram AST utilities')
    sub = parser.add_subparsers(dest='command')

    show = sub.add_parser('show', help='Pretty-print an .ast.json file')
    show.add_argument('file', help='Path to .ast.json')

    tbl = sub.add_parser('table', help='Generate markdown tables from .ast.json')
    tbl.add_argument('file', help='Path to .ast.json')
    tbl.add_argument('--name', default='', help='Diagram source name for heading')

    enrich_cmd = sub.add_parser('enrich', help='Run semantic inference on an .ast.json and save')
    enrich_cmd.add_argument('file', help='Path to .ast.json')
    enrich_cmd.add_argument('--output', '-o', help='Output path (default: overwrite input)')

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 0

    ast = load_ast(args.file)

    if args.command == 'show':
        print(json.dumps(to_json(ast), indent=2))
    elif args.command == 'table':
        enrich_ast(ast)
        print(ast_to_markdown_tables(ast, source_name=args.name or Path(args.file).stem))
    elif args.command == 'enrich':
        enrich_ast(ast)
        out_path = args.output or args.file
        save_ast(ast, out_path)
        print(f"Enriched AST saved to {out_path}")

    return 0


if __name__ == '__main__':
    sys.exit(main())
