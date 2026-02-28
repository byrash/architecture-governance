#!/usr/bin/env python3
"""
Deterministic rules extractor for the ingestion pipeline.

Derives governance rules from DiagramAST data (nodes, edges, groups)
and produces per-page rules.md files plus a consolidated _all.rules.md.

Zero LLM — all rules are inferred from structural diagram properties.
"""

import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ingest.diagram_ast import DiagramAST, DiagramEdge, DiagramGroup, DiagramNode, load_ast

# Category prefixes for stable content-hashed rule IDs
_CATEGORY_PREFIX = {
    "protocol": "PROTO",
    "zone": "ZONE",
    "role": "ROLE",
    "connectivity": "CONN",
    "data_flow": "FLOW",
    "resilience": "RESIL",
    "fanout": "FANOUT",
    "cross": "CROSS",
}


def _make_rule_id(category: str, rule_name: str, ast_condition: str) -> str:
    """Generate a stable content-hashed rule ID: R-{PREFIX}-{hash6}."""
    prefix = _CATEGORY_PREFIX.get(category, "RULE")
    content = f"{rule_name}|{ast_condition}"
    h = hashlib.md5(content.encode()).hexdigest()[:6]
    return f"R-{prefix}-{h}"


def _is_new_rule_id(rid: str) -> bool:
    """Check if an ID uses the new R-PREFIX-hash format."""
    return bool(re.match(r'^R-[A-Z]+-[a-f0-9]{6}$', rid))


# ──────────────────────────────────────────────────────────────────
# Rule derivation from AST
# ──────────────────────────────────────────────────────────────────

def _derive_protocol_rules(edges: List[DiagramEdge]) -> List[Dict]:
    """Derive rules from edge protocols (e.g. all traffic uses HTTPS)."""
    rules: List[Dict] = []
    protocols = {e.protocol.upper() for e in edges if e.protocol}
    if not protocols:
        return rules

    secure = {"HTTPS", "MTLS", "TLS", "GRPC"}
    insecure = {"HTTP"}

    used_secure = protocols & secure
    used_insecure = protocols & insecure

    proto_edges = [e for e in edges if e.protocol]
    min_conf = min((e.confidence for e in proto_edges), default=1.0)

    if used_secure and not used_insecure:
        ast_cond = f"edge.protocol IN ({', '.join(sorted(used_secure))})"
        rules.append({
            "rule": "Secure transport",
            "sev": "C", "req": "Y",
            "keywords": ", ".join(sorted(p.lower() for p in used_secure)),
            "condition": f"All communication uses secure protocols ({', '.join(sorted(used_secure))})",
            "ast_condition": ast_cond,
            "confidence": min_conf,
        })
    elif used_insecure:
        ast_cond = f"edge.protocol IN ({', '.join(sorted(used_insecure))})"
        rules.append({
            "rule": "Insecure transport present",
            "sev": "H", "req": "Y",
            "keywords": "http, insecure, transport",
            "condition": "Some edges use insecure HTTP — upgrade to HTTPS/TLS",
            "ast_condition": ast_cond,
            "confidence": min_conf,
        })

    for proto in sorted(protocols):
        if proto not in secure and proto not in insecure and proto:
            ast_cond = f"edge.protocol == {proto}"
            rules.append({
                "rule": f"{proto} protocol used",
                "sev": "M", "req": "N",
                "keywords": proto.lower(),
                "condition": f"Communication protocol {proto} is used between components",
                "ast_condition": ast_cond,
                "confidence": min_conf,
            })

    return rules


