"""Tests for ingest/drawio_to_ast.py — Draw.io parser with human-readable IDs."""
import pytest
from pathlib import Path

from ingest.drawio_to_ast import convert_drawio_to_ast

FIXTURE = Path(__file__).parent / "fixtures" / "sample.drawio"


@pytest.fixture
def drawio_ast():
    return convert_drawio_to_ast(FIXTURE)


class TestDrawioReadableIds:
    def test_node_ids_are_readable(self, drawio_ast):
        ids = {n.id for n in drawio_ast.nodes}
        for nid in ids:
            assert not nid.startswith("mxCell"), f"Raw mxCell ID found: {nid}"
            assert len(nid) <= 35

    def test_known_labels_produce_expected_ids(self, drawio_ast):
        labels = {n.label: n.id for n in drawio_ast.nodes}
        assert "api_gateway" in labels.get("API Gateway", "")
        assert "postgresql_db" in labels.get("PostgreSQL DB", "")

    def test_edge_references_use_readable_ids(self, drawio_ast):
        node_ids = {n.id for n in drawio_ast.nodes}
        for e in drawio_ast.edges:
            if e.source:
                assert e.source in node_ids or e.source == "", f"Edge source {e.source} not in nodes"

    def test_original_id_preserved(self, drawio_ast):
        for n in drawio_ast.nodes:
            assert "_original_id" in n.metadata, f"Node {n.id} missing _original_id"

    def test_confidence_is_1(self, drawio_ast):
        for n in drawio_ast.nodes:
            assert n.confidence == 1.0
        for e in drawio_ast.edges:
            assert e.confidence == 1.0


class TestDrawioExtraction:
    def test_extracts_nodes(self, drawio_ast):
        assert len(drawio_ast.nodes) >= 5

    def test_extracts_edges(self, drawio_ast):
        assert len(drawio_ast.edges) >= 5

    def test_extracts_groups(self, drawio_ast):
        assert len(drawio_ast.groups) >= 1

    def test_enrichment_applied(self, drawio_ast):
        roles = {n.role for n in drawio_ast.nodes}
        assert "gateway" in roles or "datastore" in roles
