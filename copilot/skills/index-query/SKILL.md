---
name: index-query
description: Read all documents from a governance index folder. Use when asked to get rules, fetch standards, or retrieve indexed guidelines.
---

# Index Query

Read ALL .md files from a governance index folder to build a knowledge base.

## Instructions

1. **List** all .md files in the specified index directory
2. **Read** each file to extract rules/standards/guidelines
3. **Return** the combined content for validation

## Available Indexes

| Index | Path | Content |
|-------|------|---------|
| Patterns | `governance/indexes/patterns/` | Design pattern rules and examples |
| Standards | `governance/indexes/standards/` | Architectural standards |
| Security | `governance/indexes/security/` | Security guidelines and controls |

## Usage

To query an index:
1. List files in `governance/indexes/<index>/`
2. Read each `.md` file found
3. Use the content as the knowledge base for validation

## Example

```
# List files in patterns index
governance/indexes/patterns/
├── rules.md
├── microservices-patterns.md
└── api-design-patterns.md

# Read ALL files to build knowledge base
```

## Output

Combined content from all .md files in the index, used by validation agents to check architecture documents.

## Important

- Read ALL .md files in the folder, not just rules.md
- Each file may contain different patterns/standards/controls
- The validation agent uses ALL indexed content for checking
