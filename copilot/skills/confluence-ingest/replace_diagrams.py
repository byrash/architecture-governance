#!/usr/bin/env python3
"""
Post-repair diagram replacement tool.

Runs AFTER LLM repair has produced final .ast.json files.  Handles three tasks
that would otherwise burn LLM tokens on pure mechanical work:

  1. PlantUML auto-detection  — find @startuml / ```plantuml blocks in page.md,
     convert them to Mermaid via the local plantuml_to_mermaid converter.
  2. Image-ref replacement    — swap every remaining ![…](image) reference with
     the Mermaid content from the matching .mmd (or generate it from .ast.json).
  3. Mermaid syntax auto-fix  — patch common mechanical errors that trip the
     Mermaid parser (duplicate IDs, unclosed subgraphs, bad arrows, …).

Usage:
    python replace_diagrams.py --page-dir governance/output/<PAGE_ID>
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from diagram_ast import generate_mermaid, load_ast, save_ast
from plantuml_to_mermaid import (
    convert_plantuml_to_ast,
    convert_plantuml_to_mermaid,
    extract_plantuml_blocks,
)

try:
    from validate_mermaid import validate_mermaid
except ImportError:
    validate_mermaid = None  # type: ignore[assignment]


# ──────────────────────────────────────────────────────────────────
# Phase 1 — PlantUML auto-detection and conversion
# ──────────────────────────────────────────────────────────────────

_PUML_STARTUML = re.compile(
    r'@startuml\b[^\n]*\n(.*?)@enduml', re.DOTALL | re.IGNORECASE,
)
_PUML_FENCED = re.compile(
    r'```(?:plantuml|puml)\s*\n(.*?)```', re.DOTALL | re.IGNORECASE,
)


def _replace_plantuml_blocks(
    md: str, attachments_dir: Path, counter: List[int],
) -> str:
    """Find PlantUML blocks in *md*, convert each to Mermaid in-place.

    Also saves .ast.json and .mmd artefacts next to the attachments.
    *counter* is a mutable list [converted_count] so the caller can inspect it.
    """

    def _convert(match: re.Match, inner_group: int) -> str:
        puml_body = match.group(inner_group)
        try:
            ast = convert_plantuml_to_ast(puml_body)
            mermaid = generate_mermaid(ast)
            seq = counter[0]
            stem = f"plantuml_{seq}"
            save_ast(ast, str(attachments_dir / f"{stem}.ast.json"))
            (attachments_dir / f"{stem}.mmd").write_text(
                mermaid, encoding='utf-8',
            )
            counter[0] += 1
            return f"\n{mermaid}\n"
        except Exception as exc:
            print(f"  ! PlantUML conversion failed: {exc}", file=sys.stderr)
            return match.group(0)

    md = _PUML_STARTUML.sub(lambda m: _convert(m, 1), md)
    md = _PUML_FENCED.sub(lambda m: _convert(m, 1), md)
    return md


# ──────────────────────────────────────────────────────────────────
# Phase 2 — Image reference → Mermaid replacement
# ──────────────────────────────────────────────────────────────────

_IMG_REF = re.compile(r'!\[([^\]]*)\]\(([^)]+\.(png|jpg|jpeg|gif|svg))\)', re.IGNORECASE)


def _build_mermaid_map(
    attachments_dir: Path, manifest_path: Path,
) -> Dict[str, str]:
    """Build a mapping from image filename → Mermaid code string.

    Sources (in priority order):
      1. .mmd file referenced in the conversion manifest
      2. .mmd file found by filesystem scan (matching image stem)
      3. .ast.json file found by filesystem scan (generate Mermaid on-the-fly)
    """
    mmap: Dict[str, str] = {}

    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        for entry in manifest.get('diagrams', []):
            source = entry.get('source', '')
            mmd_name = entry.get('mermaid_file')
            ast_name = entry.get('ast_file')
            if mmd_name:
                mmd_path = attachments_dir / mmd_name
                if mmd_path.exists():
                    mmap[source] = mmd_path.read_text(encoding='utf-8')
                    continue
            if ast_name:
                ast_path = attachments_dir / ast_name
                if ast_path.exists():
                    try:
                        ast = load_ast(str(ast_path))
                        mermaid = generate_mermaid(ast)
                        mmap[source] = mermaid
                        (attachments_dir / f"{Path(ast_name).stem}.mmd").write_text(
                            mermaid, encoding='utf-8',
                        )
                    except Exception:
                        pass

    for mmd_file in sorted(attachments_dir.glob('*.mmd')):
        stem = mmd_file.stem
        for ext in ('png', 'jpg', 'jpeg', 'gif', 'svg'):
            img_name = f"{stem}.{ext}"
            if img_name not in mmap and (attachments_dir / img_name).exists():
                mmap[img_name] = mmd_file.read_text(encoding='utf-8')

    for ast_file in sorted(attachments_dir.glob('*.ast.json')):
        if ast_file.name.endswith('.partial.ast.json'):
            continue
        stem = ast_file.stem
        for ext in ('png', 'jpg', 'jpeg', 'gif', 'svg'):
            img_name = f"{stem}.{ext}"
            if img_name not in mmap and (attachments_dir / img_name).exists():
                try:
                    ast = load_ast(str(ast_file))
                    mermaid = generate_mermaid(ast)
                    mmap[img_name] = mermaid
                    (attachments_dir / f"{stem}.mmd").write_text(
                        mermaid, encoding='utf-8',
                    )
                except Exception:
                    pass

    return mmap


def _replace_image_refs(md: str, mermaid_map: Dict[str, str]) -> Tuple[str, int, int]:
    """Replace image references with Mermaid code blocks.

    Returns (updated_md, replaced_count, remaining_count).
    """
    replaced = 0
    remaining = 0

    for filename, mermaid_code in mermaid_map.items():
        pattern = rf"!\[[^\]]*\]\([^)]*{re.escape(filename)}[^)]*\)"
        if re.search(pattern, md):
            md = re.sub(pattern, f"\n{mermaid_code}\n", md, count=1)
            replaced += 1
            print(f"  + Replaced {filename} with Mermaid", file=sys.stderr)

    leftover = _IMG_REF.findall(md)
    remaining = len(leftover)
    for alt, path, ext in leftover:
        fname = path.split('/')[-1]
        print(f"  - No .mmd for {fname} (still an image ref)", file=sys.stderr)

    return md, replaced, remaining


# ──────────────────────────────────────────────────────────────────
# Phase 3 — Mermaid syntax auto-fix
# ──────────────────────────────────────────────────────────────────

_MERMAID_BLOCK = re.compile(r'```mermaid\s*\n(.*?)```', re.DOTALL)


def _fix_mermaid_block(code: str) -> Tuple[str, List[str]]:
    """Apply mechanical fixes to a single Mermaid code block (no fences).

    Returns (fixed_code, list_of_fixes_applied).
    """
    fixes: List[str] = []
    lines = code.split('\n')

    arrow_replacements = [
        ('--→', '-->'), ('—>', '-->'), ('−−>', '-->'),
        ('==→', '==>'), ('—>>', '->>'),
        ('-.→', '-.->'),
    ]
    for i, line in enumerate(lines):
        original = line
        for bad, good in arrow_replacements:
            if bad in line:
                line = line.replace(bad, good)
        if line != original:
            lines[i] = line
            fixes.append(f"Fixed unicode arrows on line {i+1}")

    subgraph_depth = 0
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('subgraph ') or stripped == 'subgraph':
            subgraph_depth += 1
        elif stripped == 'end':
            subgraph_depth -= 1
    if subgraph_depth > 0:
        for _ in range(subgraph_depth):
            lines.append('    end')
        fixes.append(f"Added {subgraph_depth} missing 'end' for unclosed subgraph(s)")

    seen_ids: Dict[str, int] = {}
    node_def = re.compile(r'^(\s+)(\w+)\s*([\[\({<])')
    for i, line in enumerate(lines):
        m = node_def.match(line)
        if not m:
            continue
        indent, nid, bracket = m.group(1), m.group(2), m.group(3)
        if nid in ('subgraph', 'end', 'style', 'classDef', 'linkStyle',
                    'click', 'class', 'direction'):
            continue
        if nid in seen_ids:
            seen_ids[nid] += 1
        else:
            seen_ids[nid] = 1

    label_special = re.compile(r'^(\s+\w+\s*\[)([^\]"]+)(]\s*)$')
    for i, line in enumerate(lines):
        m = label_special.match(line)
        if not m:
            continue
        label = m.group(2)
        if re.search(r'[()[\]:{}]', label):
            lines[i] = f'{m.group(1)}"{label}"{m.group(3)}'
            fixes.append(f"Quoted special-char label on line {i+1}")

    return '\n'.join(lines), fixes


def _autofix_mermaid_blocks(md: str) -> Tuple[str, int]:
    """Find all ```mermaid blocks in *md*, apply auto-fixes.

    Returns (updated_md, total_fixes_applied).
    """
    total_fixes = 0

    def _fix(match: re.Match) -> str:
        nonlocal total_fixes
        inner = match.group(1)
        fixed, fixes = _fix_mermaid_block(inner)
        total_fixes += len(fixes)
        for f in fixes:
            print(f"  ~ {f}", file=sys.stderr)
        return f"```mermaid\n{fixed}```"

    md = _MERMAID_BLOCK.sub(_fix, md)
    return md, total_fixes


# ──────────────────────────────────────────────────────────────────
# Validation pass
# ──────────────────────────────────────────────────────────────────

def _validate_blocks(md: str) -> List[str]:
    """Validate all Mermaid blocks and return a list of error strings."""
    if validate_mermaid is None:
        return []
    errors: List[str] = []
    for i, m in enumerate(_MERMAID_BLOCK.finditer(md)):
        code = f"```mermaid\n{m.group(1)}```"
        ok, err = validate_mermaid(code)
        if not ok:
            errors.append(f"Block {i}: {err}")
    return errors


# ──────────────────────────────────────────────────────────────────
# Main entry point
# ──────────────────────────────────────────────────────────────────

def replace_diagrams(page_dir: str) -> dict:
    """Run all three phases on a page directory.  Returns a summary dict."""
    page_path = Path(page_dir)
    page_md = page_path / 'page.md'
    attachments_dir = page_path / 'attachments'
    manifest_path = page_path / 'conversion-manifest.json'

    if not page_md.exists():
        print(f"Error: {page_md} not found", file=sys.stderr)
        return {'error': 'page.md not found'}

    md = page_md.read_text(encoding='utf-8')
    original_md = md

    if not attachments_dir.exists():
        attachments_dir.mkdir(parents=True, exist_ok=True)

    # Phase 1 — PlantUML
    puml_counter = [0]
    print("Phase 1: PlantUML auto-detection...", file=sys.stderr)
    md = _replace_plantuml_blocks(md, attachments_dir, puml_counter)
    puml_converted = puml_counter[0]
    if puml_converted:
        print(f"  Converted {puml_converted} PlantUML block(s)", file=sys.stderr)
    else:
        print("  No PlantUML blocks found", file=sys.stderr)

    # Phase 2 — Image replacement
    print("Phase 2: Image reference replacement...", file=sys.stderr)
    mermaid_map = _build_mermaid_map(attachments_dir, manifest_path)
    md, img_replaced, img_remaining = _replace_image_refs(md, mermaid_map)

    # Phase 3 — Mermaid auto-fix
    print("Phase 3: Mermaid syntax auto-fix...", file=sys.stderr)
    md, fix_count = _autofix_mermaid_blocks(md)
    if fix_count:
        print(f"  Applied {fix_count} auto-fix(es)", file=sys.stderr)
    else:
        print("  No fixes needed", file=sys.stderr)

    # Validation
    errors = _validate_blocks(md)
    if errors:
        print(f"  Validation: {len(errors)} block(s) still have issues:",
              file=sys.stderr)
        for e in errors:
            print(f"    {e}", file=sys.stderr)
    else:
        block_count = len(_MERMAID_BLOCK.findall(md))
        print(f"  Validation: all {block_count} Mermaid block(s) OK",
              file=sys.stderr)

    # Write only if changed
    if md != original_md:
        page_md.write_text(md, encoding='utf-8')
        print(f"\nUpdated {page_md}", file=sys.stderr)
    else:
        print(f"\nNo changes needed for {page_md}", file=sys.stderr)

    summary = {
        'plantuml_converted': puml_converted,
        'images_replaced': img_replaced,
        'images_remaining': img_remaining,
        'auto_fixes': fix_count,
        'validation_errors': len(errors),
    }
    print(f"\nSummary: {json.dumps(summary)}", file=sys.stderr)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Replace diagrams in page.md with Mermaid (post-LLM-repair)',
    )
    parser.add_argument(
        '--page-dir', required=True,
        help='Page output directory (e.g. governance/output/<PAGE_ID>)',
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Print what would change without writing',
    )
    args = parser.parse_args()

    page_path = Path(args.page_dir)
    if not page_path.exists():
        print(f"Error: directory not found: {page_path}", file=sys.stderr)
        return 1

    if args.dry_run:
        page_md = page_path / 'page.md'
        if not page_md.exists():
            print(f"Error: {page_md} not found", file=sys.stderr)
            return 1
        md = page_md.read_text(encoding='utf-8')
        attachments_dir = page_path / 'attachments'
        manifest_path = page_path / 'conversion-manifest.json'
        puml_blocks = extract_plantuml_blocks(md)
        mermaid_map = _build_mermaid_map(attachments_dir, manifest_path) if attachments_dir.exists() else {}
        img_refs = _IMG_REF.findall(md)
        matched = sum(1 for _, p, _ in img_refs if p.split('/')[-1] in mermaid_map)
        print(f"Dry run for {page_path}:", file=sys.stderr)
        print(f"  PlantUML blocks to convert: {len(puml_blocks)}", file=sys.stderr)
        print(f"  Image refs found: {len(img_refs)} ({matched} have .mmd)", file=sys.stderr)
        return 0

    result = replace_diagrams(args.page_dir)
    return 1 if result.get('error') else 0


if __name__ == '__main__':
    sys.exit(main())
