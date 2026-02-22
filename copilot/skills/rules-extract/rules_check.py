#!/usr/bin/env python3
"""
Rules Staleness Checker

Compares source page.md files against their rules.md derivatives in
<PAGE_ID>/ subfolders. Uses both file modification times and content
fingerprints (MD5 of first 64KB) for reliable change detection.

Usage:
    python rules_check.py --folder governance/indexes/security/
    python rules_check.py --folder governance/indexes/security/ --json
    python rules_check.py --folder governance/indexes/security/ --fix
    python rules_check.py --all

Output:
    Lists stale, missing, and up-to-date .rules.md files.
    --json outputs machine-readable JSON for agent consumption.
    --fix prints the agent command to refresh stale files.
    --all scans all governance/indexes/*/ folders.

Zero external dependencies -- uses only Python 3 standard library.
"""

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class FileStatus:
    source: str                     # path to .md file
    rules_file: Optional[str]       # path to .rules.md (may not exist)
    status: str                     # 'stale', 'missing', 'current', 'orphan'
    reason: str = ""                # human-readable reason
    source_mtime: float = 0.0
    rules_mtime: float = 0.0
    source_fingerprint: str = ""    # MD5 of first 64KB
    rules_fingerprint: str = ""     # fingerprint stored in .rules.md metadata


def compute_fingerprint(filepath: str) -> str:
    """Compute MD5 fingerprint of file content (first 64KB for speed)."""
    try:
        with open(filepath, 'rb') as f:
            content = f.read(65536)
        return hashlib.md5(content).hexdigest()[:12]
    except (IOError, OSError):
        return ""


def extract_stored_fingerprint(rules_path: str) -> str:
    """Extract the source fingerprint stored in a .rules.md metadata line."""
    try:
        with open(rules_path, 'r', encoding='utf-8', errors='ignore') as f:
            # Read first 10 lines looking for metadata
            for _ in range(10):
                line = f.readline()
                if not line:
                    break
                # Look for: > Source: ... | Fingerprint: abc123def456 | ...
                m = re.search(r'Fingerprint:\s*([a-f0-9]{12})', line)
                if m:
                    return m.group(1)
    except (IOError, OSError):
        pass
    return ""


def check_folder(folder: str) -> List[FileStatus]:
    """Check all page.md files in <PAGE_ID>/ subfolders for rules staleness.

    Per-page folder layout:
        <folder>/<PAGE_ID>/page.md   -- source
        <folder>/<PAGE_ID>/rules.md  -- derived
    """
    folder_path = Path(folder)
    if not folder_path.is_dir():
        print(f"Error: {folder} is not a directory", file=sys.stderr)
        return []

    results: List[FileStatus] = []

    # Find all <PAGE_ID>/ subfolders
    subfolders = sorted([
        d for d in folder_path.iterdir()
        if d.is_dir() and not d.name.startswith('.')
    ])

    for subdir in subfolders:
        page_id = subdir.name
        page_md = subdir / 'page.md'
        rules_md = subdir / 'rules.md'

        if not page_md.exists():
            # No page.md - check for orphan rules.md
            if rules_md.exists():
                results.append(FileStatus(
                    source=f'{folder}/{page_id}/page.md (DELETED)',
                    rules_file=str(rules_md),
                    status='orphan',
                    reason='Source page.md was deleted but rules.md remains',
                    rules_mtime=rules_md.stat().st_mtime,
                ))
            # else: empty folder, skip
            continue

        source_mtime = page_md.stat().st_mtime
        source_fp = compute_fingerprint(str(page_md))

        if not rules_md.exists():
            results.append(FileStatus(
                source=str(page_md),
                rules_file=None,
                status='missing',
                reason='No rules.md file exists in subfolder',
                source_mtime=source_mtime,
                source_fingerprint=source_fp,
            ))
            continue

        rules_mtime = rules_md.stat().st_mtime
        stored_fp = extract_stored_fingerprint(str(rules_md))

        # Check staleness
        if source_fp and stored_fp:
            if source_fp != stored_fp:
                results.append(FileStatus(
                    source=str(page_md),
                    rules_file=str(rules_md),
                    status='stale',
                    reason=f'Content changed (fingerprint {stored_fp} → {source_fp})',
                    source_mtime=source_mtime,
                    rules_mtime=rules_mtime,
                    source_fingerprint=source_fp,
                    rules_fingerprint=stored_fp,
                ))
            else:
                results.append(FileStatus(
                    source=str(page_md),
                    rules_file=str(rules_md),
                    status='current',
                    reason='Fingerprint matches',
                    source_mtime=source_mtime,
                    rules_mtime=rules_mtime,
                    source_fingerprint=source_fp,
                    rules_fingerprint=stored_fp,
                ))
        elif source_mtime > rules_mtime:
            results.append(FileStatus(
                source=str(page_md),
                rules_file=str(rules_md),
                status='stale',
                reason='Source newer than rules (no fingerprint to compare)',
                source_mtime=source_mtime,
                rules_mtime=rules_mtime,
                source_fingerprint=source_fp,
            ))
        else:
            results.append(FileStatus(
                source=str(page_md),
                rules_file=str(rules_md),
                status='current',
                reason='Rules file is newer than source',
                source_mtime=source_mtime,
                rules_mtime=rules_mtime,
                source_fingerprint=source_fp,
            ))

    # Check _all.rules.md freshness
    all_rules = folder_path / '_all.rules.md'
    if all_rules.exists():
        all_mtime = all_rules.stat().st_mtime
        any_newer = any(
            r.source_mtime > all_mtime
            for r in results
            if r.status in ('stale', 'missing')
        )
        if any_newer or any(r.status in ('stale', 'missing') for r in results):
            results.append(FileStatus(
                source='(all source files)',
                rules_file=str(all_rules),
                status='stale',
                reason='Per-page rules changed; consolidated file needs regeneration',
                rules_mtime=all_mtime,
            ))
    else:
        if subfolders:
            results.append(FileStatus(
                source='(all source files)',
                rules_file=str(folder_path / '_all.rules.md'),
                status='missing',
                reason='No consolidated _all.rules.md exists',
            ))

    return results


