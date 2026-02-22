#!/usr/bin/env python3
"""
AST to Mermaid Converter — CLI tool

Reads a .ast.json file and outputs fenced Mermaid text.
This is a thin wrapper around diagram_ast.generate_mermaid().

Usage:
    python ast_to_mermaid.py --input diagram.ast.json [--output diagram.mmd]
"""

import argparse
import sys
from pathlib import Path

from diagram_ast import generate_mermaid, load_ast


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Convert an AST JSON IR file to Mermaid diagram syntax',
    )
    parser.add_argument('--input', '-i', required=True, help='Input .ast.json file')
    parser.add_argument('--output', '-o', help='Output file (default: stdout)')
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: file not found: {input_path}", file=sys.stderr)
        return 1

    ast = load_ast(str(input_path))
    mermaid = generate_mermaid(ast)

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(mermaid, encoding='utf-8')
        print(f"Written to {out}", file=sys.stderr)
    else:
        print(mermaid)

    return 0


if __name__ == '__main__':
    sys.exit(main())
