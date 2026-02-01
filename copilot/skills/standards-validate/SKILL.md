---
name: standards-validate
description: Validate architecture document against standards from the index. Use when asked to check standards, validate naming conventions, or verify documentation compliance.
---

# Standards Validation

Validate architecture document against all standards documents in the index.

## Inputs

1. **Document**: `governance/output/<PAGE_ID>/page.md` (provided by agent)
2. **Index**: `governance/indexes/standards/` (ALL .md files)

## Instructions

1. Read ALL .md files from `governance/indexes/standards/`
2. Read the architecture document
3. For each standard found in the index files, check if the document addresses it
4. Calculate score and write report

## Validation Approach

For each standard found in index files:
- Search the document for evidence of compliance
- Look for keywords, sections, diagrams addressing the standard
- Determine compliance level

## Scoring

- Required standard met: +12 points
- Required standard missing: 0 points
- Optional standard met: +4 bonus
- Base score: Start at 0, max 100

## Output

Write to `governance/output/<PAGE_ID>/standards-report.md`:

```markdown
# Standards Validation Report

**Generated**: [timestamp]
**Page ID**: <PAGE_ID>
**Document**: governance/output/<PAGE_ID>/page.md
**Index Files**: [count] files from governance/indexes/standards/
**Score**: X/100
**Status**: ✅ PASS / ⚠️ WARN / ❌ FAIL

## Summary

| Status | Count |
|--------|-------|
| ✅ Passed | N |
| ❌ Failed | N |
| ⚠️ Warnings | N |

## Standards Checked

| Standard | Source File | Status | Evidence |
|----------|-------------|--------|----------|
| [standard] | [index file] | ✅/❌/⚠️ | [brief evidence] |

## Documentation Standards

### [Standard Name]
- **Source**: [index file that defines this standard]
- **Status**: ✅ PASS / ❌ FAIL
- **Evidence**: [quote or describe what you found]
- **Recommendation**: [if failed, what to add]

[... repeat for each standard ...]

## Recommendations

[Prioritized list of improvements]
```