def _derive_zone_rules(groups: List[DiagramGroup], nodes: List[DiagramNode]) -> List[Dict]:
    """Derive rules from group zones."""
    rules: List[Dict] = []
    zones = {g.zone_type: g for g in groups if g.zone_type}
    if not zones:
        return rules

    zone_groups = [g for g in groups if g.zone_type]
    min_conf = min((g.confidence for g in zone_groups), default=1.0)

    zone_names = sorted(zones.keys())
    ast_cond = f"group.zone_type IN ({', '.join(zone_names)})"
    rules.append({
        "rule": "Zone boundaries defined",
        "sev": "H", "req": "Y",
        "keywords": ", ".join(zone_names),
        "condition": f"Architecture defines zone boundaries: {', '.join(zone_names)}",
        "ast_condition": ast_cond,
        "confidence": min_conf,
    })

    if "dmz" in zones:
        rules.append({
            "rule": "DMZ zone present",
            "sev": "C", "req": "Y",
            "keywords": "dmz, perimeter, network",
            "condition": "A DMZ zone separates external traffic from internal services",
            "ast_condition": "group.zone_type == dmz",
            "confidence": zones["dmz"].confidence,
        })

    if "external" in zones and "internal" in zones:
        conf = min(zones["external"].confidence, zones["internal"].confidence)
        rules.append({
            "rule": "External/internal separation",
            "sev": "C", "req": "Y",
            "keywords": "external, internal, isolation",
            "condition": "External and internal zones are explicitly separated",
            "ast_condition": "group.zone_type IN (external, internal)",
            "confidence": conf,
        })

    return rules


def _derive_role_rules(nodes: List[DiagramNode]) -> List[Dict]:
    """Derive rules from node roles."""
    rules: List[Dict] = []
    roles: Dict[str, List[DiagramNode]] = {}
    for n in nodes:
        if n.role:
            roles.setdefault(n.role, []).append(n)

    def _add(role_key, rule_name, sev, req, keywords, condition_tpl, ast_cond):
        if role_key in roles:
            ns = roles[role_key]
            labels = [n.label or n.id for n in ns[:3]]
            conf = min(n.confidence for n in ns)
            rules.append({
                "rule": rule_name, "sev": sev, "req": req,
                "keywords": keywords,
                "condition": condition_tpl.format(", ".join(labels)),
                "ast_condition": ast_cond,
                "confidence": conf,
            })

    _add("gateway", "API gateway present", "H", "Y", "gateway, api, routing",
         "Traffic routes through gateway ({})", "node.role == gateway")
    _add("load_balancer", "Load balancer present", "M", "N",
         "load balancer, availability, scaling",
         "Load balancer distributes traffic for availability ({})", "node.role == load_balancer")
    _add("datastore", "Data stores identified", "H", "Y",
         "database, datastore, persistence",
         "Data stores explicitly shown ({})", "node.role == datastore")
    _add("cache", "Caching layer present", "L", "N",
         "cache, performance, latency",
         "Caching layer exists for performance ({})", "node.role == cache")
    _add("queue", "Async messaging present", "M", "N",
         "queue, async, messaging, decoupling",
         "Asynchronous messaging via queues for decoupling ({})", "node.role == queue")
    _add("external", "External dependencies documented", "H", "Y",
         "external, dependency, third-party",
         "External dependencies explicitly shown ({})", "node.role == external")
    _add("firewall", "Firewall present", "M", "N",
         "firewall, waf, security",
         "Firewall/WAF protects the perimeter ({})", "node.role == firewall")
    _add("monitoring", "Monitoring present", "M", "N",
         "monitoring, observability, apm",
         "Monitoring/observability infrastructure shown ({})", "node.role == monitoring")
    _add("cdn", "CDN present", "L", "N",
         "cdn, edge, content delivery",
         "CDN layer for edge content delivery ({})", "node.role == cdn")
    _add("auth_service", "Auth service present", "H", "Y",
         "auth, identity, authentication",
         "Dedicated auth/identity service shown ({})", "node.role == auth_service")

    return rules


