#!/usr/bin/env python3
"""
Thin helper for LLM rule enrichment.

Provides staleness checking and JSON schema validation for rules-enriched.json.
Does NOT call any LLM API — the governance-agent performs enrichment using its
own LLM capability via the enrich-rules skill.
"""

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


def _fingerprint(path: Path) -> str:
    """MD5 fingerprint of the first 64KB of a file."""
    data = path.read_bytes()[:65536]
    return hashlib.md5(data).hexdigest()[:12]


def check_staleness(index_dir: Path) -> Dict[str, Any]:
    """Check if rules-enriched.json is current relative to _all.rules.md.

    Returns dict with 'stale' bool, current and stored fingerprints.
    """
    rules_md = index_dir / "_all.rules.md"
    enriched_json = index_dir / "rules-enriched.json"

    if not rules_md.exists():
        return {"stale": False, "reason": "no _all.rules.md found", "rules_exist": False}

    current_fp = _fingerprint(rules_md)

    if not enriched_json.exists():
        return {
            "stale": True,
            "reason": "rules-enriched.json does not exist",
            "current_fingerprint": current_fp,
            "stored_fingerprint": None,
            "rules_exist": True,
        }

    try:
        data = json.loads(enriched_json.read_text(encoding="utf-8"))
        stored_fp = data.get("fingerprint", "")
    except (json.JSONDecodeError, IOError):
        stored_fp = ""

    if current_fp != stored_fp:
        return {
            "stale": True,
            "reason": "fingerprint mismatch — rules changed since last enrichment",
            "current_fingerprint": current_fp,
            "stored_fingerprint": stored_fp,
            "rules_exist": True,
        }

    return {
        "stale": False,
        "reason": "enrichment is current",
        "current_fingerprint": current_fp,
        "stored_fingerprint": stored_fp,
        "enriched_at": data.get("enriched_at"),
        "rules_exist": True,
    }


def enrichment_schema_template() -> Dict[str, Any]:
    """Return the JSON schema template for rules-enriched.json."""
    return {
        "fingerprint": "<md5 of _all.rules.md>",
        "category": "<index category>",
        "enriched_at": datetime.now().isoformat(),
        "rules": [
            {
                "rule_id": "R-PROTO-xxxxxx",
                "rule_name": "Example rule",
                "synonyms": [],
                "evidence_patterns": [],
                "negation_patterns": [],
                "deferral_patterns": [],
                "section_hints": [],
                "co_occurrence_groups": [],
            }
        ],
    }


def validate_enrichment(data: Dict[str, Any]) -> list:
    """Validate the structure of a rules-enriched.json. Returns list of errors."""
    errors = []
    if "fingerprint" not in data:
        errors.append("missing 'fingerprint' field")
    if "rules" not in data or not isinstance(data.get("rules"), list):
        errors.append("missing or invalid 'rules' array")
    else:
        for i, rule in enumerate(data["rules"]):
            if "rule_id" not in rule:
                errors.append(f"rules[{i}]: missing 'rule_id'")
            for field in ("synonyms", "evidence_patterns", "negation_patterns"):
                if field not in rule or not isinstance(rule.get(field), list):
                    errors.append(f"rules[{i}]: missing or invalid '{field}'")
    return errors


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Rule enrichment helper")
    parser.add_argument("--check", action="store_true", help="Check if enrichment is stale")
    parser.add_argument("--index", "-i", required=True, help="Index name (security, patterns, standards)")
    parser.add_argument("--schema", action="store_true", help="Print JSON schema template")
    parser.add_argument("--validate", help="Validate an existing rules-enriched.json")
    args = parser.parse_args()

    index_dir = Path("governance/indexes") / args.index

    if args.schema:
        print(json.dumps(enrichment_schema_template(), indent=2))
        return 0

    if args.validate:
        data = json.loads(Path(args.validate).read_text(encoding="utf-8"))
        errs = validate_enrichment(data)
        if errs:
            for e in errs:
                print(f"  ERROR: {e}", file=sys.stderr)
            return 1
        print("  Valid", file=sys.stderr)
        return 0

    if args.check:
        result = check_staleness(index_dir)
        print(json.dumps(result, indent=2))
        return 1 if result.get("stale") else 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
