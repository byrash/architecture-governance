---
name: pattern-validate
description: Validate architecture document against pattern rules. Use when asked to check patterns, validate design patterns, or verify pattern compliance.
---

# Pattern Validation

Validate architecture document against design pattern rules.

## Inputs

1. **Document**: `governance/output/architecture.md`
2. **Rules**: `governance/indexes/patterns/rules.md`

## Instructions

1. Read the architecture document
2. Read the pattern rules
3. For each rule, analyze if the document addresses it:
   - **Required patterns**: Must be present → PASS/FAIL
   - **Recommended patterns**: Nice to have → PASS/WARN
   - **Anti-patterns**: Must NOT be present → PASS/FAIL
4. Calculate score and write report

## Validation Criteria

| Rule ID | Pattern | Required | Look For |
|---------|---------|----------|----------|
| PAT-001 | Repository Pattern | Yes | Data access abstraction, repository interfaces |
| PAT-002 | Dependency Injection | Yes | DI, IoC, injected dependencies, containers |
| PAT-003 | API Gateway | Yes | Central entry point, gateway, API management |
| PAT-004 | Factory Pattern | No | Object creation, factories, builders |
| PAT-005 | Circuit Breaker | No | Fault tolerance, resilience, fallbacks |
| PAT-006 | Event-Driven | No | Events, messages, queues, pub/sub |

## Scoring

- Required pattern present: +15 points
- Required pattern missing: 0 points
- Recommended pattern present: +5 bonus
- Anti-pattern detected: -10 points
- Base score: Start at 0, max 100

## Output

Write to `governance/output/patterns-report.md`:

```markdown
# Pattern Validation Report

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

## Required Patterns

### PAT-001: Repository Pattern
- **Status**: ✅ PASS / ❌ FAIL
- **Evidence**: [quote or describe what you found]
- **Recommendation**: [if failed, what to add]

[... repeat for each pattern ...]

## Anti-Patterns

[List any detected anti-patterns]

## Recommendations

[Prioritized list of improvements]
```
