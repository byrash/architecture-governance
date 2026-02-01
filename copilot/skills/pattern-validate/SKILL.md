---
name: pattern-validate
description: Validate architecture document against pattern rules from the index. Use when asked to check patterns, validate design patterns, or verify pattern compliance.
---

# Pattern Validation

Validate architecture document against all design pattern documents in the index.

## Inputs

1. **Document**: `governance/output/<PAGE_ID>/page.md` (provided by agent)
2. **Index**: `governance/indexes/patterns/` (ALL .md files)

## Instructions

1. Read ALL .md files from `governance/indexes/patterns/`
2. Read the architecture document
3. For each pattern found in the index files, analyze if the document addresses it:
   - **Required patterns**: Must be present → PASS/FAIL
   - **Recommended patterns**: Nice to have → PASS/WARN
   - **Anti-patterns**: Must NOT be present → PASS/FAIL
4. Calculate score and write report

## Validation Approach

For each pattern found in index files:
- Search the document for evidence of the pattern
- Look for keywords, descriptions, diagrams mentioning the pattern
- Determine if pattern is implemented or just mentioned

## Scoring

- Required pattern present: +15 points
- Required pattern missing: 0 points
- Recommended pattern present: +5 bonus
- Anti-pattern detected: -10 points
- Base score: Start at 0, max 100

## Output

Write to `governance/output/<PAGE_ID>/patterns-report.md`:

```markdown
# Pattern Validation Report

**Generated**: [timestamp]
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
