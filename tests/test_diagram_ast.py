"""Tests for ingest/diagram_ast.py — shared schema, ID generation, inference, tables."""
import pytest
from ingest.diagram_ast import (
    DiagramAST, DiagramNode, DiagramEdge, DiagramGroup,
    make_readable_id, infer_node_role, infer_secondary_role,
    infer_edge_protocol, infer_edge_protocols, infer_zone_type,
    enrich_ast, ast_to_markdown_tables, to_json, from_json,
)


class TestMakeReadableId:
    def test_basic_label(self):
        used = set()
        assert make_readable_id("API Gateway", used) == "api_gateway"

    def test_deduplication(self):
        used = set()
        assert make_readable_id("API Gateway", used) == "api_gateway"
        assert make_readable_id("API Gateway", used) == "api_gateway_2"
        assert make_readable_id("API Gateway", used) == "api_gateway_3"

    def test_special_chars(self):
        used = set()
        assert make_readable_id("PostgreSQL DB (Primary)", used) == "postgresql_db_primary"

    def test_truncation(self):
        used = set()
        result = make_readable_id("A" * 50, used)
        assert len(result) <= 30

    def test_numeric_prefix(self):
        used = set()
        result = make_readable_id("123 Service", used)
        assert result.startswith("n_")

    def test_empty_label(self):
        used = set()
        result = make_readable_id("", used)
        assert result.startswith("n_")


class TestInferEdgeProtocols:
    def test_single_protocol(self):
        assert infer_edge_protocols("HTTPS") == ["HTTPS"]

    def test_multi_protocol(self):
        result = infer_edge_protocols("gRPC over mTLS")
        assert "mTLS" in result
        assert "gRPC" in result

    def test_empty(self):
        assert infer_edge_protocols("") == []

    def test_no_match(self):
        assert infer_edge_protocols("some label") == []


class TestInferNodeRole:
    def test_database_shape(self):
        assert infer_node_role("Any", "database") == "datastore"

    def test_gateway(self):
        assert infer_node_role("API Gateway", "rectangle") == "gateway"

    def test_firewall(self):
        assert infer_node_role("WAF Firewall", "rectangle") == "firewall"

    def test_monitoring(self):
        assert infer_node_role("Prometheus Monitoring", "rectangle") == "monitoring"

    def test_auth_service(self):
        assert infer_node_role("Auth0 Identity", "rectangle") == "auth_service"

    def test_cdn(self):
        assert infer_node_role("CloudFront CDN", "rectangle") == "cdn"

    def test_ci_cd(self):
        assert infer_node_role("Jenkins Pipeline", "rectangle") == "ci_cd"

    def test_default_service(self):
        assert infer_node_role("My App", "rectangle") == "service"


class TestSecondaryRole:
    def test_gateway_cache(self):
        assert infer_secondary_role("API Gateway Cache", "gateway") == "cache"

    def test_no_secondary(self):
        assert infer_secondary_role("Load Balancer", "load_balancer") == ""


class TestEnrichAst:
    def test_enriches_roles_and_protocols(self):
        ast = DiagramAST(
            nodes=[DiagramNode(id="gw", label="API Gateway", shape="rectangle")],
            edges=[DiagramEdge(id="e1", source="a", target="b", label="HTTPS call")],
        )
        enrich_ast(ast)
        assert ast.nodes[0].role == "gateway"
        assert ast.edges[0].protocol == "HTTPS"
        assert "HTTPS" in ast.edges[0].protocols


class TestMarkdownTables:
    def test_human_readable_output(self):
        ast = DiagramAST(
            nodes=[
                DiagramNode(id="api_gw", label="API Gateway", role="gateway", shape="rectangle", parent_group="vpc"),
                DiagramNode(id="db", label="PostgreSQL", role="datastore", shape="database"),
            ],
            edges=[
                DiagramEdge(id="e1", source="api_gw", target="db", label="JDBC", protocol="JDBC"),
            ],
            groups=[
                DiagramGroup(id="vpc", label="Cloud VPC", children=["api_gw"], zone_type="cloud"),
            ],
        )
        md = ast_to_markdown_tables(ast, "test.drawio")

        assert "| From | To |" in md
        assert "API Gateway" in md
        assert "PostgreSQL" in md
        assert "| Group | Zone | Contains |" in md
        assert "Cloud VPC" in md
        assert "| ID | Label | Role | Shape | Group |" in md


class TestJsonSerialization:
    def test_roundtrip(self):
        ast = DiagramAST(
            nodes=[DiagramNode(id="n1", label="Node 1", confidence=0.9, secondary_role="cache")],
            edges=[DiagramEdge(id="e1", source="n1", target="n1", protocols=["HTTPS", "gRPC"], confidence=0.8)],
            groups=[DiagramGroup(id="g1", label="Group 1", confidence=0.7)],
        )
        data = to_json(ast)
        restored = from_json(data)
        assert restored.nodes[0].id == "n1"
        assert restored.edges[0].source == "n1"
        assert restored.groups[0].label == "Group 1"
