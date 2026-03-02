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
3. **AST files**: `governance/output/<PAGE_ID>/attachments/*.ast.json` — diagram structure (nodes, edges, groups)
4. **Pre-score** (optional): `governance/output/<PAGE_ID>/pre-score.json` — deterministic pre-scoring results

## Instructions

1. **Check for pre-score.json** at `governance/output/<PAGE_ID>/pre-score.json`
   - If it exists, read it and use the locked/unlocked status for each rule
   - **Locked rules**: Accept the pre-score status as-is — do NOT re-evaluate
   - **Unlocked rules** (WEAK_EVIDENCE, CONTRADICTION): Evaluate using full LLM analysis
   - If pre-score.json does not exist, evaluate all rules normally (backward compatible)
2. Read rules from `governance/indexes/standards/` (per index-query: `_all.rules.md` > `<PAGE_ID>/rules.md` > `<PAGE_ID>/page.md`)
3. Read the architecture document and any `*.ast.json` files from `governance/output/<PAGE_ID>/attachments/`
4. For each standard found in the index, check if the document addresses it (skip locked rules from pre-score)
5. Assign action tiers and write report — locked rules keep their pre-score action tier

## Validation Approach

For each standard found in index files:
- Search the document **text sections** for evidence of compliance
- Use **AST-based structural validation** (see below) when `attachments/*.ast.json` files exist
- Look for keywords, sections, and structural patterns addressing the standard
- Determine compliance level

### AST-Based Structural Validation

When `governance/output/<PAGE_ID>/attachments/*.ast.json` files exist, use them for structural evidence. The AST provides canonical `nodes`, `edges`, and `groups` — cite these elements in evidence.

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

## Action Tiers

Each rule is assigned an action tier based on evidence found:

| Action | When Assigned |
|--------|---------------|
| **Compliant** | Standard clearly met (AST confirmed, strong evidence, or multiple pattern matches) |
| **Verify** | Likely met but needs confirmation (co-occurrence match) |
| **Investigate** | Ambiguous or conflicting evidence (weak evidence, contradiction) |
| **Plan** | Gap acknowledged but deferred (e.g., "planned for next quarter") |
| **Remediate** | Missing, negated, or AST-confirmed violation — must be fixed |

## Output

Write to `governance/output/<PAGE_ID>-standards-report.md`:

```markdown
# Standards Validation Report

**Generated**: [timestamp]
**Model**: <actual model that produced this report>
**Page ID**: <PAGE_ID>
**Document**: governance/output/<PAGE_ID>/page.md
**Index Files**: [count] files from governance/indexes/standards/

## Action Summary

| Action | Count |
|--------|-------|
| Compliant | N |
| Verify | N |
| Investigate | N |
| Plan | N |
| Remediate | N |

## Standards Checked

| Standard | Source File | Action | Urgency | Evidence |
|----------|-------------|--------|---------|----------|
| [standard] | [index file] | Compliant/Verify/Investigate/Plan/Remediate | --/low/medium/high/critical | [brief evidence] |

## Documentation Standards

### [Standard Name]
- **Source**: [index file that defines this standard]
- **Action**: Compliant / Verify / Investigate / Plan / Remediate
- **Urgency**: -- / low / medium / high / critical
- **Evidence**: [quote or describe what you found]
- **Recommendation**: [if not compliant, what to do]

[... repeat for each standard ...]

## Recommendations

[Prioritized list of improvements — remediate items first]
```
