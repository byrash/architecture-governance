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


# ──────────────────────────────────────────────────────────────────
# Rule derivation from AST
# ──────────────────────────────────────────────────────────────────

def _derive_protocol_rules(edges: List[DiagramEdge]) -> List[Dict[str, str]]:
    """Derive rules from edge protocols (e.g. all traffic uses HTTPS)."""
    rules = []
    protocols = {e.protocol.upper() for e in edges if e.protocol}
    if not protocols:
        return rules

    secure = {"HTTPS", "MTLS", "TLS", "GRPC"}
    insecure = {"HTTP"}

    used_secure = protocols & secure
    used_insecure = protocols & insecure

    if used_secure and not used_insecure:
        rules.append({
            "rule": "Secure transport",
            "sev": "C", "req": "Y",
            "keywords": ", ".join(sorted(p.lower() for p in used_secure)),
            "condition": f"All communication uses secure protocols ({', '.join(sorted(used_secure))})",
            "ast_condition": f"edge.protocol IN ({', '.join(sorted(used_secure))})",
        })
    elif used_insecure:
        rules.append({
            "rule": "Insecure transport present",
            "sev": "H", "req": "Y",
            "keywords": "http, insecure, transport",
            "condition": "Some edges use insecure HTTP — upgrade to HTTPS/TLS",
            "ast_condition": f"edge.protocol IN ({', '.join(sorted(used_insecure))})",
        })

    for proto in sorted(protocols):
        if proto not in secure and proto not in insecure and proto:
            rules.append({
                "rule": f"{proto} protocol used",
                "sev": "M", "req": "N",
                "keywords": proto.lower(),
                "condition": f"Communication protocol {proto} is used between components",
                "ast_condition": f"edge.protocol == {proto}",
            })

    return rules


def _derive_zone_rules(groups: List[DiagramGroup], nodes: List[DiagramNode]) -> List[Dict[str, str]]:
    """Derive rules from group zones (e.g. DMZ, internal, external boundaries)."""
    rules = []
    zones = {g.zone_type: g for g in groups if g.zone_type}
    if not zones:
        return rules

    zone_names = sorted(zones.keys())
    rules.append({
        "rule": "Zone boundaries defined",
        "sev": "H", "req": "Y",
        "keywords": ", ".join(zone_names),
        "condition": f"Architecture defines zone boundaries: {', '.join(zone_names)}",
        "ast_condition": f"group.zone_type IN ({', '.join(zone_names)})",
    })

    if "dmz" in zones:
        rules.append({
            "rule": "DMZ zone present",
            "sev": "C", "req": "Y",
            "keywords": "dmz, perimeter, network",
            "condition": "A DMZ zone separates external traffic from internal services",
            "ast_condition": "group.zone_type == dmz",
        })

    if "external" in zones and "internal" in zones:
        rules.append({
            "rule": "External/internal separation",
            "sev": "C", "req": "Y",
            "keywords": "external, internal, isolation",
            "condition": "External and internal zones are explicitly separated",
            "ast_condition": "group.zone_type IN (external, internal)",
        })

    return rules


