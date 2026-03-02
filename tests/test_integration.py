"""Integration test — full pipeline from diagram to scored output."""
import json
import pytest
import tempfile
from pathlib import Path

from ingest.drawio_to_ast import convert_drawio_to_ast
from ingest.diagram_ast import save_ast, ast_to_markdown_tables, enrich_ast
from ingest.extract_rules import extract_rules_from_ast, write_rules_md, update_all_rules
from ingest.score_rules import score_rules

FIXTURE = Path(__file__).parent / "fixtures" / "sample.drawio"


class TestFullPipeline:
    def test_drawio_to_rules_to_score(self):
        """End-to-end: parse Draw.io -> AST -> rules -> score."""
        ast = convert_drawio_to_ast(FIXTURE)

        assert len(ast.nodes) >= 5
        assert len(ast.edges) >= 5

        for n in ast.nodes:
            assert "_original_id" in n.metadata

        md = ast_to_markdown_tables(ast, "sample.drawio")
        assert "| From | To |" in md
        assert "| Group | Zone | Contains |" in md

        rules = extract_rules_from_ast(ast)
        assert len(rules) >= 3

        for r in rules:
            assert "confidence" in r
            assert "rule" in r
            assert "sev" in r

        with tempfile.TemporaryDirectory() as tmpdir:
            page_dir = Path(tmpdir) / "output" / "test_page"
            page_dir.mkdir(parents=True)
            attach_dir = page_dir / "attachments"
            attach_dir.mkdir()

            page_md_content = f"# Architecture Document\n\n{md}\n"
            (page_dir / "page.md").write_text(page_md_content)
            save_ast(ast, str(attach_dir / "sample.ast.json"))

            idx_dir = Path(tmpdir) / "indexes" / "security"
            idx_dir.mkdir(parents=True)
            page_idx = idx_dir / "test_page"
            page_idx.mkdir()
            (page_idx / "page.md").write_text(page_md_content)

            rules_path = write_rules_md(rules, "test_page", page_idx, "security")
            assert rules_path.exists()
            content = rules_path.read_text()
            assert "R-" in content
            assert "| Conf |" in content

            all_path = update_all_rules(idx_dir, "test_page", rules, "security")
            assert all_path.exists()

            result = score_rules(
                "test_page",
                output_dir=str(Path(tmpdir) / "output"),
                indexes_dir=str(Path(tmpdir) / "indexes"),
            )

            assert "action_summary" in result
            assert "rules" in result
            assert len(result["rules"]) > 0

            for rule in result["rules"]:
                assert "action" in rule
                assert "urgency" in rule

            pre_score_path = page_dir / "pre-score.json"
            assert pre_score_path.exists()

            result2 = score_rules(
                "test_page",
                output_dir=str(Path(tmpdir) / "output"),
                indexes_dir=str(Path(tmpdir) / "indexes"),
            )
            assert result["action_summary"] == result2["action_summary"]
