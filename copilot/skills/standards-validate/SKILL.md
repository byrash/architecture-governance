---
name: standards-validate
description: Validate architecture document against standards rules. Use when asked to check standards, validate naming conventions, or verify documentation compliance.
---

# Standards Validation

Validate architecture document against architectural standards.

## Inputs

1. **Document**: `governance/output/architecture.md`
2. **Rules**: `governance/indexes/standards/rules.md`

## Instructions

1. Read the architecture document
2. Read the standards rules
3. For each standard, check if the document addresses it
4. Calculate score and write report

## Validation Criteria

| Rule ID | Standard | Required | Look For |
|---------|----------|----------|----------|
| STD-001 | API Versioning | Yes | /api/v1/, version headers, versioning strategy |
| STD-002 | Architecture Overview | Yes | Overview section, context diagram, description |
| STD-003 | Error Handling | Yes | Error responses, error codes, retry strategies |
| STD-004 | Component Naming | Yes | *Service, *Controller, *Repository naming |
| STD-005 | Health Check | Yes | /health, /healthz, liveness, readiness |
| STD-006 | Configuration | Yes | Externalized config, environment variables |
| STD-007 | Logging | Yes | Logging strategy, log levels, observability |
| STD-008 | Database Schema | No | ERD, data model, schema documentation |

## Scoring

- Required standard met: +12 points
- Required standard missing: 0 points
- Optional standard met: +4 bonus
- Base score: Start at 0, max 100

## Output

Write to `governance/output/standards-report.md`:

```markdown
# Standards Validation Report

**Generated**: [timestamp]
**Document**: governance/output/architecture.md
**Score**: X/100
**Status**: ✅ PASS / ⚠️ WARN / ❌ FAIL

## Summary

| Status | Count |
|--------|-------|
| ✅ Passed | N |
| ❌ Failed | N |
| ⚠️ Warnings | N |

## Documentation Standards

### STD-001: API Versioning
- **Status**: ✅ PASS / ❌ FAIL
- **Evidence**: [quote or describe what you found]
- **Recommendation**: [if failed, what to add]

[... repeat for each standard ...]

## Recommendations

[Prioritized list of improvements]
```
