---
name: standards-validate
category: standards
description: Validate architecture document against standards from the index. Use when asked to check standards, validate naming conventions, or verify documentation compliance.
---

# Standards Validation

Validate architecture document against all standards documents in the index.

## Inputs

1. **Document**: `governance/output/<PAGE_ID>/page.md` (provided by agent)
2. **Index**: `governance/indexes/standards/` (rules and per-page content)
3. **AST files**: `governance/output/<PAGE_ID>/*.ast.json` — diagram structure (nodes, edges, groups)

## Instructions

1. Read rules from `governance/indexes/standards/` (per index-query: `_all.rules.md` > `<PAGE_ID>/rules.md` > `<PAGE_ID>/page.md`)
2. Read the architecture document and any `*.ast.json` files from `governance/output/<PAGE_ID>/`
3. For each standard found in the index, check if the document addresses it
4. Calculate score and write report

## Validation Approach

For each standard found in index files:
- Search the document **text sections** for evidence of compliance
- Use **AST-based structural validation** (see below) when `*.ast.json` files exist
- Look for keywords, sections, and structural patterns addressing the standard
- Determine compliance level

### AST-Based Structural Validation

When `governance/output/<PAGE_ID>/*.ast.json` files exist, use them for structural evidence. The AST provides canonical `nodes`, `edges`, and `groups` — cite these elements in evidence.

**How to extract standards evidence from AST:**

| AST Element | What to Check | Standards Evidence |
|-------------|---------------|--------------------|
| `ast.nodes` (labels) | Naming conventions | Do node labels follow required conventions (e.g., PascalCase, kebab-case)? |
| `ast.edges` (label) | Protocol standards | Required protocols in edge labels (REST, HTTPS, mTLS)? |
| `ast.groups` (structure) | Architecture standards | Required layers/tiers present (e.g., presentation, business, data)? |
| Node shape in AST | Technology standards | Required technology types (DB, queue, service)? |
| `ast.diagram_type` | Documentation standards | Correct diagram type for the context? |

**Example — matching a standard against AST:**

Standard: *"All services must use REST for synchronous communication"*
Keywords: `REST, API, synchronous, protocol`

AST excerpt: `edges: [{source: "A", target: "B", label: "REST"}, {source: "A", target: "C", label: "REST"}, {source: "A", target: "D", label: "AMQP"}]`

Evidence: Edges A→B and A→C have label "REST". Edge A→D has "AMQP" (async, acceptable). **Cite**: `ast.edges`. **Status: PASS**

**Important**: Cite specific AST elements in your report's Evidence column (e.g., `node:A`, `edge:A→B label:REST`).

## Scoring

- Required standard met: +12 points
- Required standard missing: 0 points
- Optional standard met: +4 bonus
- Base score: Start at 0, max 100

## Output

Write to `governance/output/<PAGE_ID>-standards-report.md`:

```markdown
# Standards Validation Report

**Generated**: [timestamp]
**Model**: <actual model that produced this report>
**Page ID**: <PAGE_ID>
**Document**: governance/output/<PAGE_ID>/page.md
**Index Files**: [count] files from governance/indexes/standards/
**Score**: X/100
**Status**: ✅ PASS / ⚠️ WARN / ❌ FAIL

## Summary

| Status | Count |
|--------|-------|
| ✅ Passed | N |
| ❌ Failed | N |
| ⚠️ Warnings | N |

## Standards Checked

| Standard | Source File | Status | Evidence |
|----------|-------------|--------|----------|
| [standard] | [index file] | ✅/❌/⚠️ | [brief evidence] |

## Documentation Standards

### [Standard Name]
- **Source**: [index file that defines this standard]
- **Status**: ✅ PASS / ❌ FAIL
- **Evidence**: [quote or describe what you found]
- **Recommendation**: [if failed, what to add]

[... repeat for each standard ...]

## Recommendations

[Prioritized list of improvements]
```
