#!/usr/bin/env python3
"""
Thin helper for LLM page claims extraction.

Provides deterministic AST facts extraction, staleness checking, and JSON
schema validation for page-claims.json.

Does NOT call any LLM API — the governance-agent performs claims extraction
using its own LLM capability via the extract-claims skill.
"""

import hashlib
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from ingest.diagram_ast import load_ast


def _fingerprint(path: Path) -> str:
    """MD5 fingerprint of the first 64KB of a file."""
    data = path.read_bytes()[:65536]
    return hashlib.md5(data).hexdigest()[:12]


def extract_ast_facts(page_dir: Path) -> Dict[str, Any]:
    """Extract deterministic facts from all AST files in a page directory.

    Returns protocol counts, role counts, zone counts — pure Python, no LLM.
    """
    protocols: Counter = Counter()
    roles: Counter = Counter()
    zones: Counter = Counter()

    ast_files = list(page_dir.glob("*.ast.json")) + \
                list((page_dir / "attachments").glob("*.ast.json"))

    for ast_path in ast_files:
        try:
            ast = load_ast(str(ast_path))
        except Exception:
            continue

        for edge in ast.edges:
            if edge.protocols:
                for p in edge.protocols:
                    protocols[p] += 1
            elif edge.protocol:
                protocols[edge.protocol] += 1

        for node in ast.nodes:
            if node.role:
                roles[node.role] += 1

        for group in ast.groups:
            if group.zone_type:
                zones[group.zone_type] += 1

    return {
        "protocols": dict(protocols),
        "roles": dict(roles),
        "zones": dict(zones),
    }


def check_staleness(page_id: str, output_dir: str = "governance/output") -> Dict[str, Any]:
    """Check if page-claims.json is current relative to page.md."""
    page_dir = Path(output_dir) / page_id
    page_md = page_dir / "page.md"
    claims_json = page_dir / "page-claims.json"

    if not page_md.exists():
        return {"stale": False, "reason": "no page.md found", "page_exists": False}

    current_fp = _fingerprint(page_md)

    if not claims_json.exists():
        return {
            "stale": True,
            "reason": "page-claims.json does not exist",
            "current_fingerprint": current_fp,
            "stored_fingerprint": None,
            "page_exists": True,
        }

    try:
        data = json.loads(claims_json.read_text(encoding="utf-8"))
        stored_fp = data.get("fingerprint", "")
    except (json.JSONDecodeError, IOError):
        stored_fp = ""

    if current_fp != stored_fp:
        return {
            "stale": True,
            "reason": "fingerprint mismatch — page changed since last extraction",
            "current_fingerprint": current_fp,
            "stored_fingerprint": stored_fp,
            "page_exists": True,
        }

    return {
        "stale": False,
        "reason": "claims are current",
        "current_fingerprint": current_fp,
        "stored_fingerprint": stored_fp,
        "extracted_at": data.get("extracted_at"),
        "page_exists": True,
    }


def claims_schema_template(page_id: str) -> Dict[str, Any]:
    """Return the JSON schema template for page-claims.json."""
    return {
        "page_id": page_id,
        "fingerprint": "<md5 of page.md>",
        "extracted_at": datetime.now().isoformat(),
        "claims": [
            {
                "topic": "example_topic",
                "rule_ids": [],
                "status": "implemented|deferred|absent|mentioned",
                "method": None,
                "evidence_line": None,
                "section": None,
                "quote": None,
            }
        ],
        "ast_facts": {"protocols": {}, "roles": {}, "zones": {}},
        "contradictions": [],
    }


def validate_claims(data: Dict[str, Any]) -> List[str]:
    """Validate the structure of a page-claims.json. Returns list of errors."""
    errors: List[str] = []
    if "page_id" not in data:
        errors.append("missing 'page_id' field")
    if "fingerprint" not in data:
        errors.append("missing 'fingerprint' field")
    if "claims" not in data or not isinstance(data.get("claims"), list):
        errors.append("missing or invalid 'claims' array")
    else:
        valid_statuses = {"implemented", "deferred", "absent", "mentioned"}
        for i, claim in enumerate(data["claims"]):
            if "topic" not in claim:
                errors.append(f"claims[{i}]: missing 'topic'")
            status = claim.get("status", "")
            if status not in valid_statuses:
                errors.append(f"claims[{i}]: invalid status '{status}'")
    return errors


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Page claims extraction helper")
    parser.add_argument("--check", action="store_true", help="Check if claims are stale")
    parser.add_argument("--facts", action="store_true", help="Extract AST facts (deterministic)")
    parser.add_argument("--page-id", "-p", help="Page ID (required for --check, --facts)")
    parser.add_argument("--schema", action="store_true", help="Print JSON schema template")
    parser.add_argument("--validate", help="Validate an existing page-claims.json")
    args = parser.parse_args()

    if args.schema:
        page_id = args.page_id or "EXAMPLE"
        print(json.dumps(claims_schema_template(page_id), indent=2))
        return 0

    if args.validate:
        data = json.loads(Path(args.validate).read_text(encoding="utf-8"))
        errs = validate_claims(data)
        if errs:
            for e in errs:
                print(f"  ERROR: {e}", file=sys.stderr)
            return 1
        print("  Valid", file=sys.stderr)
        return 0

    if not args.page_id:
        parser.error("--page-id is required for --check and --facts")

    if args.facts:
        page_dir = Path("governance/output") / args.page_id
        facts = extract_ast_facts(page_dir)
        print(json.dumps(facts, indent=2))
        return 0

    if args.check:
        result = check_staleness(args.page_id)
        print(json.dumps(result, indent=2))
        return 1 if result.get("stale") else 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
