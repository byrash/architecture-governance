---
name: merge-reports
description: Merge validation reports into final governance report. Use when asked to combine reports or create final governance report.
---

# Merge Reports

Combine all validation reports into final governance report.

## Inputs

1. `governance/output/patterns-report.md`
2. `governance/output/standards-report.md`
3. `governance/output/security-report.md`

## Instructions

1. Read all three validation reports
2. Extract scores from each
3. Calculate overall weighted score
4. Write executive summary
5. Combine into final report

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

Write to `governance/output/governance-report.md`:

```markdown
# Architecture Governance Report

**Generated**: [timestamp]
**Document**: governance/output/architecture.md

## Overall Result

| Metric | Value |
|--------|-------|
| **Status** | ✅ PASS / ⚠️ WARN / ❌ FAIL |
| **Overall Score** | X/100 |
| **Patterns** | X/100 (30%) |
| **Standards** | X/100 (30%) |
| **Security** | X/100 (40%) |

## Executive Summary

[2-3 sentences summarizing key findings]

## Score Breakdown

| Category | Score | Weight | Weighted |
|----------|-------|--------|----------|
| Patterns | X/100 | 30% | X.X |
| Standards | X/100 | 30% | X.X |
| Security | X/100 | 40% | X.X |
| **Total** | | | **X/100** |

## Critical Issues

[List critical/high severity items that must be addressed]

## Quick Wins

[Easy fixes that would improve score]

## Recommendations

[Prioritized improvement list]

---

## Detailed Reports

### Pattern Validation
[Include patterns-report.md content]

### Standards Validation
[Include standards-report.md content]

### Security Validation
[Include security-report.md content]
```
