---
name: merge-reports
category: reporting
description: Merge validation reports into final governance report. Use when asked to combine reports or create final governance report.
---

# Merge Reports

Combine all validation reports into final governance report using **incremental extraction** -- read one report at a time, extract metrics, release context, repeat.

## Inputs

From `governance/output/`:
1. `<PAGE_ID>-patterns-report.md`
2. `<PAGE_ID>-standards-report.md`
3. `<PAGE_ID>-security-report.md`

## Instructions (Incremental -- one report at a time)

Process each report sequentially. Only ONE report is in context at a time.

### Phase 1: Extract from Patterns Report

1. Read `<PAGE_ID>-patterns-report.md`
2. Extract into a compact block:
   - Action counts: Compliant / Verify / Investigate / Plan / Remediate
   - Count: total checked, ERROR items, WARN items
   - Critical issues (ERROR items only -- one line each)
   - Quick wins (WARN items that are easy fixes -- one line each)
3. Write the extracted block to `<PAGE_ID>-merge-extract.md`
4. Release the patterns report from context

### Phase 2: Extract from Standards Report

1. Read `<PAGE_ID>-standards-report.md`
2. Extract same compact block (action counts, checked counts, critical issues, quick wins)
3. Append to `<PAGE_ID>-merge-extract.md`
4. Release the standards report from context

### Phase 3: Extract from Security Report

1. Read `<PAGE_ID>-security-report.md`
2. Extract same compact block (action counts, checked counts, critical issues, quick wins)
3. Append to `<PAGE_ID>-merge-extract.md`
4. Release the security report from context

### Phase 4: Assemble Final Report

1. Read `<PAGE_ID>-merge-extract.md` (small -- just the 3 compact blocks)
2. Sum action counts across categories, write executive summary focusing on required actions
3. Write `<PAGE_ID>-governance-report.md` using the output format below
4. Delete `<PAGE_ID>-merge-extract.md` (cleanup)

## Extract Format (per report)

Each compact block written to the extract file:

```markdown
### <Category>
- **Compliant**: <n> | **Verify**: <n> | **Investigate**: <n> | **Plan**: <n> | **Remediate**: <n>
- **Checked**: <total> | ERROR: <n> | WARN: <n>
- **Critical**: <one-line summary per ERROR item, or "none">
- **Quick wins**: <one-line summary per easy WARN fix, or "none">
```

## Action Tiers

Each rule is assigned an action tier instead of a numeric score:

| Action | Meaning |
|--------|---------|
| **Compliant** | No action needed — rule is satisfied |
| **Verify** | Likely compliant — confirm in next review |
| **Investigate** | Ambiguous evidence — needs human review |
| **Plan** | Acknowledged gap — schedule on roadmap |
| **Remediate** | Violation or missing — implement or fix |

## Output

Write to `governance/output/<PAGE_ID>-governance-report.md`:

```markdown
# Architecture Governance Report

**Generated**: [timestamp]
**Page ID**: <PAGE_ID>
**Document**: governance/output/<PAGE_ID>/page.md

## Action Summary

| Action | Total | Patterns | Standards | Security |
|--------|-------|----------|-----------|----------|
| **Remediate** | <n> | <n> | <n> | <n> |
| **Plan** | <n> | <n> | <n> | <n> |
| **Investigate** | <n> | <n> | <n> | <n> |
| **Verify** | <n> | <n> | <n> | <n> |
| **Compliant** | <n> | <n> | <n> | <n> |
| **Total Rules** | <n> | <n> | <n> | <n> |

## Executive Summary

[2-3 sentences summarizing the actions needed. Lead with Remediate and Investigate counts, then mention what is Compliant.]

## Critical Issues

[List items requiring remediation — group by urgency (critical first, then high, then medium)]

## Quick Wins

[Easy fixes from Investigate/Plan tiers that can be resolved quickly]

## Recommendations

[Prioritized improvement list — remediate first, then plan, then investigate]

---

## Detailed Reports

Individual reports are available at:

- **Patterns**: `governance/output/<PAGE_ID>-patterns-report.md`
- **Standards**: `governance/output/<PAGE_ID>-standards-report.md`
- **Security**: `governance/output/<PAGE_ID>-security-report.md`
```