def _derive_connectivity_rules(edges: List[DiagramEdge], nodes: List[DiagramNode]) -> List[Dict]:
    """Derive rules from edge connectivity patterns."""
    rules: List[Dict] = []
    if not edges:
        return rules

    node_map = {n.id: n for n in nodes}
    datastore_ids = {n.id for n in nodes if n.role == "datastore"}
    gateway_ids = {n.id for n in nodes if n.role == "gateway"}
    external_ids = {n.id for n in nodes if n.role == "external"}

    if gateway_ids and external_ids:
        external_bypasses_gateway = False
        for e in edges:
            if e.source in external_ids and e.target not in gateway_ids:
                external_bypasses_gateway = True
                break
            if e.target in external_ids and e.source not in gateway_ids:
                external_bypasses_gateway = True
                break
        if not external_bypasses_gateway:
            relevant = [e for e in edges if e.source in external_ids or e.target in external_ids]
            conf = min((e.confidence for e in relevant), default=1.0)
            rules.append({
                "rule": "External traffic via gateway", "sev": "C", "req": "Y",
                "keywords": "gateway, external, routing, perimeter",
                "condition": "All external traffic routes through API gateway",
                "ast_condition": "edge(external, *) -> node.role == gateway",
                "confidence": conf,
            })

    if datastore_ids and external_ids:
        direct_db = any(
            (e.source in external_ids and e.target in datastore_ids) or
            (e.target in external_ids and e.source in datastore_ids)
            for e in edges
        )
        relevant = [e for e in edges if
                     (e.source in external_ids and e.target in datastore_ids) or
                     (e.target in external_ids and e.source in datastore_ids)]
        conf = min((e.confidence for e in relevant), default=1.0) if relevant else 1.0
        if direct_db:
            rules.append({
                "rule": "Direct external DB access", "sev": "C", "req": "Y",
                "keywords": "database, external, direct, access",
                "condition": "External components have direct database access — must be mediated",
                "ast_condition": "edge(external, datastore) EXISTS",
                "confidence": conf,
            })
        else:
            rules.append({
                "rule": "No direct external DB access", "sev": "C", "req": "Y",
                "keywords": "database, isolation, access control",
                "condition": "No direct external access to data stores",
                "ast_condition": "NOT edge(external, datastore)",
                "confidence": 1.0,
            })

    return rules


def _derive_data_flow_rules(edges: List[DiagramEdge], nodes: List[DiagramNode],
                            groups: List[DiagramGroup]) -> List[Dict]:
    """Derive rules about data crossing zone boundaries."""
    rules: List[Dict] = []
    if not groups or not edges:
        return rules

    node_zone: Dict[str, str] = {}
    for g in groups:
        if g.zone_type:
            for child_id in g.children:
                node_zone[child_id] = g.zone_type

    for e in edges:
        src_zone = node_zone.get(e.source, "")
        dst_zone = node_zone.get(e.target, "")
        if src_zone and dst_zone and src_zone != dst_zone:
            if not e.protocol:
                rules.append({
                    "rule": "Data crosses zone boundary without encryption",
                    "sev": "H", "req": "Y",
                    "keywords": "zone, boundary, encryption, data flow",
                    "condition": f"Edge from {src_zone} to {dst_zone} zone has no protocol label",
                    "ast_condition": f"edge({src_zone}, {dst_zone}) AND edge.protocol == ''",
                    "confidence": e.confidence,
                })

    return _deduplicate_rules(rules)


def _derive_resilience_rules(edges: List[DiagramEdge], nodes: List[DiagramNode]) -> List[Dict]:
    """Derive rules about single points of failure and resilience."""
    rules: List[Dict] = []
    if not edges or not nodes:
        return rules

    in_degree: Dict[str, int] = {}
    for e in edges:
        in_degree[e.target] = in_degree.get(e.target, 0) + 1

    node_labels = {n.id: (n.label or n.id) for n in nodes}
    for n in nodes:
        if n.role == "actor":
            continue
        deg = in_degree.get(n.id, 0)
        if deg >= 3:
            label = node_labels.get(n.id, n.id)
            rules.append({
                "rule": f"Single point of failure — {label}",
                "sev": "H", "req": "N",
                "keywords": "spof, single point, failure, resilience",
                "condition": f"Node {label} has {deg} inbound edges and may be a single point of failure",
                "ast_condition": f"node({n.id}).in_degree >= 3",
                "confidence": n.confidence,
            })

    return rules


