"""Tests for ingest/extract_rules.py — rule extraction with stable IDs."""
import pytest
import tempfile
from pathlib import Path

from ingest.diagram_ast import DiagramAST, DiagramNode, DiagramEdge, DiagramGroup
from ingest.extract_rules import (
    extract_rules_from_ast, _make_rule_id, _derive_data_flow_rules,
    _derive_resilience_rules, _derive_fanout_rules, _derive_cross_diagram_rules,
    write_rules_md,
)


@pytest.fixture
def sample_ast():
    return DiagramAST(
        nodes=[
            DiagramNode(id="gw", label="API Gateway", role="gateway", shape="rectangle", confidence=1.0),
            DiagramNode(id="svc", label="User Service", role="service", shape="rectangle", confidence=1.0),
            DiagramNode(id="db", label="PostgreSQL", role="datastore", shape="database", confidence=1.0),
            DiagramNode(id="ext", label="External API", role="external", shape="rectangle", confidence=1.0),
            DiagramNode(id="cache", label="Redis", role="cache", shape="rectangle", confidence=1.0),
        ],
        edges=[
            DiagramEdge(id="e1", source="ext", target="gw", label="HTTPS", protocol="HTTPS", confidence=1.0),
            DiagramEdge(id="e2", source="gw", target="svc", label="gRPC", protocol="gRPC", confidence=1.0),
            DiagramEdge(id="e3", source="svc", target="db", label="JDBC", protocol="JDBC", confidence=1.0),
            DiagramEdge(id="e4", source="svc", target="cache", label="", confidence=1.0),
        ],
        groups=[
            DiagramGroup(id="ext_zone", label="External", zone_type="external", children=["ext"], confidence=1.0),
            DiagramGroup(id="int_zone", label="Internal VPC", zone_type="internal", children=["gw", "svc", "db", "cache"], confidence=1.0),
        ],
    )


class TestStableRuleIds:
    def test_deterministic(self):
        id1 = _make_rule_id("protocol", "Secure transport", "edge.protocol IN (HTTPS)")
        id2 = _make_rule_id("protocol", "Secure transport", "edge.protocol IN (HTTPS)")
        assert id1 == id2

    def test_format(self):
        rid = _make_rule_id("protocol", "Secure transport", "edge.protocol IN (HTTPS)")
        assert rid.startswith("R-PROTO-")
        assert len(rid) == len("R-PROTO-") + 6

    def test_different_content_different_id(self):
        id1 = _make_rule_id("protocol", "Secure transport", "condition A")
        id2 = _make_rule_id("protocol", "Insecure transport", "condition B")
        assert id1 != id2

    def test_same_rules_same_ids_across_runs(self, sample_ast):
        rules1 = extract_rules_from_ast(sample_ast)
        rules2 = extract_rules_from_ast(sample_ast)
        names1 = [(r["rule"], r.get("ast_condition")) for r in rules1]
        names2 = [(r["rule"], r.get("ast_condition")) for r in rules2]
        assert names1 == names2


class TestNewRuleCategories:
    def test_data_flow_rules(self, sample_ast):
        rules = _derive_data_flow_rules(sample_ast.edges, sample_ast.nodes, sample_ast.groups)
        assert isinstance(rules, list)

    def test_resilience_rules(self, sample_ast):
        rules = _derive_resilience_rules(sample_ast.edges, sample_ast.nodes)
        assert isinstance(rules, list)

    def test_fanout_rules(self, sample_ast):
        rules = _derive_fanout_rules(sample_ast.edges, sample_ast.nodes)
        assert isinstance(rules, list)


class TestCrossDiagram:
    def test_conflicting_roles(self):
        ast1 = DiagramAST(nodes=[DiagramNode(id="redis", label="Redis", role="cache", confidence=1.0)])
        ast2 = DiagramAST(nodes=[DiagramNode(id="redis", label="Redis", role="datastore", confidence=1.0)])
        rules = _derive_cross_diagram_rules([ast1, ast2])
        assert len(rules) >= 1
        assert "conflicting" in rules[0]["rule"].lower()

    def test_no_conflict_with_single_ast(self):
        ast = DiagramAST(nodes=[DiagramNode(id="n1", label="Node", role="service")])
        rules = _derive_cross_diagram_rules([ast])
        assert len(rules) == 0


class TestConfidencePropagation:
    def test_rules_have_confidence(self, sample_ast):
        rules = extract_rules_from_ast(sample_ast)
        for r in rules:
            assert "confidence" in r
            assert 0.0 <= r["confidence"] <= 1.0


class TestWriteRulesMd:
    def test_writes_with_stable_ids(self, sample_ast):
        rules = extract_rules_from_ast(sample_ast)
        with tempfile.TemporaryDirectory() as tmpdir:
            page_dir = Path(tmpdir)
            (page_dir / "page.md").write_text("# Test")
            path = write_rules_md(rules, "test_page", page_dir, "security")
            content = path.read_text()
            assert "| ID |" in content
            assert "| Conf |" in content
            assert "R-" in content