def _derive_role_rules(nodes: List[DiagramNode]) -> List[Dict[str, str]]:
    """Derive rules from node roles (e.g. gateway exists, datastores present)."""
    rules = []
    roles = {}
    for n in nodes:
        if n.role:
            roles.setdefault(n.role, []).append(n.label or n.id)

    if "gateway" in roles:
        gateways = roles["gateway"]
        rules.append({
            "rule": "API gateway present",
            "sev": "H", "req": "Y",
            "keywords": "gateway, api, routing",
            "condition": f"Traffic routes through gateway ({', '.join(gateways[:3])})",
            "ast_condition": "node.role == gateway",
        })

    if "load_balancer" in roles:
        rules.append({
            "rule": "Load balancer present",
            "sev": "M", "req": "N",
            "keywords": "load balancer, availability, scaling",
            "condition": "Load balancer distributes traffic for availability",
            "ast_condition": "node.role == load_balancer",
        })

    if "datastore" in roles:
        stores = roles["datastore"]
        rules.append({
            "rule": "Data stores identified",
            "sev": "H", "req": "Y",
            "keywords": "database, datastore, persistence",
            "condition": f"Data stores explicitly shown ({', '.join(stores[:3])})",
            "ast_condition": "node.role == datastore",
        })

    if "cache" in roles:
        rules.append({
            "rule": "Caching layer present",
            "sev": "L", "req": "N",
            "keywords": "cache, performance, latency",
            "condition": "Caching layer exists for performance",
            "ast_condition": "node.role == cache",
        })

    if "queue" in roles:
        rules.append({
            "rule": "Async messaging present",
            "sev": "M", "req": "N",
            "keywords": "queue, async, messaging, decoupling",
            "condition": "Asynchronous messaging via queues for decoupling",
            "ast_condition": "node.role == queue",
        })

    if "external" in roles:
        externals = roles["external"]
        rules.append({
            "rule": "External dependencies documented",
            "sev": "H", "req": "Y",
            "keywords": "external, dependency, third-party",
            "condition": f"External dependencies explicitly shown ({', '.join(externals[:3])})",
            "ast_condition": "node.role == external",
        })

    return rules


def _derive_connectivity_rules(edges: List[DiagramEdge], nodes: List[DiagramNode]) -> List[Dict[str, str]]:
    """Derive rules from edge connectivity patterns."""
    rules = []
    if not edges:
        return rules

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
            rules.append({
                "rule": "External traffic via gateway",
                "sev": "C", "req": "Y",
                "keywords": "gateway, external, routing, perimeter",
                "condition": "All external traffic routes through API gateway",
                "ast_condition": "edge(external, *) -> node.role == gateway",
            })

    if datastore_ids and external_ids:
        direct_db = any(
            (e.source in external_ids and e.target in datastore_ids) or
            (e.target in external_ids and e.source in datastore_ids)
            for e in edges
        )
        if direct_db:
            rules.append({
                "rule": "Direct external DB access",
                "sev": "C", "req": "Y",
                "keywords": "database, external, direct, access",
                "condition": "External components have direct database access — must be mediated",
                "ast_condition": "edge(external, datastore) EXISTS",
            })
        else:
            rules.append({
                "rule": "No direct external DB access",
                "sev": "C", "req": "Y",
                "keywords": "database, isolation, access control",
                "condition": "No direct external access to data stores",
                "ast_condition": "NOT edge(external, datastore)",
            })

    return rules


def extract_rules_from_ast(ast: DiagramAST) -> List[Dict[str, str]]:
    """Extract all deterministic governance rules from a DiagramAST."""
    rules = []
    rules.extend(_derive_protocol_rules(ast.edges))
    rules.extend(_derive_zone_rules(ast.groups, ast.nodes))
    rules.extend(_derive_role_rules(ast.nodes))
    rules.extend(_derive_connectivity_rules(ast.edges, ast.nodes))
    return rules


def extract_rules_from_page(page_dir: Path) -> List[Dict[str, str]]:
    """
    Extract rules from all AST files in a page directory.

    Looks for *.ast.json in the page directory and its attachments/ subdirectory.
    """
    all_rules = []
    ast_files = list(page_dir.glob("*.ast.json")) + list((page_dir / "attachments").glob("*.ast.json"))

    for ast_path in ast_files:
        try:
            ast = load_ast(str(ast_path))
            rules = extract_rules_from_ast(ast)
            all_rules.extend(rules)
        except Exception:
            continue

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


