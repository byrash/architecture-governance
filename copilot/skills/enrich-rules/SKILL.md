---
name: enrich-rules
category: utility
description: LLM-powered rule enrichment — generates expanded synonyms, regex patterns, section hints, and co-occurrence groups for each governance rule. Produces rules-enriched.json for deterministic scoring. Use when asked to enrich rules after indexing.
---

# Rule Enrichment (LLM-Assisted)

Enriches hand-authored governance rules with LLM-generated detection patterns to enable deterministic scoring. The enriched output is cached and only regenerated when rules change.

## When to Use

- After indexing pages and extracting rules (when `_all.rules.md` exists)
- When the UI shows "Enrich rules for {category} index"
- As part of index preparation (Process 1) via `@governance-agent Prepare index <category>` in VS Code Chat, or CLI (`make enrich-rules INDEX=<category>`)

## Workflow

1. **Check staleness**: Run `python -m ingest.enrich_rules --check --index {category}` to see if enrichment is needed
2. **Read rules**: Read `governance/indexes/{category}/_all.rules.md`
3. **Generate enrichment**: For each rule, produce the structured fields below
4. **Write output**: Write `governance/indexes/{category}/rules-enriched.json`

## Per-Rule Enrichment Schema

For each rule in `_all.rules.md`, generate:

```json
{
  "rule_id": "R-PROTO-a3f2c1",
  "rule_name": "Secure transport",
  "synonyms": ["TLS", "SSL", "encrypted", "secure channel", "transport security", "HTTPS", "certificate", "mTLS", "end-to-end encryption", "wire encryption"],
  "evidence_patterns": [
    "(?i)\\ball\\s+(communication|traffic)\\s+.*\\b(encrypted|TLS|HTTPS)\\b",
    "(?i)\\btransport\\s+layer\\s+security\\b",
    "(?i)\\bmtls\\b.*\\benforced\\b",
    "(?i)\\bcertificate\\s+(pinning|rotation|management)\\b",
    "(?i)\\bend.to.end\\s+encrypt\\b"
  ],
  "negation_patterns": [
    "(?i)\\b(plain\\s*text|unencrypted|no\\s+TLS)\\b",
    "(?i)\\bHTTP\\b(?!S)",
    "(?i)\\b(disabled|removed)\\s+encryption\\b"
  ],
  "deferral_patterns": [
    "(?i)\\b(TBD|planned|future|backlog)\\b.*\\b(TLS|encryption|transport)\\b",
    "(?i)\\btransport\\s+security\\b.*\\b(Q[1-4]|next\\s+sprint)\\b",
    "(?i)\\b(will|plan\\s+to)\\s+(add|implement)\\s+.*\\bTLS\\b"
  ],
  "section_hints": ["## Security", "## Network", "## Transport", "## Infrastructure"],
  "co_occurrence_groups": [
    ["TLS", "certificate", "port 443"],
    ["mTLS", "service mesh", "sidecar"],
    ["HTTPS", "API gateway", "SSL termination"]
  ]
}
```

## Output Format

Write `governance/indexes/{category}/rules-enriched.json`:

```json
{
  "fingerprint": "<md5 of _all.rules.md first 64KB>",
  "category": "security",
  "enriched_at": "2025-01-15T10:30:00Z",
  "rules": [
    { "rule_id": "...", "rule_name": "...", "synonyms": [...], ... }
  ]
}
```

## Important Notes

- The `fingerprint` field must match the current `_all.rules.md` content hash — this is how staleness is detected
- Generate 10-15 synonyms per rule (beyond the hand-authored keywords)
- Generate 5 evidence regex patterns, 3 negation patterns, 3 deferral patterns
- Section hints should be markdown heading patterns where evidence typically appears
- Co-occurrence groups should be sets of 3+ terms that co-occur when truly satisfied
- If enrichment already exists and fingerprint matches, skip (already current)
