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
3. **AST files**: `governance/output/<PAGE_ID>/attachments/*.ast.json` — diagram structure (nodes, edges, groups)
4. **Pre-score** (optional): `governance/output/<PAGE_ID>/pre-score.json` — deterministic pre-scoring results

## Instructions

1. **Check for pre-score.json** at `governance/output/<PAGE_ID>/pre-score.json`
   - If it exists, read it and use the locked/unlocked status for each rule
   - **Locked rules**: Accept the pre-score status as-is — do NOT re-evaluate
   - **Unlocked rules** (WEAK_EVIDENCE, CONTRADICTION): Evaluate using full LLM analysis
   - If pre-score.json does not exist, evaluate all rules normally (backward compatible)
2. Read rules from `governance/indexes/patterns/` (per index-query: `_all.rules.md` > `<PAGE_ID>/rules.md` > `<PAGE_ID>/page.md`)
3. Read the architecture document and any `*.ast.json` files from `governance/output/<PAGE_ID>/attachments/`
4. For each pattern found in the index, analyze if the document addresses it (skip locked rules from pre-score):
   - **Required patterns**: Must be present -> PASS/FAIL
   - **Recommended patterns**: Nice to have -> PASS/WARN
   - **Anti-patterns**: Must NOT be present -> PASS/FAIL
5. Assign action tiers and write report — locked rules keep their pre-score action tier

## Validation Approach

For each pattern found in index files:
- Search the document **text sections** for evidence of the pattern
- Use **AST-based structural validation** (see below) when `attachments/*.ast.json` files exist
- Look for keywords, descriptions, and structural patterns
- Determine if pattern is implemented or just mentioned

### AST-Based Structural Validation

When `governance/output/<PAGE_ID>/attachments/*.ast.json` files exist, use them for structural evidence. The AST provides canonical `nodes`, `edges`, and `groups` — cite these elements in evidence.

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

## Action Tiers

Each rule is assigned an action tier based on evidence found:

| Action | When Assigned |
|--------|---------------|
| **Compliant** | Pattern clearly present (AST confirmed, strong evidence, or multiple pattern matches) |
| **Verify** | Likely present but needs confirmation (co-occurrence match) |
| **Investigate** | Ambiguous or conflicting evidence (weak evidence, contradiction) |
| **Plan** | Gap acknowledged but deferred (e.g., "planned for next quarter") |
| **Remediate** | Missing, negated, or AST-confirmed violation — must be fixed |

## Output

Write to `governance/output/<PAGE_ID>-patterns-report.md`:

```markdown
# Pattern Validation Report

**Generated**: [timestamp]
**Model**: <actual model that produced this report>
**Page ID**: <PAGE_ID>
**Document**: governance/output/<PAGE_ID>/page.md
**Index Files**: [count] files from governance/indexes/patterns/

## Action Summary

| Action | Count |
|--------|-------|
| Compliant | N |
| Verify | N |
| Investigate | N |
| Plan | N |
| Remediate | N |

## Patterns Checked

| Pattern | Source File | Action | Urgency | Evidence |
|---------|-------------|--------|---------|----------|
| [pattern] | [index file] | Compliant/Verify/Investigate/Plan/Remediate | --/low/medium/high/critical | [brief evidence] |

## Required Patterns

### [Pattern Name]
- **Source**: [index file that defines this pattern]
- **Action**: Compliant / Verify / Investigate / Plan / Remediate
- **Urgency**: -- / low / medium / high / critical
- **Evidence**: [quote or describe what you found]
- **Recommendation**: [if not compliant, what to do]

[... repeat for each pattern ...]

## Anti-Patterns

[List any detected anti-patterns]

## Recommendations

[Prioritized list of improvements — remediate items first]
```
