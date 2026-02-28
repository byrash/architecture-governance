#!/usr/bin/env python3
"""
Deterministic scoring engine for governance rules.

Pure Python — zero LLM. Matches enriched rules against page claims and AST
facts to produce pre-score.json with per-rule status and deterministic scores.

Scoring priority chain per rule:
  1. AST condition (strongest) -> CONFIRMED_PASS or CONFIRMED_ERROR
  2. Page claim (LLM-extracted, cached) -> STRONG_PASS, DEFERRED_ERROR, ABSENT_ERROR, WEAK_EVIDENCE
  3. Enriched pattern matching (regex on text) -> PATTERN_PASS, NEGATION_ERROR, etc.
  4. Cross-validation: AST contradicts claim -> CONTRADICTION
  5. No evidence -> ABSENT_ERROR

Locked statuses (LLM cannot override): CONFIRMED_PASS, STRONG_PASS, PATTERN_PASS,
CO_OCCUR_PASS, CONFIRMED_ERROR, ABSENT_ERROR, NEGATION_ERROR, DEFERRED_ERROR

Unlocked statuses (LLM may re-evaluate): WEAK_EVIDENCE, CONTRADICTION
"""

import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# Status constants and their score contributions
STATUS_SCORES = {
    "CONFIRMED_PASS": 100,
    "STRONG_PASS": 95,
    "PATTERN_PASS": 85,
    "CO_OCCUR_PASS": 80,
    "WEAK_EVIDENCE": 50,
    "CONTRADICTION": 40,
    "DEFERRED_ERROR": 20,
    "NEGATION_ERROR": 10,
    "ABSENT_ERROR": 0,
    "CONFIRMED_ERROR": 0,
}

LOCKED_STATUSES = {
    "CONFIRMED_PASS", "STRONG_PASS", "PATTERN_PASS", "CO_OCCUR_PASS",
    "CONFIRMED_ERROR", "ABSENT_ERROR", "NEGATION_ERROR", "DEFERRED_ERROR",
}


def _fingerprint(path: Path) -> str:
    data = path.read_bytes()[:65536]
    return hashlib.md5(data).hexdigest()[:12]


def _load_enriched_rules(index_dir: Path) -> Optional[Dict[str, Any]]:
    """Load rules-enriched.json if it exists and is current."""
    path = index_dir / "rules-enriched.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return None


def _load_page_claims(page_dir: Path) -> Optional[Dict[str, Any]]:
    """Load page-claims.json if it exists."""
    path = page_dir / "page-claims.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return None


def _load_page_text(page_dir: Path) -> str:
    """Load page.md content for pattern matching."""
    path = page_dir / "page.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def _parse_rules_from_md(rules_md: Path) -> List[Dict[str, Any]]:
    """Parse rules from _all.rules.md."""
    rules: List[Dict[str, Any]] = []
    in_table = False
    for line in rules_md.read_text(encoding="utf-8").split("\n"):
        if line.startswith("| ID") or line.startswith("|-"):
            in_table = True
            continue
        if in_table and line.startswith("|"):
            cols = [c.strip() for c in line.split("|")[1:-1]]
            if len(cols) >= 7:
                r: Dict[str, Any] = {
                    "id": cols[0],
                    "rule": cols[1],
                    "sev": cols[2],
                    "req": cols[3],
                    "keywords": cols[4],
                    "condition": cols[5],
                    "ast_condition": cols[6] if len(cols) > 6 else "",
                }
                if len(cols) >= 8:
                    try:
                        r["confidence"] = float(cols[7])
                    except ValueError:
                        r["confidence"] = 1.0
                else:
                    r["confidence"] = 1.0
                rules.append(r)
        elif in_table and not line.startswith("|"):
            in_table = False
    return rules


def _evaluate_ast_condition(ast_cond: str, ast_facts: Dict[str, Any]) -> Optional[str]:
    """Evaluate an AST condition against extracted AST facts.

    Returns CONFIRMED_PASS, CONFIRMED_ERROR, or None (inconclusive).
    """
    if not ast_cond:
        return None

    protocols = ast_facts.get("protocols", {})
    roles = ast_facts.get("roles", {})
    zones = ast_facts.get("zones", {})

    m = re.match(r"edge\.protocol\s+IN\s+\(([^)]+)\)", ast_cond)
    if m:
        expected = {p.strip() for p in m.group(1).split(",")}
        found = set(protocols.keys())
        if expected & found:
            return "CONFIRMED_PASS"
        return None

    m = re.match(r"edge\.protocol\s*==\s*(\w+)", ast_cond)
    if m:
        proto = m.group(1)
        if proto in protocols:
            return "CONFIRMED_PASS"
        return None

    m = re.match(r"node\.role\s*==\s*(\w+)", ast_cond)
    if m:
        role = m.group(1)
        if role in roles and roles[role] > 0:
            return "CONFIRMED_PASS"
        return None

    m = re.match(r"group\.zone_type\s+IN\s+\(([^)]+)\)", ast_cond)
    if m:
        expected = {z.strip() for z in m.group(1).split(",")}
        found = set(zones.keys())
        if expected <= found:
            return "CONFIRMED_PASS"
        return None

    m = re.match(r"group\.zone_type\s*==\s*(\w+)", ast_cond)
    if m:
        zone = m.group(1)
        if zone in zones and zones[zone] > 0:
            return "CONFIRMED_PASS"
        return None

    if "NOT edge(" in ast_cond:
        return "CONFIRMED_PASS"

    if "edge(" in ast_cond and "EXISTS" in ast_cond:
        return "CONFIRMED_ERROR"

    return None


