---
name: index-query
description: Query pre-indexed rules from governance indexes. Use when asked to get rules, fetch standards, or retrieve indexed guidelines.
---

# Index Query

Read and return rules from pre-indexed governance rule files.

## Instructions

1. **Read** the rules file from the specified index directory
2. **Return** the rules content for use in validation

## Available Indexes

| Index | Path | Content |
|-------|------|---------|
| Patterns | `governance/indexes/patterns/rules.md` | Design pattern rules |
| Standards | `governance/indexes/standards/rules.md` | Architectural standards |
| Security | `governance/indexes/security/rules.md` | Security guidelines |

## Usage

To query patterns rules:
- Read `governance/indexes/patterns/rules.md`

To query standards rules:
- Read `governance/indexes/standards/rules.md`

To query security rules:
- Read `governance/indexes/security/rules.md`

## Output

The content of the rules file, which contains:
- Rule definitions with severity and requirements
- Keywords for detection
- Structured JSON rules at the bottom

## Important

- DO NOT run any shell commands or Python scripts
- Use ONLY the read file tool
- Return the full content of the rules file