def _derive_fanout_rules(edges: List[DiagramEdge], nodes: List[DiagramNode]) -> List[Dict]:
    """Derive rules about high fan-out and orphan nodes."""
    rules: List[Dict] = []
    if not nodes:
        return rules

    out_degree: Dict[str, int] = {}
    connected: set = set()
    for e in edges:
        out_degree[e.source] = out_degree.get(e.source, 0) + 1
        connected.add(e.source)
        connected.add(e.target)

    node_labels = {n.id: (n.label or n.id) for n in nodes}

    for n in nodes:
        deg = out_degree.get(n.id, 0)
        if deg > 5:
            label = node_labels.get(n.id, n.id)
            rules.append({
                "rule": f"High fan-out — {label}",
                "sev": "M", "req": "N",
                "keywords": "fan-out, coupling, god service",
                "condition": f"Node {label} connects to {deg} downstream services",
                "ast_condition": f"node({n.id}).out_degree > 5",
                "confidence": n.confidence,
            })

    orphans = [n for n in nodes if n.id not in connected and n.role != "actor"]
    if orphans:
        labels = ", ".join(n.label or n.id for n in orphans[:5])
        conf = min(n.confidence for n in orphans)
        rules.append({
            "rule": "Orphan nodes detected",
            "sev": "L", "req": "N",
            "keywords": "orphan, disconnected, isolated",
            "condition": f"Disconnected nodes with no edges: {labels}",
            "ast_condition": "node.degree == 0",
            "confidence": conf,
        })

    return rules


def _derive_cross_diagram_rules(all_asts: List[DiagramAST]) -> List[Dict]:
    """Detect conflicting roles and implicit dependencies across diagrams."""
    rules: List[Dict] = []
    if len(all_asts) < 2:
        return rules

    label_roles: Dict[str, List[tuple]] = {}
    for i, ast in enumerate(all_asts):
        src = ast.metadata.get('source_file', f'diagram_{i}')
        for n in ast.nodes:
            key = (n.label or n.id).lower().strip()
            label_roles.setdefault(key, []).append((n.role, src, n.confidence))

    for label, entries in label_roles.items():
        roles_set = {r for r, _, _ in entries}
        if len(roles_set) > 1 and len(entries) >= 2:
            sources = set()
            min_conf = 1.0
            for role, src, conf in entries:
                sources.add(src)
                min_conf = min(min_conf, conf)
            roles_str = ", ".join(sorted(roles_set))
            rules.append({
                "rule": f"Conflicting roles for '{label}'",
                "sev": "M", "req": "N",
                "keywords": "cross-diagram, conflict, role",
                "condition": f"Node '{label}' has roles [{roles_str}] across diagrams",
                "ast_condition": f"cross_diagram: node.label == '{label}' roles=({roles_str})",
                "confidence": min_conf,
            })

    return rules


def extract_rules_from_ast(ast: DiagramAST) -> List[Dict]:
    """Extract all deterministic governance rules from a DiagramAST."""
    rules: List[Dict] = []
    rules.extend(_derive_protocol_rules(ast.edges))
    rules.extend(_derive_zone_rules(ast.groups, ast.nodes))
    rules.extend(_derive_role_rules(ast.nodes))
    rules.extend(_derive_connectivity_rules(ast.edges, ast.nodes))
    rules.extend(_derive_data_flow_rules(ast.edges, ast.nodes, ast.groups))
    rules.extend(_derive_resilience_rules(ast.edges, ast.nodes))
    rules.extend(_derive_fanout_rules(ast.edges, ast.nodes))
    return rules


def extract_rules_from_page(page_dir: Path) -> List[Dict]:
    """
    Extract rules from all AST files in a page directory.

    Looks for *.ast.json in the page directory and its attachments/ subdirectory.
    Also runs cross-diagram correlation when multiple ASTs exist.
    """
    all_rules: List[Dict] = []
    all_asts: List[DiagramAST] = []
    ast_files = list(page_dir.glob("*.ast.json")) + list((page_dir / "attachments").glob("*.ast.json"))

    for ast_path in ast_files:
        try:
            ast = load_ast(str(ast_path))
            all_asts.append(ast)
            rules = extract_rules_from_ast(ast)
            all_rules.extend(rules)
        except Exception:
            continue

    all_rules.extend(_derive_cross_diagram_rules(all_asts))
    return _deduplicate_rules(all_rules)


