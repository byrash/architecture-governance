---
name: verbose-logging
category: utility
description: Shared verbose logging templates for all agents. Read this skill to get the correct status announcement format for your agent. Use when instructed to announce step progress.
---

# Verbose Logging Templates

Each agent has its own logging format. Find your agent name below and use the corresponding templates for all status announcements.

**CRITICAL**: Announce every action you take. The user needs to see what's happening at each step. Use the templates below as formatting guides -- replace `<placeholders>` with actual values.

---

## governance-agent

### Watcher Webhook

After each step announcement below, also POST a progress update to the watcher server so the UI shows live progress. See the governance-agent instructions for the curl command format. Use `|| true` so failures are silent.

### Pipeline Start (Validation Mode)
```
═══════════════════════════════════════════════════════════════════
🏛️ GOVERNANCE-AGENT: Starting Governance Pipeline
═══════════════════════════════════════════════════════════════════
   Page ID: <PAGE_ID>
   Model: <actual model running this agent>
   Pipeline Mode: Full Validation
   Steps: Verify → Claims → Score → Patterns → Standards → Security → Merge → HTML → Post
═══════════════════════════════════════════════════════════════════
```

### Pipeline Start (Index Preparation — Single)
```
═══════════════════════════════════════════════════════════════════
🏛️ GOVERNANCE-AGENT: Starting Index Preparation
═══════════════════════════════════════════════════════════════════
   Category: <CATEGORY>
   Model: <actual model running this agent>
   Pipeline Mode: Index Preparation
   Steps: Discover → Extract (per page) → Merge → Enrich
═══════════════════════════════════════════════════════════════════
```

### Pipeline Start (Index Preparation — All)
```
═══════════════════════════════════════════════════════════════════
🏛️ GOVERNANCE-AGENT: Starting Index Preparation (All)
═══════════════════════════════════════════════════════════════════
   Categories: patterns, standards, security
   Model: <actual model running this agent>
   Pipeline Mode: Index Preparation (all indexes)
   Steps: For each index → Discover → Extract → Merge → Enrich
═══════════════════════════════════════════════════════════════════
```

### Step Start/Complete
```
───────────────────────────────────────────────────
🏛️ GOVERNANCE-AGENT: Step <N>/10 - <Action Description>
───────────────────────────────────────────────────
   Action: <what is being done>
   Target Agent/Skill: <name>
   Expected Output: <file path>
───────────────────────────────────────────────────
```

```
───────────────────────────────────────────────────
🏛️ GOVERNANCE-AGENT: Step <N>/10 - <Step Name> Complete
───────────────────────────────────────────────────
   Status: ✅ SUCCESS / ❌ FAILED
   Output: <file path>
   Score: <X>/100 (if applicable)
───────────────────────────────────────────────────
```

### Merge Step (Step 8)
```
───────────────────────────────────────────────────
🏛️ GOVERNANCE-AGENT: Step 8/10 - Merge Complete
───────────────────────────────────────────────────
   Scores Extracted:
   - Patterns Score: <X>/100
   - Standards Score: <X>/100
   - Security Score: <X>/100
   Calculation:
   - Patterns: <X> × 0.30 = <Y>
   - Standards: <X> × 0.30 = <Y>
   - Security: <X> × 0.40 = <Y>
   OVERALL SCORE: <TOTAL>/100
───────────────────────────────────────────────────
```

### Pipeline Complete
```
═══════════════════════════════════════════════════════════════════
✅ GOVERNANCE-AGENT: Pipeline Complete
═══════════════════════════════════════════════════════════════════
   Page ID: <PAGE_ID>
   Model: <actual model that ran this agent>
   RESULTS:
   ├── Patterns:  <X>/100 (weight: 30%)
   ├── Standards: <X>/100 (weight: 30%)
   ├── Security:  <X>/100 (weight: 40%)
   └── OVERALL:   <TOTAL>/100
   STATUS: ✅ PASS (≥70) / ❌ FAIL (<70)
   OUTPUT FILES:
   ├── Page:     governance/output/<PAGE_ID>/page.md
   ├── Patterns: governance/output/<PAGE_ID>-patterns-report.md
   ├── Standards: governance/output/<PAGE_ID>-standards-report.md
   ├── Security: governance/output/<PAGE_ID>-security-report.md
   ├── Merged:   governance/output/<PAGE_ID>-governance-report.md
   └── Dashboard: governance/output/<PAGE_ID>-governance-report.html
═══════════════════════════════════════════════════════════════════
```

### Error
```
───────────────────────────────────────────────────
❌ GOVERNANCE-AGENT: Error at Step <N>
───────────────────────────────────────────────────
   Step: <step name>
   Agent/Skill: <name>
   Error: <error message>
   Action: <what will be attempted next>
───────────────────────────────────────────────────
```

---

## patterns-agent

### Starting
```
═══════════════════════════════════════════════════════════════════
🔷 PATTERNS-AGENT: Starting Pattern Validation
═══════════════════════════════════════════════════════════════════
   Document: governance/output/<PAGE_ID>/page.md
   Model: <actual model running this agent>
   Index Folder: governance/indexes/patterns/
   Output: governance/output/<PAGE_ID>-patterns-report.md
═══════════════════════════════════════════════════════════════════
```

### Step Start/Complete
```
───────────────────────────────────────────────────
🔷 PATTERNS-AGENT: Phase <N>/4 - <Action Description>
───────────────────────────────────────────────────
   Action: <what is being done>
   Tool: <tool name>
   Details: <relevant details>
───────────────────────────────────────────────────
```

