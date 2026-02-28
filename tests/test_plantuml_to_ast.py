"""Tests for ingest/plantuml_to_ast.py — PlantUML parser."""
import pytest
from pathlib import Path

from ingest.plantuml_to_ast import convert_plantuml_to_ast, detect_diagram_type

FIXTURE = Path(__file__).parent / "fixtures" / "sample.puml"


@pytest.fixture
def puml_ast():
    content = FIXTURE.read_text(encoding="utf-8")
    inner = content.replace("@startuml", "").replace("@enduml", "").strip()
    return convert_plantuml_to_ast(inner)


class TestPlantUMLParsing:
    def test_detects_component_type(self):
        content = FIXTURE.read_text(encoding="utf-8")
        assert detect_diagram_type(content) == "component"

    def test_extracts_nodes(self, puml_ast):
        assert len(puml_ast.nodes) >= 5

    def test_extracts_edges(self, puml_ast):
        assert len(puml_ast.edges) >= 5

    def test_extracts_groups(self, puml_ast):
        assert len(puml_ast.groups) >= 2

    def test_confidence_is_085(self, puml_ast):
        for n in puml_ast.nodes:
            assert n.confidence == 0.85


class TestPlantUMLBoxGroups:
    def test_box_group_parsing(self):
        content = '''
        package "System" {
          box "Frontend" #LightBlue
            component "Web App" as web
            component "Mobile" as mob
          end box
          component "Backend" as be
        }
        web --> be : HTTPS
        mob --> be : HTTPS
        '''
        ast = convert_plantuml_to_ast(content)
        group_labels = {g.label for g in ast.groups}
        assert "Frontend" in group_labels

    def test_together_group_parsing(self):
        content = '''
        package "Services" {
          component "A" as a
          component "B" as b
        }
        a --> b : call
        '''
        ast = convert_plantuml_to_ast(content)
        assert len(ast.groups) >= 1


class TestPlantUMLEnrichment:
    def test_roles_enriched(self, puml_ast):
        roles = {n.role for n in puml_ast.nodes}
        assert "gateway" in roles or "datastore" in roles or "service" in roles