def _deduplicate_rules(rules: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Remove duplicate rules by (rule name, ast_condition) pair."""
    seen = set()
    unique = []
    for r in rules:
        key = (r["rule"], r.get("ast_condition", ""))
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique


# ──────────────────────────────────────────────────────────────────
# Write rules.md per page
# ──────────────────────────────────────────────────────────────────

def _fingerprint(path: Path) -> str:
    """MD5 fingerprint of the first 64KB of a file."""
    data = path.read_bytes()[:65536]
    return hashlib.md5(data).hexdigest()[:12]


def _infer_rule_category(rule: Dict) -> str:
    """Infer the derivation category from rule content for ID generation."""
    ast_cond = rule.get("ast_condition", "")
    rule_name = rule.get("rule", "").lower()
    if "edge.protocol" in ast_cond or "protocol" in rule_name:
        return "protocol"
    if "group.zone_type" in ast_cond or "zone" in rule_name:
        return "zone"
    if "node.role" in ast_cond:
        return "role"
    if "cross_diagram" in ast_cond:
        return "cross"
    if "edge(" in ast_cond:
        if "data" in rule_name or "boundary" in rule_name:
            return "data_flow"
        return "connectivity"
    if "in_degree" in ast_cond or "single point" in rule_name:
        return "resilience"
    if "out_degree" in ast_cond or "fan-out" in rule_name or "orphan" in rule_name:
        return "fanout"
    return "role"


def write_rules_md(
    rules: List[Dict],
    page_id: str,
    page_dir: Path,
    category: str,
    source_path: Optional[Path] = None,
) -> Path:
    """Write a per-page rules.md file with stable content-hashed IDs."""
    if source_path is None:
        source_path = page_dir / "page.md"

    fp = _fingerprint(source_path) if source_path.exists() else "unknown"
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines = [
        f"# Rules - {page_id}",
        "",
        f"> Source: {source_path} | Extracted: {now} | Model: deterministic | Category: {category} | Fingerprint: {fp}",
        "",
    ]

    if not rules:
        lines.append("_No structural rules derived from diagrams._")
    else:
        lines.append("| ID | Rule | Sev | Req | Keywords | Condition | AST Condition | Conf |")
        lines.append("|----|------|-----|-----|----------|-----------|---------------|------|")
        for r in rules:
            cat = _infer_rule_category(r)
            rid = _make_rule_id(cat, r['rule'], r.get('ast_condition', ''))
            conf = r.get('confidence', 1.0)
            conf_str = f"{conf:.2f}"
            lines.append(
                f"| {rid} | {r['rule']} | {r['sev']} | {r['req']} "
                f"| {r['keywords']} | {r['condition']} | {r.get('ast_condition', '')} | {conf_str} |"
            )

    out_path = page_dir / "rules.md"
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path


# ──────────────────────────────────────────────────────────────────
# Consolidated _all.rules.md
# ──────────────────────────────────────────────────────────────────

def update_all_rules(
    index_dir: Path,
    page_id: str,
    new_rules: List[Dict],
    category: str,
) -> Path:
    """Create or update _all.rules.md with stable content-hashed IDs."""
    all_rules_path = index_dir / "_all.rules.md"

    existing_rules: List[Dict] = []
    existing_sources: Dict[str, int] = {}

    if all_rules_path.exists():
        existing_rules, existing_sources = _parse_all_rules(all_rules_path)

    filtered = [r for r in existing_rules if r.get("_source") != page_id]
    for r in new_rules:
        r["_source"] = page_id
    merged = filtered + new_rules
    merged = _deduplicate_rules_with_source(merged)

    source_counts: Dict[str, int] = {}
    for r in merged:
        src = r.get("_source", "unknown")
        source_counts[src] = source_counts.get(src, 0) + 1

    sev_counts = {"C": 0, "H": 0, "M": 0, "L": 0}
    for r in merged:
        sev = r.get("sev", "M")
        if sev in sev_counts:
            sev_counts[sev] += 1

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"# Consolidated Rules - {category}",
        "",
        f"> Sources: {len(source_counts)} documents | Extracted: {now} | Model: deterministic | Category: {category}",
        ">",
    ]
    for src, count in sorted(source_counts.items()):
        lines.append(f"> - {src}/page.md ({count} rules)")
    lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append("| Severity | Count |")
    lines.append("|----------|-------|")
    lines.append(f"| Critical | {sev_counts['C']} |")
    lines.append(f"| High | {sev_counts['H']} |")
    lines.append(f"| Medium | {sev_counts['M']} |")
    lines.append(f"| Low | {sev_counts['L']} |")
    lines.append(f"| **Total** | **{len(merged)}** |")
    lines.append("")

    lines.append("## All Rules")
    lines.append("")
    lines.append("| ID | Rule | Sev | Req | Keywords | Condition | AST Condition | Conf | Source |")
    lines.append("|----|------|-----|-----|----------|-----------|---------------|------|--------|")
    for r in merged:
        cat = _infer_rule_category(r)
        rid = _make_rule_id(cat, r['rule'], r.get('ast_condition', ''))
        conf_str = f"{r.get('confidence', 1.0):.2f}"
        src = r.get("_source", "")
        lines.append(
            f"| {rid} | {r['rule']} | {r['sev']} | {r['req']} "
            f"| {r['keywords']} | {r['condition']} | {r.get('ast_condition', '')} | {conf_str} | {src} |"
        )
    lines.append("")

    all_rules_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return all_rules_path


def _parse_all_rules(path: Path) -> tuple:
    """Parse an existing _all.rules.md to extract rules and source info.

    Handles both old format (7 columns) and new format (9 columns with Conf + Source).
    """
    content = path.read_text(encoding="utf-8")
    rules = []
    sources: Dict[str, int] = {}

    in_table = False
    for line in content.split("\n"):
        if line.startswith("| ID") or line.startswith("|-"):
            in_table = True
            continue
        if in_table and line.startswith("|"):
            cols = [c.strip() for c in line.split("|")[1:-1]]
            if len(cols) >= 7:
                r: Dict[str, Any] = {
                    "rule": cols[1],
                    "sev": cols[2],
                    "req": cols[3],
                    "keywords": cols[4],
                    "condition": cols[5],
                    "ast_condition": cols[6] if len(cols) > 6 else "",
                }
                if len(cols) >= 9:
                    try:
                        r["confidence"] = float(cols[7])
                    except (ValueError, IndexError):
                        r["confidence"] = 1.0
                    r["_source"] = cols[8] if len(cols) > 8 else ""
                elif len(cols) >= 8:
                    r["_source"] = cols[7]
                    r["confidence"] = 1.0
                else:
                    r["_source"] = ""
                    r["confidence"] = 1.0
                rules.append(r)
                src = r["_source"]
                if src:
                    sources[src] = sources.get(src, 0) + 1
        elif in_table and not line.startswith("|"):
            in_table = False

    return rules, sources


def _deduplicate_rules_with_source(rules: List[Dict]) -> List[Dict]:
    """Deduplicate by (rule, ast_condition) keeping highest severity and confidence."""
    sev_rank = {"C": 0, "H": 1, "M": 2, "L": 3}
    best: Dict[tuple, Dict] = {}
    for r in rules:
        key = (r["rule"], r.get("ast_condition", ""))
        existing = best.get(key)
        if existing is None or sev_rank.get(r["sev"], 9) < sev_rank.get(existing["sev"], 9):
            best[key] = r
        elif (sev_rank.get(r["sev"], 9) == sev_rank.get(existing["sev"], 9) and
              r.get("confidence", 1.0) > existing.get("confidence", 1.0)):
            best[key] = r
    return list(best.values())


# ──────────────────────────────────────────────────────────────────
# Top-level: extract + write + consolidate (called from ingest_page)
# ──────────────────────────────────────────────────────────────────

def extract_and_write_rules(
    page_id: str,
    index: str,
    output_dir: str = "governance/output",
    indexes_dir: str = "governance/indexes",
) -> Dict[str, Any]:
    """
    Full deterministic rules pipeline for a single page.

    1. Find AST files in output dir
    2. Extract structural rules from ASTs
    3. Write per-page rules.md to the index
    4. Update _all.rules.md at index root

    Returns dict with rules count and paths.
    """
    output_page = Path(output_dir) / page_id
    index_page = Path(indexes_dir) / index / page_id

    rules = extract_rules_from_page(output_page)

    if not index_page.exists():
        index_page.mkdir(parents=True, exist_ok=True)

    rules_path = write_rules_md(
        rules, page_id, index_page, category=index,
        source_path=index_page / "page.md",
    )
    print(f"  Rules extracted: {len(rules)} → {rules_path}", file=sys.stderr)

    index_dir = Path(indexes_dir) / index
    all_path = update_all_rules(index_dir, page_id, rules, category=index)
    print(f"  Consolidated: {all_path}", file=sys.stderr)

    return {
        "rules_count": len(rules),
        "rules_path": str(rules_path),
        "all_rules_path": str(all_path),
    }


# ──────────────────────────────────────────────────────────────────
# Batch mode: process all pages in an index folder
# ──────────────────────────────────────────────────────────────────

def batch_extract(
    index_dir: str,
    category: Optional[str] = None,
    refresh_only: bool = False,
) -> Dict[str, Any]:
    """
    Extract rules for all pages in an index folder.

    Args:
        index_dir: Path like governance/indexes/security/
        category: Category name (auto-detected from folder name if omitted)
        refresh_only: If True, only process stale/missing pages

    Returns dict with per-page results and totals.
    """
    idx = Path(index_dir)
    if not idx.is_dir():
        print(f"Error: {index_dir} is not a directory", file=sys.stderr)
        return {"error": f"{index_dir} not found", "pages": {}}

    if category is None:
        category = idx.name

    subfolders = sorted(
        d for d in idx.iterdir()
        if d.is_dir() and not d.name.startswith("_") and not d.name.startswith(".")
    )

    results: Dict[str, Any] = {}
    total_rules = 0

    for subdir in subfolders:
        page_id = subdir.name
        page_md = subdir / "page.md"
        if not page_md.exists():
            continue

        if refresh_only:
            rules_md = subdir / "rules.md"
            if rules_md.exists():
                stored_fp = _read_stored_fingerprint(rules_md)
                current_fp = _fingerprint(page_md)
                if stored_fp and stored_fp == current_fp:
                    print(f"  {page_id}: current (skipped)", file=sys.stderr)
                    results[page_id] = {"status": "current", "rules_count": 0}
                    continue

        rules = extract_rules_from_page(subdir)
        rules_path = write_rules_md(rules, page_id, subdir, category=category)
        print(f"  {page_id}: {len(rules)} rules → {rules_path}", file=sys.stderr)

        results[page_id] = {"status": "extracted", "rules_count": len(rules)}
        total_rules += len(rules)

    all_path = _rebuild_all_rules(idx, category)
    print(f"\n  Consolidated: {all_path} ({total_rules} total rules)", file=sys.stderr)

    return {
        "index": index_dir,
        "category": category,
        "pages": results,
        "total_rules": total_rules,
        "all_rules_path": str(all_path),
    }


def _read_stored_fingerprint(rules_md: Path) -> str:
    """Read the Fingerprint from rules.md metadata."""
    try:
        for line in rules_md.read_text(encoding="utf-8").split("\n")[:10]:
            m = re.search(r"Fingerprint:\s*([a-f0-9]{12})", line)
            if m:
                return m.group(1)
    except (IOError, OSError):
        pass
    return ""


def _rebuild_all_rules(index_dir: Path, category: str) -> Path:
    """Rebuild _all.rules.md from scratch by reading all per-page rules.md files."""
    all_rules: List[Dict] = []

    subfolders = sorted(
        d for d in index_dir.iterdir()
        if d.is_dir() and not d.name.startswith("_") and not d.name.startswith(".")
    )

    for subdir in subfolders:
        rules_md = subdir / "rules.md"
        if not rules_md.exists():
            continue

        page_id = subdir.name
        page_rules = _parse_page_rules(rules_md, page_id)
        all_rules.extend(page_rules)

    all_rules = _deduplicate_rules_with_source(all_rules)

    sev_counts = {"C": 0, "H": 0, "M": 0, "L": 0}
    source_counts: Dict[str, int] = {}
    for r in all_rules:
        sev = r.get("sev", "M")
        if sev in sev_counts:
            sev_counts[sev] += 1
        src = r.get("_source", "unknown")
        source_counts[src] = source_counts.get(src, 0) + 1

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"# Consolidated Rules - {category}",
        "",
        f"> Sources: {len(source_counts)} documents | Extracted: {now} | Model: deterministic | Category: {category}",
        ">",
    ]
    for src, count in sorted(source_counts.items()):
        lines.append(f"> - {src}/page.md ({count} rules)")
    lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append("| Severity | Count |")
    lines.append("|----------|-------|")
    lines.append(f"| Critical | {sev_counts['C']} |")
    lines.append(f"| High | {sev_counts['H']} |")
    lines.append(f"| Medium | {sev_counts['M']} |")
    lines.append(f"| Low | {sev_counts['L']} |")
    lines.append(f"| **Total** | **{len(all_rules)}** |")
    lines.append("")

    lines.append("## All Rules")
    lines.append("")
    lines.append("| ID | Rule | Sev | Req | Keywords | Condition | AST Condition | Conf | Source |")
    lines.append("|----|------|-----|-----|----------|-----------|---------------|------|--------|")
    for r in all_rules:
        cat = _infer_rule_category(r)
        rid = _make_rule_id(cat, r['rule'], r.get('ast_condition', ''))
        conf_str = f"{r.get('confidence', 1.0):.2f}"
        src = r.get("_source", "")
        lines.append(
            f"| {rid} | {r['rule']} | {r['sev']} | {r['req']} "
            f"| {r['keywords']} | {r['condition']} | {r.get('ast_condition', '')} | {conf_str} | {src} |"
        )
    lines.append("")

    all_path = index_dir / "_all.rules.md"
    all_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return all_path


def _parse_page_rules(rules_md: Path, page_id: str) -> List[Dict]:
    """Parse rules from a per-page rules.md file. Handles old and new formats."""
    rules: List[Dict] = []
    in_table = False
    for line in rules_md.read_text(encoding="utf-8").split("\n"):
        if line.startswith("| ID") or line.startswith("|-"):
            in_table = True
            continue
        if in_table and line.startswith("|"):
            cols = [c.strip() for c in line.split("|")[1:-1]]
            if len(cols) >= 6:
                r: Dict[str, Any] = {
                    "rule": cols[1],
                    "sev": cols[2],
                    "req": cols[3],
                    "keywords": cols[4],
                    "condition": cols[5],
                    "ast_condition": cols[6] if len(cols) > 6 else "",
                    "_source": page_id,
                }
                if len(cols) >= 8:
                    try:
                        r["confidence"] = float(cols[7])
                    except (ValueError, IndexError):
                        r["confidence"] = 1.0
                else:
                    r["confidence"] = 1.0
                rules.append(r)
        elif in_table and not line.startswith("|"):
            in_table = False
    return rules


# ──────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Deterministic rules extraction from AST data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Extract rules for all pages in an index
  python -m ingest.extract_rules --folder governance/indexes/security/

  # Refresh only stale pages
  python -m ingest.extract_rules --folder governance/indexes/security/ --refresh

  # Extract for a single page (after ingestion)
  python -m ingest.extract_rules --page 123456789 --index security

  # Check all indexes
  python -m ingest.extract_rules --all
        """,
    )
    parser.add_argument("--folder", "-f", help="Index folder to process (batch mode)")
    parser.add_argument("--all", action="store_true", help="Process all governance/indexes/*/ folders")
    parser.add_argument("--refresh", action="store_true", help="Only process stale/missing pages")
    parser.add_argument("--page", "-p", help="Single page ID")
    parser.add_argument("--index", "-i", help="Index name (for single page mode)")
    parser.add_argument("--category", "-c", help="Category override (auto-detected from folder name)")

    args = parser.parse_args()

    if args.all:
        indexes_dir = Path("governance/indexes")
        if not indexes_dir.is_dir():
            print("Error: governance/indexes/ not found", file=sys.stderr)
            sys.exit(1)
        for folder in sorted(d for d in indexes_dir.iterdir() if d.is_dir()):
            print(f"\n{'='*60}", file=sys.stderr)
            print(f"  Index: {folder.name}", file=sys.stderr)
            print(f"{'='*60}", file=sys.stderr)
            batch_extract(str(folder), refresh_only=args.refresh)
        return

    if args.folder:
        result = batch_extract(args.folder, category=args.category, refresh_only=args.refresh)
        print(json.dumps(result, indent=2))
        return

    if args.page and args.index:
        result = extract_and_write_rules(args.page, args.index)
        print(json.dumps(result, indent=2))
        return

    parser.error("Provide --folder, --all, or --page + --index")


if __name__ == "__main__":
    main()
