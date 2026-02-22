---
name: pattern-validate
category: patterns
description: Validate architecture document against pattern rules from the index. Use when asked to check patterns, validate design patterns, or verify pattern compliance.
---

# Pattern Validation

Validate architecture document against all design pattern documents in the index.

## Inputs

1. **Document**: `governance/output/<PAGE_ID>/page.md` (provided by agent)
2. **Index**: `governance/indexes/patterns/` (rules and per-page content)
3. **AST files**: `governance/output/<PAGE_ID>/*.ast.json` — diagram structure (nodes, edges, groups)

## Instructions

1. Read rules from `governance/indexes/patterns/` (per index-query: `_all.rules.md` > `<PAGE_ID>/rules.md` > `<PAGE_ID>/page.md`)
2. Read the architecture document and any `*.ast.json` files from `governance/output/<PAGE_ID>/`
3. For each pattern found in the index, analyze if the document addresses it:
   - **Required patterns**: Must be present → PASS/FAIL
   - **Recommended patterns**: Nice to have → PASS/WARN
   - **Anti-patterns**: Must NOT be present → PASS/FAIL
4. Calculate score and write report

## Validation Approach

For each pattern found in index files:
- Search the document **text sections** for evidence of the pattern
- Use **AST-based structural validation** (see below) when `*.ast.json` files exist
- Look for keywords, descriptions, and structural patterns
- Determine if pattern is implemented or just mentioned

### AST-Based Structural Validation

When `governance/output/<PAGE_ID>/*.ast.json` files exist, use them for structural evidence. The AST provides canonical `nodes`, `edges`, and `groups` — cite these elements in evidence.

**How to extract pattern evidence from AST:**

| AST Element | What to Check | Pattern Evidence |
|-------------|---------------|------------------|
| `ast.nodes` | Node ids, labels, shapes | Component types (e.g., node label "Gateway" = API Gateway pattern, "Queue" = async messaging) |
| `ast.edges` | source → target, label | Communication patterns, protocol choices (REST, gRPC in edge label) |
| `ast.groups` | group id, label, children | Layered architecture, tier separation, bounded contexts |
| Fan-out edges (one source, many targets) | Distribution patterns | Load balancing, pub/sub, event-driven |
| Edge direction (A→B but not B→A) | Mediation patterns | Proxy, adapter, gateway patterns |
| Group membership (node in group) | Isolation patterns | Microservice independence, domain boundaries |
| Node shape in AST | Data patterns | Database, queue, service types |

**Example — matching a pattern rule against AST:**

Rule: *"API Gateway pattern required"*
Keywords: `gateway, api, routing, entry point`

AST excerpt: `nodes: [{id: "GW", label: "API Gateway", ...}], edges: [{source: "Client", target: "GW"}, {source: "GW", target: "ServiceA"}, ...]`

Evidence: Node `GW` (label "API Gateway") exists. Edge `Client→GW` as single entry, edges `GW→ServiceA`, `GW→ServiceB` show fan-out. **Cite**: `ast.nodes[GW]`, `ast.edges[Client→GW]`. **Status: PASS**

**Anti-pattern example:**

Anti-pattern: *"No direct client-to-service calls"*

Evidence: Edges `Client→ServiceA`, `Client→ServiceB` in `ast.edges` bypass gateway. **Cite**: `ast.edges` entries. **Status: FAIL (anti-pattern detected)**

**Important**: Cite specific AST elements in your report's Evidence column (e.g., `node:GW in group:Internal`, `edge:Client→Gateway`).

## Scoring

- Required pattern present: +15 points
- Required pattern missing: 0 points
- Recommended pattern present: +5 bonus
- Anti-pattern detected: -10 points
- Base score: Start at 0, max 100

## Output

Write to `governance/output/<PAGE_ID>-patterns-report.md`:

```markdown
# Pattern Validation Report

**Generated**: [timestamp]
**Model**: <actual model that produced this report>
**Page ID**: <PAGE_ID>
**Document**: governance/output/<PAGE_ID>/page.md
**Index Files**: [count] files from governance/indexes/patterns/
**Score**: X/100
**Status**: ✅ PASS / ⚠️ WARN / ❌ FAIL

## Summary

| Status | Count |
|--------|-------|
| ✅ Passed | N |
| ❌ Failed | N |
| ⚠️ Warnings | N |

## Patterns Checked

| Pattern | Source File | Status | Evidence |
|---------|-------------|--------|----------|
| [pattern] | [index file] | ✅/❌/⚠️ | [brief evidence] |

## Required Patterns

### [Pattern Name]
- **Source**: [index file that defines this pattern]
- **Status**: ✅ PASS / ❌ FAIL
- **Evidence**: [quote or describe what you found]
- **Recommendation**: [if failed, what to add]

[... repeat for each pattern ...]

## Anti-Patterns

[List any detected anti-patterns]

## Recommendations

[Prioritized list of improvements]
```
