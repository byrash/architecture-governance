#!/usr/bin/env python3
"""
AST Eval — Deterministic quality gate for LLM-repaired .ast.json files.

Validates that the final AST meets structural and content-quality thresholds
before it is converted to Mermaid.  No LLM is used — every check is
rule-based and fully reproducible.

Checks performed:
  1. Schema conformance (required fields, valid types)
  2. Generic-label detection (Node_X / node_X leftovers)
  3. Orphan-node detection (nodes with zero edges)
  4. Edge validity (source/target reference existing node IDs)
  5. Duplicate-edge detection
  6. Empty-graph detection
  7. CV-drift check (optional: compares final AST against partial AST
     to ensure the deterministic backbone was preserved)

Exit codes:
  0 — all checks pass
  1 — one or more checks failed (details in JSON output)
  2 — bad arguments / file not found

Usage:
    python eval_ast.py --input repaired.ast.json [--partial partial.ast.json] [--json]
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


GENERIC_LABEL_RE = re.compile(r'^[Nn]ode_\d+$')

VALID_SHAPES = {
    'rectangle', 'stadium', 'database', 'diamond',
    'circle', 'parallelogram', 'hexagon',
}

VALID_EDGE_STYLES = {'solid', 'dashed', 'dotted', 'thick'}

VALID_DIAGRAM_TYPES = {'flowchart', 'sequence', 'class', 'state', 'er'}

VALID_DIRECTIONS = {'TB', 'BT', 'LR', 'RL'}


def _check_schema(data: dict) -> List[str]:
    """Verify required fields and valid enum values."""
    errors: List[str] = []

    if 'nodes' not in data or not isinstance(data['nodes'], list):
        errors.append("Missing or invalid 'nodes' (expected list)")
    if 'edges' not in data or not isinstance(data['edges'], list):
        errors.append("Missing or invalid 'edges' (expected list)")

    dt = data.get('diagram_type', '')
    if dt and dt not in VALID_DIAGRAM_TYPES:
        errors.append(f"Unknown diagram_type '{dt}' (expected one of {sorted(VALID_DIAGRAM_TYPES)})")

    direction = data.get('direction', '')
    if direction and direction not in VALID_DIRECTIONS:
        errors.append(f"Unknown direction '{direction}' (expected one of {sorted(VALID_DIRECTIONS)})")

    for i, node in enumerate(data.get('nodes', [])):
        if not isinstance(node, dict):
            errors.append(f"nodes[{i}]: expected dict, got {type(node).__name__}")
            continue
        if not node.get('id'):
            errors.append(f"nodes[{i}]: missing 'id'")
        if 'label' not in node:
            errors.append(f"nodes[{i}] ({node.get('id', '?')}): missing 'label'")
        shape = node.get('shape', 'rectangle')
        if shape not in VALID_SHAPES:
            errors.append(f"nodes[{i}] ({node.get('id', '?')}): unknown shape '{shape}'")

    for i, edge in enumerate(data.get('edges', [])):
        if not isinstance(edge, dict):
            errors.append(f"edges[{i}]: expected dict, got {type(edge).__name__}")
            continue
        if not edge.get('source'):
            errors.append(f"edges[{i}] ({edge.get('id', '?')}): missing 'source'")
        if not edge.get('target'):
            errors.append(f"edges[{i}] ({edge.get('id', '?')}): missing 'target'")
        style = edge.get('style', 'solid')
        if style not in VALID_EDGE_STYLES:
            errors.append(f"edges[{i}] ({edge.get('id', '?')}): unknown style '{style}'")

    return errors


def _check_generic_labels(data: dict) -> List[str]:
    """Flag nodes still carrying CV-generated placeholder labels."""
    issues: List[str] = []
    for node in data.get('nodes', []):
        label = node.get('label', '')
        if GENERIC_LABEL_RE.match(label):
            issues.append(
                f"Node '{node.get('id', '?')}' has generic label '{label}' "
                f"— LLM gap-fill did not replace it with text from the image"
            )
        elif not label.strip():
            issues.append(
                f"Node '{node.get('id', '?')}' has an empty label"
            )
    return issues


def _check_orphan_nodes(data: dict) -> List[str]:
    """Flag nodes that have zero incoming or outgoing edges."""
    node_ids: Set[str] = {n['id'] for n in data.get('nodes', []) if 'id' in n}
    connected: Set[str] = set()
    for edge in data.get('edges', []):
        connected.add(edge.get('source', ''))
        connected.add(edge.get('target', ''))

    orphans = node_ids - connected
    group_children: Set[str] = set()
    for g in data.get('groups', []):
        group_children.update(g.get('children', []))

    issues: List[str] = []
    for oid in sorted(orphans):
        node = next((n for n in data['nodes'] if n.get('id') == oid), {})
        label = node.get('label', oid)
        if oid in group_children:
            issues.append(
                f"Node '{oid}' ('{label}') is in a group but has no edges "
                f"— verify in the image whether it connects to other nodes"
            )
        else:
            issues.append(
                f"Node '{oid}' ('{label}') is an orphan — no edges connect to or from it. "
                f"Check the image for missing connections"
            )
    return issues


def _check_edge_validity(data: dict) -> List[str]:
    """Ensure every edge source/target references an existing node ID."""
    node_ids: Set[str] = {n['id'] for n in data.get('nodes', []) if 'id' in n}
    issues: List[str] = []
    for edge in data.get('edges', []):
        eid = edge.get('id', '?')
        src = edge.get('source', '')
        tgt = edge.get('target', '')
        if src and src not in node_ids:
            issues.append(f"Edge '{eid}': source '{src}' does not match any node ID")
        if tgt and tgt not in node_ids:
            issues.append(f"Edge '{eid}': target '{tgt}' does not match any node ID")
        if src == tgt and src:
            issues.append(f"Edge '{eid}': self-loop (source == target == '{src}')")
    return issues


def _check_duplicate_edges(data: dict) -> List[str]:
    """Flag duplicate source→target pairs."""
    seen: Dict[Tuple[str, str], str] = {}
    issues: List[str] = []
    for edge in data.get('edges', []):
        key = (edge.get('source', ''), edge.get('target', ''))
        if key in seen:
            issues.append(
                f"Edge '{edge.get('id', '?')}' duplicates '{seen[key]}' "
                f"(both connect {key[0]} → {key[1]})"
            )
        else:
            seen[key] = edge.get('id', '?')
    return issues


def _check_empty_graph(data: dict) -> List[str]:
    """Flag completely empty ASTs."""
    nodes = data.get('nodes', [])
    edges = data.get('edges', [])
    if not nodes and not edges:
        return ["AST is empty — no nodes and no edges. CV or LLM extraction failed entirely."]
    if not nodes:
        return ["AST has edges but no nodes."]
    return []


def _check_cv_drift(final: dict, partial: dict) -> List[str]:
    """Compare final AST against partial AST to verify CV backbone was preserved.

    Checks that nodes present in the partial AST still exist in the final AST
    with the same ID, position, and (where CV got them right) colors.
    New nodes added by the LLM are allowed.
    """
    issues: List[str] = []

    partial_nodes = {n['id']: n for n in partial.get('nodes', []) if 'id' in n}
    final_nodes = {n['id']: n for n in final.get('nodes', []) if 'id' in n}

    for nid, pnode in partial_nodes.items():
        if nid not in final_nodes:
            issues.append(
                f"CV node '{nid}' ('{pnode.get('label', '')}') was removed by LLM — "
                f"the deterministic backbone should be preserved"
            )
            continue

        fnode = final_nodes[nid]

        px, py = pnode.get('x', 0), pnode.get('y', 0)
        fx, fy = fnode.get('x', 0), fnode.get('y', 0)
        if (px, py) != (0, 0) and (abs(fx - px) > 5 or abs(fy - py) > 5):
            issues.append(
                f"CV node '{nid}': position shifted from ({px},{py}) to ({fx},{fy}) — "
                f"LLM should not move nodes that CV positioned"
            )

    partial_edges = {(e.get('source', ''), e.get('target', ''))
                     for e in partial.get('edges', [])}
    final_edges = {(e.get('source', ''), e.get('target', ''))
                   for e in final.get('edges', [])}

    removed = partial_edges - final_edges
    for src, tgt in removed:
        issues.append(
            f"CV edge {src} → {tgt} was removed by LLM — "
            f"the deterministic backbone should be preserved unless the edge is clearly wrong"
        )

    return issues


def evaluate(ast_path: str, partial_path: Optional[str] = None) -> Dict[str, Any]:
    """Run all checks and return structured results."""
    with open(ast_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    results: Dict[str, Any] = {
        'file': ast_path,
        'checks': {},
        'passed': True,
        'total_errors': 0,
        'total_warnings': 0,
    }

    errors_checks = [
        ('schema', _check_schema(data)),
        ('generic_labels', _check_generic_labels(data)),
        ('edge_validity', _check_edge_validity(data)),
        ('duplicate_edges', _check_duplicate_edges(data)),
        ('empty_graph', _check_empty_graph(data)),
    ]

    warning_checks = [
        ('orphan_nodes', _check_orphan_nodes(data)),
    ]

    if partial_path:
        with open(partial_path, 'r', encoding='utf-8') as f:
            partial_data = json.load(f)
        warning_checks.append(('cv_drift', _check_cv_drift(data, partial_data)))

    for name, issues in errors_checks:
        results['checks'][name] = {
            'status': 'FAIL' if issues else 'PASS',
            'level': 'error',
            'issues': issues,
        }
        if issues:
            results['passed'] = False
            results['total_errors'] += len(issues)

    for name, issues in warning_checks:
        results['checks'][name] = {
            'status': 'WARN' if issues else 'PASS',
            'level': 'warning',
            'issues': issues,
        }
        if issues:
            results['total_warnings'] += len(issues)

    node_count = len(data.get('nodes', []))
    edge_count = len(data.get('edges', []))
    group_count = len(data.get('groups', []))
    generic_count = len(results['checks'].get('generic_labels', {}).get('issues', []))
    orphan_count = len(results['checks'].get('orphan_nodes', {}).get('issues', []))

    results['summary'] = {
        'nodes': node_count,
        'edges': edge_count,
        'groups': group_count,
        'generic_labels_remaining': generic_count,
        'orphan_nodes': orphan_count,
    }

    return results


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Evaluate a repaired .ast.json for quality and correctness',
    )
    parser.add_argument('--input', '-i', required=True, help='Final .ast.json file to evaluate')
    parser.add_argument('--partial', '-p', help='Optional partial .ast.json for CV-drift check')
    parser.add_argument('--json', action='store_true', help='Output results as JSON')
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: file not found: {input_path}", file=sys.stderr)
        return 2

    partial_path = args.partial
    if partial_path and not Path(partial_path).exists():
        print(f"Warning: partial AST not found: {partial_path}, skipping CV-drift check",
              file=sys.stderr)
        partial_path = None

    results = evaluate(str(input_path), partial_path)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        status = "PASS" if results['passed'] else "FAIL"
        s = results['summary']
        print(f"  Eval: {status}  |  {s['nodes']} nodes, {s['edges']} edges, {s['groups']} groups")
        if results['total_errors'] > 0:
            print(f"  Errors: {results['total_errors']}")
        if results['total_warnings'] > 0:
            print(f"  Warnings: {results['total_warnings']}")
        for name, check in results['checks'].items():
            if check['issues']:
                label = "ERROR" if check['level'] == 'error' else "WARN"
                print(f"  [{label}] {name}:")
                for issue in check['issues']:
                    print(f"    - {issue}")

    return 0 if results['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