def print_results(results: List[FileStatus], folder: str, as_json: bool = False, fix: bool = False):
    """Print check results."""
    if as_json:
        output = {
            'folder': folder,
            'files': [
                {
                    'source': r.source,
                    'rules_file': r.rules_file,
                    'status': r.status,
                    'reason': r.reason,
                    'source_fingerprint': r.source_fingerprint,
                }
                for r in results
            ],
            'summary': {
                'total': len([r for r in results if r.status != 'stale' or '(all' not in r.source]),
                'stale': len([r for r in results if r.status == 'stale' and '(all' not in r.source]),
                'missing': len([r for r in results if r.status == 'missing' and '(all' not in r.source]),
                'current': len([r for r in results if r.status == 'current']),
                'orphan': len([r for r in results if r.status == 'orphan']),
            }
        }
        print(json.dumps(output, indent=2))
        return

    stale = [r for r in results if r.status == 'stale']
    missing = [r for r in results if r.status == 'missing']
    current = [r for r in results if r.status == 'current']
    orphans = [r for r in results if r.status == 'orphan']

    print(f"📋 Rules Status: {folder}")
    print(f"{'─' * 60}")

    if current:
        for r in current:
            print(f"  ✅ {Path(r.source).name} → up to date")

    if stale:
        print()
        for r in stale:
            src_name = Path(r.source).name if '(all' not in r.source else '_all.rules.md'
            print(f"  ⚠️  {src_name} → STALE ({r.reason})")

    if missing:
        print()
        for r in missing:
            src_name = Path(r.source).name if '(all' not in r.source else '_all.rules.md'
            print(f"  ❌ {src_name} → MISSING rules")

    if orphans:
        print()
        for r in orphans:
            print(f"  🗑️  {Path(r.rules_file).name} → ORPHAN (source deleted)")

    print(f"{'─' * 60}")
    needs_update = len([r for r in stale + missing if '(all' not in r.source])
    total_src = len([r for r in results if r.status != 'orphan' and '(all' not in r.source])
    print(f"  Total: {total_src} | Current: {len(current)} | Need update: {needs_update} | Orphan: {len(orphans)}")

    if fix and (stale or missing):
        stale_files = [
            Path(r.source).parent.name  # PAGE_ID from <folder>/<PAGE_ID>/page.md
            for r in stale + missing
            if '(all' not in r.source and '(DELETED)' not in r.source
        ]
        if stale_files:
            print()
            print("  💡 To refresh stale rules, run in Copilot Chat:")
            print()
            print(f"    @rules-extraction-agent Refresh rules in {folder}")
            print()
            print(f"  Or re-extract the full folder:")
            print()
            print(f"    @rules-extraction-agent Extract rules from {folder}")


def main():
    parser = argparse.ArgumentParser(description="Check rules staleness")
    parser.add_argument("--folder", "-f", help="Folder to check")
    parser.add_argument("--all", action="store_true", help="Check all governance/indexes/*/ folders")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--fix", action="store_true", help="Show commands to fix stale rules")
    args = parser.parse_args()

    if args.all:
        indexes_dir = Path("governance/indexes")
        if not indexes_dir.is_dir():
            print("Error: governance/indexes/ not found", file=sys.stderr)
            sys.exit(1)
        folders = sorted([d for d in indexes_dir.iterdir() if d.is_dir()])
        any_stale = False
        for folder in folders:
            results = check_folder(str(folder))
            if results:
                print_results(results, str(folder), as_json=args.json, fix=args.fix)
                if any(r.status in ('stale', 'missing') for r in results):
                    any_stale = True
                print()
        sys.exit(1 if any_stale else 0)

    if not args.folder:
        parser.error("Either --folder or --all is required")

    results = check_folder(args.folder)
    if not results:
        print(f"No <PAGE_ID>/page.md files found in {args.folder}")
        sys.exit(0)

    print_results(results, args.folder, as_json=args.json, fix=args.fix)

    has_stale = any(r.status in ('stale', 'missing') for r in results)
    sys.exit(1 if has_stale else 0)


if __name__ == "__main__":
    main()
