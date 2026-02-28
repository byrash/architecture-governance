"""Tests for ingest/score_rules.py — deterministic scoring engine."""
import json
import pytest
import tempfile
from pathlib import Path

from ingest.score_rules import (
    _evaluate_ast_condition, _match_claim, _keyword_match,
    STATUS_SCORES, LOCKED_STATUSES, score_rules,
)


class TestAstConditionEvaluation:
    def test_protocol_match(self):
        facts = {"protocols": {"HTTPS": 3}, "roles": {}, "zones": {}}
        result = _evaluate_ast_condition("edge.protocol IN (HTTPS, TLS)", facts)
        assert result == "CONFIRMED_PASS"

    def test_protocol_no_match(self):
        facts = {"protocols": {"gRPC": 1}, "roles": {}, "zones": {}}
        result = _evaluate_ast_condition("edge.protocol == HTTPS", facts)
        assert result is None

    def test_role_match(self):
        facts = {"protocols": {}, "roles": {"gateway": 1}, "zones": {}}
        result = _evaluate_ast_condition("node.role == gateway", facts)
        assert result == "CONFIRMED_PASS"

    def test_zone_match(self):
        facts = {"protocols": {}, "roles": {}, "zones": {"external": 1, "internal": 1}}
        result = _evaluate_ast_condition("group.zone_type IN (external, internal)", facts)
        assert result == "CONFIRMED_PASS"

    def test_empty_condition(self):
        result = _evaluate_ast_condition("", {})
        assert result is None


class TestClaimMatching:
    def test_implemented_claim(self):
        rule = {"id": "R-PROTO-abc123", "rule": "Secure transport", "keywords": "https, tls"}
        claims = [{"topic": "https", "rule_ids": ["R-PROTO-abc123"], "status": "implemented"}]
        result = _match_claim(rule, claims)
        assert result is not None
        assert result[0] == "STRONG_PASS"

    def test_deferred_claim(self):
        rule = {"id": "R-1", "rule": "Rate limiting", "keywords": "rate limit"}
        claims = [{"topic": "rate_limiting", "rule_ids": [], "status": "deferred"}]
        result = _match_claim(rule, claims)
        assert result is not None
        assert result[0] == "DEFERRED_ERROR"

    def test_no_matching_claim(self):
        rule = {"id": "R-1", "rule": "Audit logging", "keywords": "audit, logging"}
        claims = [{"topic": "encryption", "rule_ids": [], "status": "implemented"}]
        result = _match_claim(rule, claims)
        assert result is None


class TestKeywordMatch:
    def test_multiple_keywords_match(self):
        rule = {"keywords": "gateway, api, routing"}
        text = "The system uses an API gateway for routing all requests."
        result = _keyword_match(rule, text)
        assert result == "PATTERN_PASS"

    def test_single_keyword_match(self):
        rule = {"keywords": "gateway, api, routing"}
        text = "The gateway handles traffic."
        result = _keyword_match(rule, text)
        assert result == "WEAK_EVIDENCE"

    def test_no_match(self):
        rule = {"keywords": "gateway, api, routing"}
        text = "Nothing relevant here."
        result = _keyword_match(rule, text)
        assert result is None


class TestLocking:
    def test_locked_statuses(self):
        for status in LOCKED_STATUSES:
            assert status in STATUS_SCORES

    def test_unlocked_statuses(self):
        assert "WEAK_EVIDENCE" not in LOCKED_STATUSES
        assert "CONTRADICTION" not in LOCKED_STATUSES


class TestDeterministicScoring:
    def test_identical_results(self):
        """Run scorer multiple times on same inputs — must be identical."""
        with tempfile.TemporaryDirectory() as tmpdir:
            page_dir = Path(tmpdir) / "output" / "test_page"
            page_dir.mkdir(parents=True)
            idx_dir = Path(tmpdir) / "indexes" / "security"
            idx_dir.mkdir(parents=True)

            (page_dir / "page.md").write_text(
                "# Test\nAll traffic uses HTTPS. The API gateway handles routing.\n"
                "PostgreSQL database stores all data."
            )

            rules_md = idx_dir / "_all.rules.md"
            rules_md.write_text(
                "# Consolidated Rules - security\n\n"
                "## All Rules\n\n"
                "| ID | Rule | Sev | Req | Keywords | Condition | AST Condition | Conf | Source |\n"
                "|----|------|-----|-----|----------|-----------|---------------|------|--------|\n"
                "| R-PROTO-abc123 | Secure transport | C | Y | https, tls | All uses HTTPS | edge.protocol IN (HTTPS) | 1.00 | p1 |\n"
                "| R-ROLE-def456 | Gateway present | H | Y | gateway, api | Gateway exists | node.role == gateway | 1.00 | p1 |\n"
            )

            results = []
            for _ in range(3):
                r = score_rules(
                    "test_page",
                    output_dir=str(Path(tmpdir) / "output"),
                    indexes_dir=str(Path(tmpdir) / "indexes"),
                )
                results.append(r["overall_score"])

            assert results[0] == results[1] == results[2], f"Scores differ: {results}"
