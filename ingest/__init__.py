"""Deterministic Confluence ingestion pipeline.

Converts Draw.io, SVG, and PlantUML diagrams to canonical DiagramAST JSON
and embeds them as markdown tables in page.md files. Zero LLM.

In index mode, also extracts structural governance rules from AST data
and produces per-page rules.md + consolidated _all.rules.md.
"""

from ingest.confluence_ingest import ingest_page, post_report_to_confluence
from ingest.extract_rules import extract_and_write_rules, extract_rules_from_ast

__all__ = [
    "ingest_page",
    "post_report_to_confluence",
    "extract_and_write_rules",
    "extract_rules_from_ast",
]
