---
name: security-validate
category: security
description: Validate architecture document against security rules from the index. Use when asked to check security, validate threat models, or verify security compliance.
---

# Security Validation

Validate architecture document against all security documents in the index.

## Inputs

1. **Document**: `governance/output/<PAGE_ID>/page.md` (provided by agent)
2. **Index**: `governance/indexes/security/` (rules and per-page content)
3. **AST files**: `governance/output/<PAGE_ID>/attachments/*.ast.json` — diagram structure (nodes, edges, groups)
4. **Pre-score** (optional): `governance/output/<PAGE_ID>/pre-score.json` — deterministic pre-scoring results

## Instructions

1. **Check for pre-score.json** at `governance/output/<PAGE_ID>/pre-score.json`
   - If it exists, read it and use the locked/unlocked status for each rule
   - **Locked rules**: Accept the pre-score status as-is (CONFIRMED_PASS, STRONG_PASS, ABSENT_ERROR, etc.) — do NOT re-evaluate
   - **Unlocked rules** (WEAK_EVIDENCE, CONTRADICTION): Evaluate these using your full LLM analysis
   - If pre-score.json does not exist, evaluate all rules normally (backward compatible)
2. Read rules from `governance/indexes/security/` (per index-query: `_all.rules.md` > `<PAGE_ID>/rules.md` > `<PAGE_ID>/page.md`)
3. Read the architecture document and any `*.ast.json` files from `governance/output/<PAGE_ID>/attachments/`
4. For each security control found in the index, check if addressed (skip locked rules from pre-score)
5. Look for vulnerabilities (hardcoded secrets, etc.)
6. Assign action tiers and write report — locked rules keep their pre-score action tier, unlocked rules use your evaluation

## Validation Approach

For each security control found in index files:
- Search the document **text sections** for evidence of the control
- Use **AST-based structural validation** (see below) when `attachments/*.ast.json` files exist
- Look for security mechanisms, protocols, configurations
- Identify any vulnerabilities or security gaps

### AST-Based Structural Validation

When `governance/output/<PAGE_ID>/attachments/*.ast.json` files exist, use them for structural evidence. The AST provides canonical `nodes`, `edges`, and `groups` — cite these elements in evidence.

**How to extract security evidence from AST:**

| AST Element | What to Check | Security Evidence |
|-------------|---------------|-------------------|
| `ast.edges` (label) | Protocol between components | Encryption in transit (HTTPS, mTLS in edge label) |
| `ast.nodes` (labels) | Component types | Presence of security components (Gateway, Auth, WAF) |
| `ast.groups` | Network segmentation | Trust zones, isolation boundaries (group membership) |
| Missing edges in `ast.edges` | Forbidden communication | No edge A→B → access control, data flow restrictions |
| Edge direction (A→B but not B→A) | One-way data flow | Data flow controls, read-only patterns |
| Node metadata (fill_color, etc.) | Classification | Sensitivity levels, security tiers |

**Example — matching a rule against AST:**

Rule: *"All external vendor traffic must route through API gateway"*
Keywords: `vendor, gateway, external`

AST excerpt: `groups: [{id: "External", children: ["Vendor"]}, {id: "Internal", children: ["GW", "App"]}], edges: [{source: "Vendor", target: "GW", label: "HTTPS"}, {source: "GW", target: "App", label: "mTLS"}]`

Evidence: Edge `Vendor→GW` with label "HTTPS" confirms vendor traffic routes through gateway. No edge `Vendor→App` confirms isolation. **Cite**: `ast.edges`, `ast.groups`. **Status: PASS**

**Important**: Cite specific AST elements in your report's Evidence column (e.g., `edge:Vendor→GW`, `group:Internal`).

## Vulnerabilities to Detect

- Hardcoded passwords/secrets
- Missing encryption
- No authentication mentioned
- Direct database access without validation
- Sensitive data exposure

## Action Tiers

Each rule is assigned an action tier based on evidence found:

| Action | When Assigned |
|--------|---------------|
| **Compliant** | Control clearly met (AST confirmed, strong evidence, or multiple pattern matches) |
| **Verify** | Likely met but needs confirmation (co-occurrence match) |
| **Investigate** | Ambiguous or conflicting evidence (weak evidence, contradiction) |
| **Plan** | Gap acknowledged but deferred (e.g., "planned for next quarter") |
| **Remediate** | Missing, negated, or AST-confirmed violation — must be fixed |

## Output

Write to `governance/output/<PAGE_ID>-security-report.md`:

```markdown
# Security Validation Report

**Generated**: [timestamp]
**Model**: <actual model that produced this report>
**Page ID**: <PAGE_ID>
**Document**: governance/output/<PAGE_ID>/page.md
**Index Files**: [count] files from governance/indexes/security/

## Action Summary

| Action | Count |
|--------|-------|
| Compliant | N |
| Verify | N |
| Investigate | N |
| Plan | N |
| Remediate | N |

## Security Controls Checked

| Control | Source File | Severity | Action | Urgency | Evidence |
|---------|-------------|----------|--------|---------|----------|
| [control] | [index file] | Critical/High/Medium | Compliant/Verify/Investigate/Plan/Remediate | --/low/medium/high/critical | [brief evidence] |

## Security Controls

### [Control Name]
- **Source**: [index file that defines this control]
- **Severity**: Critical / High / Medium
- **Action**: Compliant / Verify / Investigate / Plan / Remediate
- **Urgency**: -- / low / medium / high / critical
- **Evidence**: [quote or describe what you found]
- **Risk**: [what could go wrong if missing]
- **Recommendation**: [if not compliant, what to do]

[... repeat for each control ...]

## Vulnerabilities Detected

[List any security issues found with severity and urgency]

## Risk Assessment

[Overall security posture analysis focusing on actions needed]

## Recommendations

[Prioritized security improvements — remediate items first, then plan, then investigate]
```