```
───────────────────────────────────────────────────
🔷 PATTERNS-AGENT: Phase <N>/4 - <Phase Name> Complete
───────────────────────────────────────────────────
   Status: ✅ SUCCESS
   Results: <summary>
───────────────────────────────────────────────────
```

### Completion
```
═══════════════════════════════════════════════════════════════════
✅ PATTERNS-AGENT: Validation Complete
═══════════════════════════════════════════════════════════════════
   Document: governance/output/<PAGE_ID>/page.md
   Model: <actual model that ran this agent>
   RESULTS:
   ├── Status: <PASS/FAIL>
   ├── Score: <X>/100
   ├── Patterns checked: <count>
   │   ├── PASS:  <count>
   │   ├── ERROR: <count>
   │   └── WARN:  <count>
   ├── Anti-patterns: <count detected>
   └── Skills used: <list of discovered skills>
   OUTPUT:
   └── Report: governance/output/<PAGE_ID>-patterns-report.md
═══════════════════════════════════════════════════════════════════
```

### Error
```
───────────────────────────────────────────────────
❌ PATTERNS-AGENT: Error at Phase <N>
───────────────────────────────────────────────────
   Phase: <phase name>
   Tool/Skill: <name>
   Error: <error message>
   Action: <what will be attempted next>
───────────────────────────────────────────────────
```

---

## standards-agent

### Starting
```
═══════════════════════════════════════════════════════════════════
📋 STANDARDS-AGENT: Starting Standards Validation
═══════════════════════════════════════════════════════════════════
   Document: governance/output/<PAGE_ID>/page.md
   Model: <actual model running this agent>
   Index Folder: governance/indexes/standards/
   Output: governance/output/<PAGE_ID>-standards-report.md
═══════════════════════════════════════════════════════════════════
```

### Step Start/Complete
```
───────────────────────────────────────────────────
📋 STANDARDS-AGENT: Phase <N>/4 - <Action Description>
───────────────────────────────────────────────────
   Action: <what is being done>
   Tool: <tool name>
   Details: <relevant details>
───────────────────────────────────────────────────
```

```
───────────────────────────────────────────────────
📋 STANDARDS-AGENT: Phase <N>/4 - <Phase Name> Complete
───────────────────────────────────────────────────
   Status: ✅ SUCCESS
   Results: <summary>
───────────────────────────────────────────────────
```

### Completion
```
═══════════════════════════════════════════════════════════════════
✅ STANDARDS-AGENT: Validation Complete
═══════════════════════════════════════════════════════════════════
   Document: governance/output/<PAGE_ID>/page.md
   Model: <actual model that ran this agent>
   RESULTS:
   ├── Status: <PASS/FAIL>
   ├── Score: <X>/100
   ├── Standards checked: <count>
   │   ├── PASS:  <count>
   │   ├── ERROR: <count>
   │   └── WARN:  <count>
   └── Skills used: <list of discovered skills>
   OUTPUT:
   └── Report: governance/output/<PAGE_ID>-standards-report.md
═══════════════════════════════════════════════════════════════════
```

### Error
```
───────────────────────────────────────────────────
❌ STANDARDS-AGENT: Error at Phase <N>
───────────────────────────────────────────────────
   Phase: <phase name>
   Tool/Skill: <name>
   Error: <error message>
   Action: <what will be attempted next>
───────────────────────────────────────────────────
```

---

## security-agent

### Starting
```
═══════════════════════════════════════════════════════════════════
🔒 SECURITY-AGENT: Starting Security Validation
═══════════════════════════════════════════════════════════════════
   Document: governance/output/<PAGE_ID>/page.md
   Model: <actual model running this agent>
   Index Folder: governance/indexes/security/
   Output: governance/output/<PAGE_ID>-security-report.md
═══════════════════════════════════════════════════════════════════
```

### Step Start/Complete
```
───────────────────────────────────────────────────
🔒 SECURITY-AGENT: Phase <N>/5 - <Action Description>
───────────────────────────────────────────────────
   Action: <what is being done>
   Tool: <tool name>
   Details: <relevant details>
───────────────────────────────────────────────────
```

```
───────────────────────────────────────────────────
🔒 SECURITY-AGENT: Phase <N>/5 - <Phase Name> Complete
───────────────────────────────────────────────────
   Status: ✅ SUCCESS
   Results: <summary>
───────────────────────────────────────────────────
```

### Completion
```
═══════════════════════════════════════════════════════════════════
✅ SECURITY-AGENT: Validation Complete
═══════════════════════════════════════════════════════════════════
   Document: governance/output/<PAGE_ID>/page.md
   Model: <actual model that ran this agent>
   RESULTS:
   ├── Status: <PASS/FAIL>
   ├── Score: <X>/100
   ├── Risk Level: <LOW/MEDIUM/HIGH/CRITICAL>
   ├── Controls checked: <count>
   │   ├── PASS:  <count>
   │   ├── ERROR: <count>
   │   └── WARN:  <count>
   ├── Vulnerabilities: <count or "none">
   └── Skills used: <list of discovered skills>
   OUTPUT:
   └── Report: governance/output/<PAGE_ID>-security-report.md
═══════════════════════════════════════════════════════════════════
```

### Error
```
───────────────────────────────────────────────────
❌ SECURITY-AGENT: Error at Phase <N>
───────────────────────────────────────────────────
   Phase: <phase name>
   Tool/Skill: <name>
   Error: <error message>
   Action: <what will be attempted next>
───────────────────────────────────────────────────
```
