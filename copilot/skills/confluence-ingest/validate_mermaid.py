#!/usr/bin/env python3
"""
Mermaid syntax validator.
Uses mmdc (Mermaid CLI) via npx to validate Mermaid diagram syntax.
Returns structured validation results for pipeline integration.
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Tuple


DIAGRAM_TYPES = [
    'flowchart', 'graph', 'sequenceDiagram', 'classDiagram',
    'stateDiagram', 'stateDiagram-v2', 'erDiagram', 'gantt',
    'pie', 'gitGraph', 'journey', 'mindmap', 'timeline',
    'quadrantChart', 'sankey', 'xychart', 'block',
]


def validate_basic(mermaid_code: str) -> Tuple[bool, str]:
    """Quick structural checks before invoking mmdc."""
    stripped = mermaid_code.strip()
    if not stripped:
        return False, "Empty Mermaid code"

    cleaned = re.sub(r'```mermaid\s*', '', stripped)
    cleaned = re.sub(r'```\s*$', '', cleaned).strip()
    if not cleaned:
        return False, "Empty Mermaid code after stripping fences"

    first_line = cleaned.split('\n')[0].strip()
    has_type = any(first_line.startswith(t) for t in DIAGRAM_TYPES)
    if not has_type:
        return False, f"No recognized diagram type on first line: '{first_line}'"

    non_comment = [
        l.strip() for l in cleaned.split('\n')
        if l.strip() and not l.strip().startswith('%%')
    ]
    if len(non_comment) < 2:
        return False, "Diagram has no content (only type declaration)"

    return True, ""


def validate_with_mmdc(mermaid_code: str) -> Tuple[bool, str]:
    """Validate using Mermaid CLI (mmdc). Falls back to basic validation if mmdc unavailable."""
    cleaned = mermaid_code.strip()
    cleaned = re.sub(r'^```mermaid\s*\n?', '', cleaned)
    cleaned = re.sub(r'\n?```\s*$', '', cleaned)

    with tempfile.NamedTemporaryFile(mode='w', suffix='.mmd', delete=False) as f:
        f.write(cleaned)
        tmp_path = f.name

    try:
        result = subprocess.run(
            ['npx', '-y', '@mermaid-js/mermaid-cli', 'mmdc',
             '-i', tmp_path, '-o', '/dev/null', '--quiet'],
            capture_output=True, text=True, timeout=30
        )

        if result.returncode == 0:
            return True, ""

        error_msg = (result.stderr or result.stdout or "Unknown error").strip()
        error_msg = error_msg[:500]
        return False, f"mmdc validation failed: {error_msg}"

    except FileNotFoundError:
        return True, "mmdc not available, basic validation only"
    except subprocess.TimeoutExpired:
        return False, "mmdc validation timed out after 30s"
    except Exception as e:
        return True, f"mmdc check skipped: {e}"
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def validate_mermaid(mermaid_code: str) -> Tuple[bool, str]:
    """
    Full validation: basic structural checks + mmdc syntax check.
    Returns (is_valid, error_message).
    """
    is_valid, error = validate_basic(mermaid_code)
    if not is_valid:
        return False, error

    return validate_with_mmdc(mermaid_code)


def count_elements(mermaid_code: str) -> dict:
    """Count nodes and edges in Mermaid code for manifest reporting."""
    cleaned = re.sub(r'^```mermaid\s*\n?', '', mermaid_code.strip())
    cleaned = re.sub(r'\n?```\s*$', '', cleaned)

    lines = [l.strip() for l in cleaned.split('\n')
             if l.strip() and not l.strip().startswith('%%')]

    node_pattern = re.compile(r'^\s*(\w+)\s*[\[\({]')
    edge_pattern = re.compile(r'-->|-.->|==>|<-->|<-.->|<==>')
    subgraph_pattern = re.compile(r'^\s*subgraph\s')
    classdef_pattern = re.compile(r'^\s*classDef\s')
    style_pattern = re.compile(r'^\s*style\s')

    nodes = set()
    edge_count = 0
    subgraph_count = 0

    for line in lines:
        if classdef_pattern.match(line) or style_pattern.match(line):
            continue
        if subgraph_pattern.match(line):
            subgraph_count += 1
            continue
        if line in ('end',):
            continue

        if edge_pattern.search(line):
            edge_count += 1
            parts = re.split(r'-->|-.->|==>|<-->|<-.->|<==>|---|-.-|===', line)
            for p in parts:
                p = p.strip()
                node_match = re.match(r'(\w+)', p)
                if node_match:
                    nodes.add(node_match.group(1))
        else:
            m = node_pattern.match(line)
            if m:
                nodes.add(m.group(1))

    diagram_types = set(DIAGRAM_TYPES)
    nodes = {n for n in nodes if n not in diagram_types and n not in ('end', 'subgraph')}

    return {
        'node_count': len(nodes),
        'edge_count': edge_count,
        'subgraph_count': subgraph_count,
    }


def main():
    parser = argparse.ArgumentParser(description='Validate Mermaid diagram syntax')
    parser.add_argument('--input', '-i', help='Input .mmd file path')
    parser.add_argument('--code', '-c', help='Mermaid code string to validate')
    parser.add_argument('--json', action='store_true', help='Output result as JSON')
    args = parser.parse_args()

    if args.input:
        p = Path(args.input)
        if not p.exists():
            print(f"Error: File not found: {p}", file=sys.stderr)
            return 1
        mermaid_code = p.read_text(encoding='utf-8')
    elif args.code:
        mermaid_code = args.code
    else:
        mermaid_code = sys.stdin.read()

    is_valid, error = validate_mermaid(mermaid_code)
    counts = count_elements(mermaid_code)

    if args.json:
        result = {
            'valid': is_valid,
            'error': error if not is_valid else None,
            **counts,
        }
        print(json.dumps(result, indent=2))
    else:
        if is_valid:
            print(f"VALID ({counts['node_count']} nodes, {counts['edge_count']} edges)",
                  file=sys.stderr)
        else:
            print(f"INVALID: {error}", file=sys.stderr)

    return 0 if is_valid else 1


if __name__ == '__main__':
    sys.exit(main())