def _match_claim(rule: Dict[str, Any], claims: List[Dict[str, Any]]) -> Optional[Tuple[str, Dict]]:
    """Match a rule against page claims. Returns (status, claim) or None."""
    rule_id = rule.get("id", "")
    rule_name = rule.get("rule", "").lower()
    rule_keywords = {k.strip().lower() for k in rule.get("keywords", "").split(",")}

    for claim in claims:
        topic = claim.get("topic", "").lower()
        topic_normalized = topic.replace("_", " ")
        claim_rule_ids = claim.get("rule_ids", [])

        matched = False
        if rule_id in claim_rule_ids:
            matched = True
        elif topic and any(kw in topic or kw in topic_normalized or topic in kw or topic_normalized in kw for kw in rule_keywords if kw):
            matched = True
        elif topic and (topic in rule_name or topic_normalized in rule_name):
            matched = True

        if matched:
            status = claim.get("status", "absent")
            if status == "implemented":
                return "STRONG_PASS", claim
            elif status == "deferred":
                return "DEFERRED_ERROR", claim
            elif status == "absent":
                return "ABSENT_ERROR", claim
            elif status == "mentioned":
                return "WEAK_EVIDENCE", claim

    return None


def _match_enriched_patterns(
    rule: Dict[str, Any],
    enriched_rule: Optional[Dict[str, Any]],
    page_text: str,
) -> Optional[str]:
    """Match enriched patterns against page text. Returns status or None."""
    if not enriched_rule or not page_text:
        return None

    negation_patterns = enriched_rule.get("negation_patterns", [])
    for pattern in negation_patterns:
        try:
            if re.search(pattern, page_text):
                return "NEGATION_ERROR"
        except re.error:
            continue

    deferral_patterns = enriched_rule.get("deferral_patterns", [])
    for pattern in deferral_patterns:
        try:
            if re.search(pattern, page_text):
                return "DEFERRED_ERROR"
        except re.error:
            continue

    co_groups = enriched_rule.get("co_occurrence_groups", [])
    for group in co_groups:
        if len(group) >= 3:
            hits = sum(1 for term in group if re.search(re.escape(term), page_text, re.IGNORECASE))
            if hits >= len(group):
                return "CO_OCCUR_PASS"

    evidence_patterns = enriched_rule.get("evidence_patterns", [])
    evidence_hits = 0
    for pattern in evidence_patterns:
        try:
            if re.search(pattern, page_text):
                evidence_hits += 1
        except re.error:
            continue
    if evidence_hits >= 2:
        return "PATTERN_PASS"

    synonyms = enriched_rule.get("synonyms", [])
    synonym_hits = sum(
        1 for s in synonyms
        if re.search(re.escape(s), page_text, re.IGNORECASE)
    )
    if synonym_hits >= 1:
        return "WEAK_EVIDENCE"

    return None


def _keyword_match(rule: Dict[str, Any], page_text: str) -> Optional[str]:
    """Fallback keyword matching when no enrichment available."""
    if not page_text:
        return None

    keywords = [k.strip() for k in rule.get("keywords", "").split(",") if k.strip()]
    if not keywords:
        return None

    hits = sum(
        1 for kw in keywords
        if re.search(re.escape(kw), page_text, re.IGNORECASE)
    )

    if hits >= 2:
        return "PATTERN_PASS"
    if hits >= 1:
        return "WEAK_EVIDENCE"
    return None


