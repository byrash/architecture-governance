---
name: index-query
category: utility
description: Read all documents from a governance index folder. Use when asked to get rules, fetch standards, or retrieve indexed guidelines.
---

# Index Query

Read governance rules from an index folder, preferring compact pre-extracted `.rules.md` files over raw `.md` documents for token efficiency.

## Instructions

1. **List** all items in the specified index directory (root files + `<PAGE_ID>/` subfolders)
2. **Apply the priority order** below when choosing what to read for each page
3. **Return** the combined content for validation

## Index Folder Layout

```
governance/indexes/<index>/
├── _all.rules.md           # consolidated (read first if present)
├── rules.md                # standalone hand-written rules
├── <PAGE_ID>/
│   ├── page.md             # raw document (fallback)
│   ├── rules.md            # per-page extracted rules (preferred)
│   └── *.ast.json          # AST JSON files
```

## Priority Order

| Priority | File Path | Description | When Used |
|----------|-----------|-------------|-----------|
| 1st (best) | `_all.rules.md` | Consolidated rules from ALL sources, deduplicated, sorted | After batch rules-extraction |
| 2nd (preferred) | `<PAGE_ID>/rules.md` | Compact pre-extracted rules per page | After per-page rules-extraction |
| 3rd (fallback) | `<PAGE_ID>/page.md` | Raw full document | Before rules extraction, or if extraction failed |

**If `_all.rules.md` exists**, read ONLY that file -- it contains all rules from all sources in one consolidated, deduplicated table. This is the most token-efficient option.

## Available Indexes

| Index | Path | Content |
|-------|------|---------|
| Patterns | `governance/indexes/patterns/` | Design pattern rules and examples |
| Standards | `governance/indexes/standards/` | Architectural standards |
| Security | `governance/indexes/security/` | Security guidelines and controls |

## Usage

To query an index:
1. List contents in `governance/indexes/<index>/`
2. If `_all.rules.md` exists → read only that
3. Otherwise, for each `<PAGE_ID>/` subfolder: prefer `rules.md`, fall back to `page.md`
4. Read standalone `rules.md` in index root if present
5. Use the selected content as the knowledge base for validation

## Example

```
# List contents in patterns index
governance/indexes/patterns/
├── _all.rules.md                   # consolidated rules (BEST - read only this if present)
├── rules.md                        # standalone hand-written rules
├── 123456789/
│   ├── page.md                     # raw document
│   ├── rules.md                    # per-page extracted rules (preferred)
│   └── diagram1.ast.json           # AST JSON
└── 987654321/
    ├── page.md
    └── rules.md

# Reading strategy when _all.rules.md EXISTS:
# ✅ Read _all.rules.md              (consolidated, ~400 tokens for all rules)
# ⏭️ Skip everything else            (_all.rules.md already contains all rules)

# Reading strategy when _all.rules.md DOES NOT EXIST:
# ✅ Read 123456789/rules.md          (compact table, ~200 tokens)
# ⏭️ Skip 123456789/page.md           (rules.md preferred)
# ✅ Read 987654321/rules.md          (compact table)
# ⏭️ Skip 987654321/page.md           (rules.md preferred)
# ✅ Read rules.md                    (standalone, always read)
```

## Output

Combined rules content from the index, used by validation agents to check architecture documents.

## Incremental Reading Mode (for large rule sets)

When `_all.rules.md` grows large, loading it entirely alongside the architecture document may overflow the context window. Use incremental reading to ensure ALL rules are checked.

### When to use incremental mode

1. Estimate combined context: `(chars in _all.rules.md + chars in page.md) / 4`
2. If combined estimate > **80K tokens** → use incremental mode
3. If combined estimate <= 80K tokens → use standard single-pass mode (no change)

### Incremental mode steps

1. **Read page.md** once (stays in working memory throughout validation)
2. **Write report shell** to the output path with placeholder header and table headers (no data rows yet)
3. **Count total rules** in `_all.rules.md` by counting table rows (read just the header area to get the count without loading all content)
4. **Process rules in batches of 50**:
   a. Read rules R-001 through R-050 from `_all.rules.md` (using line offset/limit to read only those rows)
   b. Validate each rule against page.md, citing Rule ID + evidence
   c. **Append finding rows directly to the report file** on disk (not a separate partial file)
   d. Release the batch from context
   e. Read next batch: R-051 through R-100
   f. Repeat until ALL rules have been processed
5. **Finalize report**:
   a. Scan the report file for status column values -- count PASS / ERROR / WARN rows
   b. Calculate score
   c. Update the header placeholders with final score and status
   d. Append remaining sections (errors summary, recommendations)

### Key principles

- page.md is read ONCE and kept in context
- Rules are read in batches -- each batch fits alongside page.md
- Finding rows are appended directly to the report file on disk -- no separate partial file needed
- The finalize step only scans for status counts, not full evidence re-read
- ALL rules are checked -- nothing is skipped or deprioritized
- The batch size (50) can be adjusted: use smaller batches for very large documents

## Important

- Priority: `_all.rules.md` > `<PAGE_ID>/rules.md` > `<PAGE_ID>/page.md`
- Always prefer `<PAGE_ID>/rules.md` over `<PAGE_ID>/page.md` when both exist
- Read standalone `rules.md` in index root (no subfolder)
- The `.rules.md` files contain the same governance rules in a compact markdown table (~90% fewer tokens)
- If a per-page `rules.md` seems incomplete or empty, fall back to `page.md` for that page
- Each page may contain different patterns/standards/controls
- The validation agent uses ALL indexed content for checking
