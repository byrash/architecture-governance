---
name: security-validate
description: Validate architecture document against security rules. Use when asked to check security, validate threat models, or verify security compliance.
---

# Security Validation

Validate architecture document against security guidelines.

## Inputs

1. **Document**: `governance/output/architecture.md`
2. **Rules**: `governance/indexes/security/rules.md`

## Instructions

1. Read the architecture document
2. Read the security rules
3. For each security control, check if addressed
4. Look for vulnerabilities (hardcoded secrets, etc.)
5. Calculate score and write report

## Validation Criteria

| Rule ID | Security Control | Severity | Look For |
|---------|-----------------|----------|----------|
| SEC-001 | Authentication | Critical | OAuth, JWT, SSO, login mechanisms |
| SEC-002 | Authorization | Critical | RBAC, permissions, access control |
| SEC-003 | Data Encryption | Critical | TLS, HTTPS, AES, encryption at rest |
| SEC-004 | Secrets Management | Critical | Vault, secrets manager, no hardcoded secrets |
| SEC-005 | Input Validation | High | Sanitization, validation, parameterized queries |
| SEC-006 | SQL Injection Prevention | Critical | ORM, prepared statements, parameterized |
| SEC-007 | Audit Logging | High | Security logs, audit trail, SIEM |
| SEC-008 | Rate Limiting | Medium | Throttling, rate limits, DDoS protection |
| SEC-009 | CORS | Medium | CORS configuration, allowed origins |

## Vulnerabilities to Detect

- Hardcoded passwords/secrets
- Missing encryption
- No authentication mentioned
- Direct database access without validation

## Scoring

- Critical control met: +15 points
- Critical control missing: 0 points (MAJOR issue)
- High control met: +10 points
- Medium control met: +5 points
- Vulnerability found: -20 points each
- Base score: Start at 0, max 100

## Output

Write to `governance/output/security-report.md`:

```markdown
# Security Validation Report

**Generated**: [timestamp]
**Document**: governance/output/architecture.md
**Score**: X/100
**Status**: ✅ PASS / ⚠️ WARN / ❌ FAIL

## Summary

| Status | Count |
|--------|-------|
| ✅ Passed | N |
| ❌ Failed | N |
| 🚨 Critical | N |

## Authentication & Authorization

### SEC-001: Authentication
- **Status**: ✅ PASS / ❌ FAIL
- **Severity**: Critical
- **Evidence**: [quote or describe what you found]
- **Risk**: [what could go wrong if missing]
- **Recommendation**: [if failed, what to add]

[... repeat for each control ...]

## Vulnerabilities Detected

[List any security issues found]

## Risk Assessment

[Overall security posture analysis]

## Recommendations

[Prioritized security improvements]
```