def score_rules(
    page_id: str,
    output_dir: str = "governance/output",
    indexes_dir: str = "governance/indexes",
    categories: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Run the deterministic scoring engine.

    Scores all rules from all indexes against the page, producing pre-score.json.
    """
    page_dir = Path(output_dir) / page_id
    page_text = _load_page_text(page_dir)
    page_claims_data = _load_page_claims(page_dir)

    claims = page_claims_data.get("claims", []) if page_claims_data else []
    ast_facts = page_claims_data.get("ast_facts", {}) if page_claims_data else {}
    contradictions = page_claims_data.get("contradictions", []) if page_claims_data else []

    if not ast_facts:
        from ingest.extract_claims import extract_ast_facts
        ast_facts = extract_ast_facts(page_dir)

    if categories is None:
        idx_root = Path(indexes_dir)
        categories = [d.name for d in idx_root.iterdir() if d.is_dir()] if idx_root.exists() else []

    all_results: List[Dict[str, Any]] = []
    category_scores: Dict[str, Dict[str, Any]] = {}

    for category in categories:
        index_dir = Path(indexes_dir) / category
        rules_md = index_dir / "_all.rules.md"
        if not rules_md.exists():
            continue

        rules = _parse_rules_from_md(rules_md)
        enriched_data = _load_enriched_rules(index_dir)
        enriched_map: Dict[str, Dict] = {}
        if enriched_data:
            for er in enriched_data.get("rules", []):
                enriched_map[er.get("rule_id", "")] = er

        cat_total = 0
        cat_max = 0
        cat_results: List[Dict[str, Any]] = []

        for rule in rules:
            rule_id = rule["id"]
            enriched_rule = enriched_map.get(rule_id)

            status = _evaluate_ast_condition(rule.get("ast_condition", ""), ast_facts)

            if status is None:
                claim_result = _match_claim(rule, claims)
                if claim_result:
                    status = claim_result[0]

            if status is None:
                status = _match_enriched_patterns(rule, enriched_rule, page_text)

            if status is None:
                status = _keyword_match(rule, page_text)

            if status is None:
                status = "ABSENT_ERROR"

            contradiction_hit = None
            for c in contradictions:
                if rule_id in str(c):
                    contradiction_hit = c
                    if status in ("STRONG_PASS", "PATTERN_PASS", "CO_OCCUR_PASS"):
                        status = "CONTRADICTION"
                    break

            locked = status in LOCKED_STATUSES
            points = STATUS_SCORES.get(status, 0)
            confidence = rule.get("confidence", 1.0)

            sev_weight = {"C": 4, "H": 3, "M": 2, "L": 1}.get(rule.get("sev", "M"), 2)
            weighted_points = points * sev_weight * confidence

            cat_total += weighted_points
            cat_max += 100 * sev_weight * confidence

            result = {
                "rule_id": rule_id,
                "rule_name": rule["rule"],
                "category": category,
                "severity": rule.get("sev", "M"),
                "required": rule.get("req", "N") == "Y",
                "status": status,
                "locked": locked,
                "points": points,
                "confidence": confidence,
                "evidence": None,
            }
            if contradiction_hit:
                result["contradiction"] = contradiction_hit

            cat_results.append(result)
            all_results.append(result)

        cat_score = round((cat_total / cat_max) * 100, 1) if cat_max > 0 else 0
        locked_count = sum(1 for r in cat_results if r["locked"])
        total_count = len(cat_results)

        category_scores[category] = {
            "score": cat_score,
            "rules_total": total_count,
            "rules_locked": locked_count,
            "rules_unlocked": total_count - locked_count,
            "locked_pct": round(locked_count / total_count * 100, 1) if total_count else 0,
        }

    total_points = sum(
        r["points"] * {"C": 4, "H": 3, "M": 2, "L": 1}.get(r["severity"], 2) * r["confidence"]
        for r in all_results
    )
    max_points = sum(
        100 * {"C": 4, "H": 3, "M": 2, "L": 1}.get(r["severity"], 2) * r["confidence"]
        for r in all_results
    )
    overall_score = round((total_points / max_points) * 100, 1) if max_points > 0 else 0

    output = {
        "page_id": page_id,
        "scored_at": datetime.now().isoformat(),
        "overall_score": overall_score,
        "category_scores": category_scores,
        "rules": all_results,
        "stats": {
            "total_rules": len(all_results),
            "locked": sum(1 for r in all_results if r["locked"]),
            "unlocked": sum(1 for r in all_results if not r["locked"]),
        },
    }

    pre_score_path = page_dir / "pre-score.json"
    pre_score_path.parent.mkdir(parents=True, exist_ok=True)
    pre_score_path.write_text(json.dumps(output, indent=2), encoding="utf-8")

    return output


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Deterministic rule scoring engine")
    parser.add_argument("--page-id", "-p", required=True, help="Page ID to score")
    parser.add_argument("--all", action="store_true", help="Score against all index categories")
    parser.add_argument("--category", "-c", action="append", help="Specific category to score against")
    parser.add_argument("--output-dir", default="governance/output", help="Output directory")
    parser.add_argument("--indexes-dir", default="governance/indexes", help="Indexes directory")
    args = parser.parse_args()

    cats = args.category if args.category else None
    result = score_rules(
        args.page_id,
        output_dir=args.output_dir,
        indexes_dir=args.indexes_dir,
        categories=cats,
    )

    print(f"Score: {result['overall_score']}/100", file=sys.stderr)
    print(f"Rules: {result['stats']['total_rules']} "
          f"(locked: {result['stats']['locked']}, unlocked: {result['stats']['unlocked']})",
          file=sys.stderr)

    for cat, cs in result["category_scores"].items():
        print(f"  {cat}: {cs['score']}/100 ({cs['locked_pct']}% locked)", file=sys.stderr)

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
