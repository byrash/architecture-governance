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
   - Score (X/100)
   - Status (PASS/FAIL)
   - Count: total checked, PASS, ERROR, WARN
   - Critical issues (ERROR items only -- one line each)
   - Quick wins (WARN items that are easy fixes -- one line each)
3. Write the extracted block to `<PAGE_ID>-merge-extract.md`
4. Release the patterns report from context

### Phase 2: Extract from Standards Report

1. Read `<PAGE_ID>-standards-report.md`
2. Extract same compact block (score, status, counts, critical issues, quick wins)
3. Append to `<PAGE_ID>-merge-extract.md`
4. Release the standards report from context

### Phase 3: Extract from Security Report

1. Read `<PAGE_ID>-security-report.md`
2. Extract same compact block (score, status, counts, critical issues, quick wins)
3. Append to `<PAGE_ID>-merge-extract.md`
4. Release the security report from context

### Phase 4: Assemble Final Report

1. Read `<PAGE_ID>-merge-extract.md` (small -- just the 3 compact blocks)
2. Calculate weighted score, determine overall status, write executive summary
3. Write `<PAGE_ID>-governance-report.md` using the output format below
4. Delete `<PAGE_ID>-merge-extract.md` (cleanup)

## Extract Format (per report)

Each compact block written to the extract file:

```markdown
### <Category> (weight: <N>%)
- **Score**: X/100
- **Status**: PASS | FAIL
- **Checked**: <total> | PASS: <n> | ERROR: <n> | WARN: <n>
- **Critical**: <one-line summary per ERROR item, or "none">
- **Quick wins**: <one-line summary per easy WARN fix, or "none">
```

## Scoring Formula

```
Overall = (Patterns × 0.30) + (Standards × 0.30) + (Security × 0.40)
```

Security weighted highest (40%) due to criticality.

## Pass/Fail Threshold

- **PASS**: Score >= 70
- **WARN**: Score 50-69
- **FAIL**: Score < 50

## Output

Write to `governance/output/<PAGE_ID>-governance-report.md`:

```markdown
# Architecture Governance Report

**Generated**: [timestamp]
**Page ID**: <PAGE_ID>
**Document**: governance/output/<PAGE_ID>/page.md

## Overall Result

| Metric | Value |
|--------|-------|
| **Status** | ✅ PASS / ⚠️ WARN / ❌ FAIL |
| **Overall Score** | X/100 |
| **Patterns** | X/100 (30%) |
| **Standards** | X/100 (30%) |
| **Security** | X/100 (40%) |

## Executive Summary

[2-3 sentences summarizing key findings across all three reports]

## Score Breakdown

| Category | Score | Weight | Weighted | Checked | Errors | Warnings |
|----------|-------|--------|----------|---------|--------|----------|
| Patterns | X/100 | 30% | X.X | <n> | <n> | <n> |
| Standards | X/100 | 30% | X.X | <n> | <n> | <n> |
| Security | X/100 | 40% | X.X | <n> | <n> | <n> |
| **Total** | | | **X/100** | **<n>** | **<n>** | **<n>** |

## Critical Issues

[List critical/high severity items from all three reports that must be addressed]

## Quick Wins

[Easy fixes from all three reports that would improve score]

## Recommendations

[Prioritized improvement list]

---

## Detailed Reports

Individual reports are available at:

- **Patterns**: `governance/output/<PAGE_ID>-patterns-report.md`
- **Standards**: `governance/output/<PAGE_ID>-standards-report.md`
- **Security**: `governance/output/<PAGE_ID>-security-report.md`
```
