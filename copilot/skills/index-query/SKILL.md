---
name: index-query
category: utility
description: Read all documents from a governance index folder. Use when asked to get rules, fetch standards, or retrieve indexed guidelines.
---

# Index Query

Read governance rules from an index folder, preferring compact pre-extracted `.rules.md` files over raw `.md` documents for token efficiency.

## Instructions

1. **List** all files in the specified index directory
2. **For each document**, check if a `.rules.md` file exists:
   - If `<name>.rules.md` exists → read ONLY the `.rules.md` file (compact, pre-extracted rules)
   - If no `.rules.md` exists for that document → fall back to reading the raw `.md` file
3. **Return** the combined content for validation

## Priority Order

| Priority | File Pattern | Description | When Used |
|----------|-------------|-------------|-----------|
| 1st (best) | `_all.rules.md` | Consolidated rules from ALL sources, deduplicated, sorted | After batch rules-extraction |
| 2nd (preferred) | `<name>.rules.md` | Compact pre-extracted rules per document | After per-file rules-extraction |
| 3rd (fallback) | `<name>.md` | Raw full document | Before rules extraction, or if extraction failed |

**If `_all.rules.md` exists**, read ONLY that file -- it contains all rules from all sources in one consolidated, deduplicated table. This is the most token-efficient option.

## Available Indexes

| Index | Path | Content |
|-------|------|---------|
| Patterns | `governance/indexes/patterns/` | Design pattern rules and examples |
| Standards | `governance/indexes/standards/` | Architectural standards |
| Security | `governance/indexes/security/` | Security guidelines and controls |

## Usage

To query an index:
1. List files in `governance/indexes/<index>/`
2. Group files by base name (e.g., `123-doc.md` and `123-doc.rules.md` are the same document)
3. For each document, prefer `.rules.md` if available
4. Read the selected files and use as the knowledge base for validation

## Example

```
# List files in patterns index
governance/indexes/patterns/
├── _all.rules.md                   # consolidated rules (BEST - read only this if present)
├── 123-microservices.md            # raw document
├── 123-microservices.rules.md      # pre-extracted rules
├── 456-api-design.md               # raw document
├── 456-api-design.rules.md         # pre-extracted rules
└── rules.md                        # standalone rules file

# Reading strategy when _all.rules.md EXISTS:
# ✅ Read _all.rules.md              (consolidated, ~400 tokens for all rules)
# ⏭️ Skip everything else            (_all.rules.md already contains all rules)

# Reading strategy when _all.rules.md DOES NOT EXIST:
# ✅ Read 123-microservices.rules.md  (compact table, ~200 tokens)
# ⏭️ Skip 123-microservices.md        (raw doc has matching .rules.md)
# ✅ Read 456-api-design.rules.md     (compact table)
# ⏭️ Skip 456-api-design.md           (raw doc has matching .rules.md)
# ✅ Read rules.md                    (standalone, always read)
```

## Output

Combined rules content from the index, used by validation agents to check architecture documents.

## Important

- Always prefer `.rules.md` over raw `.md` when both exist for the same document
- Read standalone `.md` files (like `rules.md`) that have no corresponding `.rules.md`
- The `.rules.md` files contain the same governance rules in a compact markdown table (~90% fewer tokens)
- If a `.rules.md` seems incomplete or empty, fall back to the raw `.md` for that document
- Each file may contain different patterns/standards/controls
- The validation agent uses ALL indexed content for checking