def write_rules_md(
    rules: List[Dict[str, str]],
    page_id: str,
    page_dir: Path,
    category: str,
    source_path: Optional[Path] = None,
) -> Path:
    """Write a per-page rules.md file and return its path."""
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
        lines.append("| ID | Rule | Sev | Req | Keywords | Condition | AST Condition |")
        lines.append("|----|------|-----|-----|----------|-----------|---------------|")
        for i, r in enumerate(rules, 1):
            rid = f"R-{i:03d}"
            lines.append(
                f"| {rid} | {r['rule']} | {r['sev']} | {r['req']} "
                f"| {r['keywords']} | {r['condition']} | {r.get('ast_condition', '')} |"
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
    new_rules: List[Dict[str, str]],
    category: str,
) -> Path:
    """
    Create or update _all.rules.md at the index root.

    If the file exists, merges new rules from this page (replacing any
    previously extracted rules for the same page_id). If it doesn't exist,
    creates it from scratch.
    """
    all_rules_path = index_dir / "_all.rules.md"

    existing_rules: List[Dict[str, str]] = []
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
    lines.append("| ID | Rule | Sev | Req | Keywords | Condition | AST Condition | Source |")
    lines.append("|----|------|-----|-----|----------|-----------|---------------|--------|")
    for i, r in enumerate(merged, 1):
        rid = f"R-{i:03d}"
        src = r.get("_source", "")
        lines.append(
            f"| {rid} | {r['rule']} | {r['sev']} | {r['req']} "
            f"| {r['keywords']} | {r['condition']} | {r.get('ast_condition', '')} | {src} |"
        )
    lines.append("")

    all_rules_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return all_rules_path


def _parse_all_rules(path: Path) -> tuple:
    """Parse an existing _all.rules.md to extract rules and source info."""
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
                r = {
                    "rule": cols[1],
                    "sev": cols[2],
                    "req": cols[3],
                    "keywords": cols[4],
                    "condition": cols[5],
                    "ast_condition": cols[6] if len(cols) > 6 else "",
                    "_source": cols[7] if len(cols) > 7 else "",
                }
                rules.append(r)
                src = r["_source"]
                if src:
                    sources[src] = sources.get(src, 0) + 1
        elif in_table and not line.startswith("|"):
            in_table = False

    return rules, sources


def _deduplicate_rules_with_source(rules: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Deduplicate by (rule, ast_condition) keeping highest severity."""
    sev_rank = {"C": 0, "H": 1, "M": 2, "L": 3}
    best: Dict[tuple, Dict[str, str]] = {}
    for r in rules:
        key = (r["rule"], r.get("ast_condition", ""))
        existing = best.get(key)
        if existing is None or sev_rank.get(r["sev"], 9) < sev_rank.get(existing["sev"], 9):
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
    all_rules: List[Dict[str, str]] = []

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
    lines.append("| ID | Rule | Sev | Req | Keywords | Condition | AST Condition | Source |")
    lines.append("|----|------|-----|-----|----------|-----------|---------------|--------|")
    for i, r in enumerate(all_rules, 1):
        rid = f"R-{i:03d}"
        src = r.get("_source", "")
        lines.append(
            f"| {rid} | {r['rule']} | {r['sev']} | {r['req']} "
            f"| {r['keywords']} | {r['condition']} | {r.get('ast_condition', '')} | {src} |"
        )
    lines.append("")

    all_path = index_dir / "_all.rules.md"
    all_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return all_path


def _parse_page_rules(rules_md: Path, page_id: str) -> List[Dict[str, str]]:
    """Parse rules from a per-page rules.md file."""
    rules = []
    in_table = False
    for line in rules_md.read_text(encoding="utf-8").split("\n"):
        if line.startswith("| ID") or line.startswith("|-"):
            in_table = True
            continue
        if in_table and line.startswith("|"):
            cols = [c.strip() for c in line.split("|")[1:-1]]
            if len(cols) >= 6:
                rules.append({
                    "rule": cols[1],
                    "sev": cols[2],
                    "req": cols[3],
                    "keywords": cols[4],
                    "condition": cols[5],
                    "ast_condition": cols[6] if len(cols) > 6 else "",
                    "_source": page_id,
                })
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
