---
name: extract-claims
category: utility
description: LLM-powered page claims extraction — generates structured per-topic claims from a page.md document for deterministic scoring. Produces page-claims.json. Use during validation before scoring.
---

# Page Claims Extraction (LLM-Assisted)

Extracts structured claims from a page.md document, producing a per-topic assessment that the deterministic scorer can match against enriched rules. Claims are cached by page fingerprint.

## When to Use

- During validation, before running the deterministic scorer
- When `page-claims.json` is missing or stale (page.md changed)
- The governance-agent triggers this automatically during validation

## Workflow

1. **Check staleness**: Run `python -m ingest.extract_claims --check --page-id <PAGE_ID>` to see if extraction is needed
2. **Get AST facts**: Run `python -m ingest.extract_claims --facts --page-id <PAGE_ID>` to get deterministic AST facts (protocols, roles, zones)
3. **Read page**: Read `governance/output/<PAGE_ID>/page.md`
4. **Read topic list**: Read the rule names from all `_all.rules.md` files in governance/indexes/ to know what topics to look for
5. **Generate claims**: For each topic, produce a structured claim
6. **Write output**: Write `governance/output/<PAGE_ID>/page-claims.json`

## Per-Topic Claim Schema

For each governance topic (derived from rule names in all indexes), generate:

```json
{
  "topic": "authentication",
  "rule_ids": ["R-ROLE-a1b2c3"],
  "status": "implemented",
  "method": "OAuth 2.0 with JWT via Auth0",
  "evidence_line": 42,
  "section": "## Security Architecture",
  "quote": "All API requests are authenticated via OAuth 2.0, returning JWT tokens signed with RS256"
}
```

**Status values:**
- `implemented` — clear evidence the topic is addressed
- `deferred` — explicitly mentioned as planned/TBD/future
- `absent` — no mention found anywhere in the document
- `mentioned` — referenced but without implementation details (weak evidence)

## Output Format

Write `governance/output/{PAGE_ID}/page-claims.json`:

```json
{
  "page_id": "12345",
  "fingerprint": "<md5 of page.md first 64KB>",
  "extracted_at": "2025-01-15T10:30:00Z",
  "claims": [
    { "topic": "...", "rule_ids": [...], "status": "...", ... }
  ],
  "ast_facts": {
    "protocols": { "HTTPS": 4, "gRPC": 2 },
    "roles": { "gateway": 1, "datastore": 2, "queue": 1 },
    "zones": { "external": 1, "internal": 1, "dmz": 1 }
  },
  "contradictions": [
    {
      "text_claim": "All communication uses TLS",
      "ast_evidence": "edge user_service->cache has no protocol",
      "severity": "medium"
    }
  ]
}
```

## Important Notes

- The `fingerprint` must match the current page.md content hash for cache validity
- The `ast_facts` section is produced by the deterministic helper (`python -m ingest.extract_claims --facts`)
- Look for contradictions between text claims and AST evidence (e.g., "all traffic encrypted" but AST shows unencrypted edges)
- Always include a `quote` with the exact text from page.md that supports the claim
- If no evidence found, set status to `absent` with null quote/section/evidence_line
