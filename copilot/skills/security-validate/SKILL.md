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
3. **AST files**: `governance/output/<PAGE_ID>/*.ast.json` — diagram structure (nodes, edges, groups)

## Instructions

1. Read rules from `governance/indexes/security/` (per index-query: `_all.rules.md` > `<PAGE_ID>/rules.md` > `<PAGE_ID>/page.md`)
2. Read the architecture document and any `*.ast.json` files from `governance/output/<PAGE_ID>/`
3. For each security control found in the index, check if addressed
4. Look for vulnerabilities (hardcoded secrets, etc.)
5. Calculate score and write report

## Validation Approach

For each security control found in index files:
- Search the document **text sections** for evidence of the control
- Use **AST-based structural validation** (see below) when `*.ast.json` files exist
- Look for security mechanisms, protocols, configurations
- Identify any vulnerabilities or security gaps

### AST-Based Structural Validation

When `governance/output/<PAGE_ID>/*.ast.json` files exist, use them for structural evidence. The AST provides canonical `nodes`, `edges`, and `groups` — cite these elements in evidence.

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

## Scoring

- Critical control met: +15 points
- Critical control missing: 0 points (MAJOR issue)
- High control met: +10 points
- Medium control met: +5 points
- Vulnerability found: -20 points each
- Base score: Start at 0, max 100

## Output

Write to `governance/output/<PAGE_ID>-security-report.md`:

```markdown
# Security Validation Report

**Generated**: [timestamp]
**Model**: <actual model that produced this report>
**Page ID**: <PAGE_ID>
**Document**: governance/output/<PAGE_ID>/page.md
**Index Files**: [count] files from governance/indexes/security/
**Score**: X/100
**Risk Level**: LOW / MEDIUM / HIGH / CRITICAL
**Status**: ✅ PASS / ⚠️ WARN / ❌ FAIL

## Summary

| Status | Count |
|--------|-------|
| ✅ Passed | N |
| ❌ Failed | N |
| 🚨 Critical | N |

## Security Controls Checked

| Control | Source File | Severity | Status | Evidence |
|---------|-------------|----------|--------|----------|
| [control] | [index file] | Critical/High/Medium | ✅/❌ | [brief evidence] |

## Security Controls

### [Control Name]
- **Source**: [index file that defines this control]
- **Severity**: Critical / High / Medium
- **Status**: ✅ PASS / ❌ FAIL
- **Evidence**: [quote or describe what you found]
- **Risk**: [what could go wrong if missing]
- **Recommendation**: [if failed, what to add]

[... repeat for each control ...]

## Vulnerabilities Detected

[List any security issues found with severity]

## Risk Assessment

[Overall security posture analysis]

## Recommendations

[Prioritized security improvements]
```
