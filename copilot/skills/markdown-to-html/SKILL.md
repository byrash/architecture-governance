---
name: markdown-to-html
category: reporting
description: Convert governance report to HTML dashboard. Use when asked to generate HTML or create dashboard.
---

# Markdown to HTML Dashboard

Generate HTML dashboard from governance report using **incremental generation** -- read one source at a time, write HTML in phases.

## Input

- `governance/output/<PAGE_ID>-governance-report.md` (compact summary with action tiers)
- `governance/output/<PAGE_ID>-patterns-report.md` (detailed findings)
- `governance/output/<PAGE_ID>-standards-report.md` (detailed findings)
- `governance/output/<PAGE_ID>-security-report.md` (detailed findings)

## Instructions (Incremental -- one source at a time)

### Phase 1: Write HTML shell from governance report

1. Read `<PAGE_ID>-governance-report.md` (compact -- action summary, critical issues, recommendations)
2. Write `<PAGE_ID>-governance-report.html` with:
   - Full `<head>` with embedded CSS (see Styles below)
   - Hero header with gradient, page title, generated timestamp, and action headline
   - Action summary bar (horizontal stacked bar showing proportions of each tier)
   - Five action count cards in a row (Compliant, Verify, Investigate, Plan, Remediate)
   - Executive Summary callout card
   - Actions by Category table (rows: category, columns: action tiers)
   - Critical Issues cards (red left-border, warning icon)
   - Quick Wins cards (green left-border, lightbulb icon)
   - Recommendations cards (blue left-border, arrow icon)
   - **Open** the Detailed Findings `<div>` but do NOT close `</body></html>` yet
3. Release the governance report from context

### Phase 2: Append patterns findings

1. Read `<PAGE_ID>-patterns-report.md`
2. Extract the Patterns Checked table rows and Anti-Patterns Check rows
3. Convert to HTML table rows
4. **Append** a `<details><summary>🔍 Pattern Validation <span class="finding-count">N checks</span></summary>...</details>` block to the HTML file
5. Release the patterns report from context

### Phase 3: Append standards findings

1. Read `<PAGE_ID>-standards-report.md`
2. Extract the Standards Checked table rows
3. Convert to HTML table rows
4. **Append** a `<details><summary>📐 Standards Validation <span class="finding-count">N checks</span></summary>...</details>` block to the HTML file
5. Release the standards report from context

### Phase 4: Append security findings

1. Read `<PAGE_ID>-security-report.md`
2. Extract the Security Controls Checked table rows and Vulnerability Scan rows
3. Convert to HTML table rows
4. **Append** a `<details><summary>🛡️ Security Validation <span class="finding-count">N checks</span></summary>...</details>` block to the HTML file
5. Release the security report from context

### Phase 5: Close HTML

Append closing tags to the HTML file:

```html
    </div><!-- end detailed findings -->
  </main>
</body>
</html>
```

## Output

Write to `governance/output/<PAGE_ID>-governance-report.html`

## Styles

Embed this CSS in the `<style>` tag:

```css
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

:root {
    --green: #10b981;
    --green-bg: #ecfdf5;
    --yellow: #f59e0b;
    --yellow-bg: #fffbeb;
    --orange: #f97316;
    --orange-bg: #fff7ed;
    --red: #ef4444;
    --red-bg: #fef2f2;
    --blue: #3b82f6;
    --blue-bg: #eff6ff;
    --purple: #8b5cf6;
    --gray-50: #f9fafb;
    --gray-100: #f3f4f6;
    --gray-200: #e5e7eb;
    --gray-300: #d1d5db;
    --gray-500: #6b7280;
    --gray-700: #374151;
    --gray-900: #111827;
    --shadow-sm: 0 1px 2px rgba(0,0,0,0.05);
    --shadow: 0 4px 6px -1px rgba(0,0,0,0.07), 0 2px 4px -2px rgba(0,0,0,0.05);
    --shadow-lg: 0 10px 25px -5px rgba(0,0,0,0.08), 0 8px 10px -6px rgba(0,0,0,0.04);
    --radius: 12px;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    line-height: 1.6; color: var(--gray-700); background: var(--gray-50);
}

main { max-width: 1100px; margin: 0 auto; padding: 0 24px 48px; }

/* ── Hero header ──────────────────────────────── */
.hero {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
    color: white; padding: 40px 48px; margin: -24px -24px 32px;
    position: relative; overflow: hidden;
}
.hero::after {
    content: ''; position: absolute; inset: 0;
    background: url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.05'%3E%3Ccircle cx='30' cy='30' r='2'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E");
}
.hero > * { position: relative; z-index: 1; }
.hero h1 { font-size: 1.75rem; font-weight: 700; margin-bottom: 4px; letter-spacing: -0.02em; }
.hero .meta { opacity: 0.85; font-size: 0.9rem; }
.hero .action-headline {
    margin-top: 16px; padding: 8px 20px; border-radius: 999px;
    font-weight: 600; font-size: 0.95rem; backdrop-filter: blur(8px);
    display: inline-flex; align-items: center; gap: 8px;
    background: rgba(255,255,255,0.15); border: 1px solid rgba(255,255,255,0.3);
}

/* ── Action summary bar ──────────────────────────── */
.action-summary-bar {
    display: flex; height: 14px; border-radius: 7px; overflow: hidden;
    margin-bottom: 24px; box-shadow: var(--shadow-sm);
}
.action-summary-bar .seg { transition: width 0.6s ease; }
.seg-compliant { background: var(--green); }
.seg-verify { background: var(--blue); }
.seg-investigate { background: var(--yellow); }
.seg-plan { background: var(--orange); }
.seg-remediate { background: var(--red); }

/* ── Action count cards row ──────────────────────── */
.action-cards { display: flex; gap: 16px; justify-content: center; margin-bottom: 32px; flex-wrap: wrap; }
.action-card {
    background: white; border-radius: var(--radius); padding: 20px 24px;
    box-shadow: var(--shadow); text-align: center; min-width: 140px; flex: 1;
    border-top: 4px solid var(--gray-200);
    transition: transform 0.2s, box-shadow 0.2s;
}
.action-card:hover { transform: translateY(-2px); box-shadow: var(--shadow-lg); }
.action-card .count { font-size: 2rem; font-weight: 700; line-height: 1; margin-bottom: 4px; }
.action-card .tier-label { font-size: 0.8rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--gray-500); }
.action-card.compliant { border-top-color: var(--green); }
.action-card.compliant .count { color: var(--green); }
.action-card.verify { border-top-color: var(--blue); }
.action-card.verify .count { color: var(--blue); }
.action-card.investigate { border-top-color: var(--yellow); }
.action-card.investigate .count { color: var(--yellow); }
.action-card.plan { border-top-color: var(--orange); }
.action-card.plan .count { color: var(--orange); }
.action-card.remediate { border-top-color: var(--red); }
.action-card.remediate .count { color: var(--red); }

/* ── Section cards ────────────────────────────── */
.section {
    background: white; border-radius: var(--radius); padding: 24px;
    box-shadow: var(--shadow-sm); margin-bottom: 20px;
    border: 1px solid var(--gray-200);
}
.section h2 {
    font-size: 1.1rem; font-weight: 600; color: var(--gray-900);
    margin-bottom: 16px; display: flex; align-items: center; gap: 10px;
}
.section h2 .icon { font-size: 1.3rem; }

/* ── Executive summary ────────────────────────── */
.exec-summary {
    background: linear-gradient(135deg, var(--blue-bg) 0%, #f0f4ff 100%);
    border: 1px solid rgba(59,130,246,0.15); border-radius: var(--radius);
    padding: 24px 28px; margin-bottom: 24px; font-size: 1rem; line-height: 1.7;
}
.exec-summary strong { color: var(--gray-900); }

/* ── Actions by category table ────────────────── */
table { width: 100%; border-collapse: separate; border-spacing: 0; }
th { background: var(--gray-50); font-weight: 600; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.04em; color: var(--gray-500); }
th, td { padding: 12px 16px; text-align: left; }
tbody tr { border-bottom: 1px solid var(--gray-100); }
tbody tr:last-child { border-bottom: none; }
tbody tr:hover { background: var(--gray-50); }
.count-cell { font-weight: 600; text-align: center; }
.count-cell.has-value { font-size: 1.1rem; }
.total-row { font-weight: 700; background: var(--gray-50); }
.total-row td { border-top: 2px solid var(--gray-200); }

/* ── Issue / Quick-win / Recommendation cards ─── */
.callout-list { display: flex; flex-direction: column; gap: 12px; }
.callout {
    display: flex; gap: 14px; padding: 16px 18px;
    border-radius: 10px; border-left: 4px solid transparent;
    font-size: 0.95rem; line-height: 1.55;
}
.callout .callout-icon { font-size: 1.2rem; flex-shrink: 0; margin-top: 1px; }
.callout.critical { background: var(--red-bg); border-left-color: var(--red); }
.callout.quickwin { background: var(--green-bg); border-left-color: var(--green); }
.callout.recommendation { background: var(--blue-bg); border-left-color: var(--blue); }

/* ── Collapsible findings ─────────────────────── */
.findings-section { margin-top: 32px; }
.findings-section h2 { margin-bottom: 16px; }
details {
    background: white; border: 1px solid var(--gray-200); border-radius: var(--radius);
    margin-bottom: 12px; overflow: hidden; box-shadow: var(--shadow-sm);
}
summary {
    cursor: pointer; padding: 16px 20px; font-weight: 600; font-size: 0.95rem;
    display: flex; align-items: center; gap: 10px; user-select: none;
    transition: background 0.15s;
}
summary:hover { background: var(--gray-50); }
summary::marker { content: ''; }
summary::before {
    content: '▶'; font-size: 0.7rem; color: var(--gray-500);
    transition: transform 0.2s; margin-right: 4px;
}
details[open] > summary::before { transform: rotate(90deg); }
.finding-count {
    margin-left: auto; background: var(--gray-100); color: var(--gray-500);
    padding: 2px 10px; border-radius: 999px; font-size: 0.8rem; font-weight: 500;
}
details .detail-body { padding: 0 20px 20px; }
details table { font-size: 0.9rem; }

/* ── Action pills in tables ──────────────────── */
.status-pill {
    display: inline-block; padding: 2px 10px; border-radius: 999px;
    font-size: 0.8rem; font-weight: 600; text-transform: uppercase;
}
.status-pill.compliant { background: var(--green-bg); color: var(--green); }
.status-pill.verify { background: var(--blue-bg); color: var(--blue); }
.status-pill.investigate { background: var(--yellow-bg); color: var(--yellow); }
.status-pill.plan { background: var(--orange-bg); color: var(--orange); }
.status-pill.remediate { background: var(--red-bg); color: var(--red); }

/* ── Footer ───────────────────────────────────── */
.report-footer {
    text-align: center; padding: 24px; color: var(--gray-500);
    font-size: 0.8rem; margin-top: 24px; border-top: 1px solid var(--gray-200);
}

/* ── Responsive ───────────────────────────────── */
@media (max-width: 768px) {
    .action-cards { flex-direction: column; align-items: center; }
    .action-card { min-width: unset; width: 100%; max-width: 300px; }
    .hero { padding: 24px; }
}
```

## HTML Structure Reference

### Hero Header

```html
<div class="hero">
    <h1>🏛️ Architecture Governance Report</h1>
    <div class="meta">Page ID: <PAGE_ID> · Generated: <TIMESTAMP></div>
    <div class="action-headline">
        [N] rules need remediation, [N] need investigation
    </div>
</div>
```

### Action Summary Bar

A horizontal stacked bar showing the proportion of each action tier. Calculate each segment width as `(count / total * 100)%`.

```html
<div class="action-summary-bar">
    <div class="seg seg-compliant" style="width:[X]%" title="Compliant: [N]"></div>
    <div class="seg seg-verify" style="width:[X]%" title="Verify: [N]"></div>
    <div class="seg seg-investigate" style="width:[X]%" title="Investigate: [N]"></div>
    <div class="seg seg-plan" style="width:[X]%" title="Plan: [N]"></div>
    <div class="seg seg-remediate" style="width:[X]%" title="Remediate: [N]"></div>
</div>
```

### Action Count Cards

```html
<div class="action-cards">
    <div class="action-card compliant">
        <div class="count">[N]</div>
        <div class="tier-label">Compliant</div>
    </div>
    <div class="action-card verify">
        <div class="count">[N]</div>
        <div class="tier-label">Verify</div>
    </div>
    <div class="action-card investigate">
        <div class="count">[N]</div>
        <div class="tier-label">Investigate</div>
    </div>
    <div class="action-card plan">
        <div class="count">[N]</div>
        <div class="tier-label">Plan</div>
    </div>
    <div class="action-card remediate">
        <div class="count">[N]</div>
        <div class="tier-label">Remediate</div>
    </div>
</div>
```

### Executive Summary Card

```html
<div class="exec-summary">
    [2-3 sentences from the governance report executive summary, focusing on actions needed]
</div>
```

### Actions by Category Table

```html
<div class="section">
    <h2><span class="icon">📊</span> Actions by Category</h2>
    <table>
        <thead><tr><th>Category</th><th>Compliant</th><th>Verify</th><th>Investigate</th><th>Plan</th><th>Remediate</th><th>Total</th></tr></thead>
        <tbody>
            <tr>
                <td>Patterns</td>
                <td class="count-cell">[n]</td><td class="count-cell">[n]</td><td class="count-cell">[n]</td><td class="count-cell">[n]</td><td class="count-cell">[n]</td><td class="count-cell"><strong>[n]</strong></td>
            </tr>
            <!-- Standards, Security rows -->
            <tr class="total-row">
                <td>Total</td>
                <td class="count-cell"><strong>[n]</strong></td><td class="count-cell"><strong>[n]</strong></td><td class="count-cell"><strong>[n]</strong></td><td class="count-cell"><strong>[n]</strong></td><td class="count-cell"><strong>[n]</strong></td><td class="count-cell"><strong>[n]</strong></td>
            </tr>
        </tbody>
    </table>
</div>
```

### Critical Issues / Quick Wins / Recommendations

```html
<div class="section">
    <h2><span class="icon">🚨</span> Critical Issues</h2>
    <div class="callout-list">
        <div class="callout critical"><span class="callout-icon">⚠️</span><div>[Issue description]</div></div>
    </div>
</div>

<div class="section">
    <h2><span class="icon">💡</span> Quick Wins</h2>
    <div class="callout-list">
        <div class="callout quickwin"><span class="callout-icon">✅</span><div>[Quick win description]</div></div>
    </div>
</div>

<div class="section">
    <h2><span class="icon">📋</span> Recommendations</h2>
    <div class="callout-list">
        <div class="callout recommendation"><span class="callout-icon">→</span><div>[Recommendation text]</div></div>
    </div>
</div>
```

### Finding Table Rows in Detail Sections

Apply action pill based on action tier:

```html
<tr>
    <td>Pattern Name</td>
    <td>R-001</td>
    <td>source.md</td>
    <td><span class="status-pill compliant">COMPLIANT</span></td>
    <td>Evidence quote</td>
</tr>
<tr>
    <td>Pattern Name</td>
    <td>R-002</td>
    <td>source.md</td>
    <td><span class="status-pill remediate">REMEDIATE</span></td>
    <td>NOT FOUND</td>
</tr>
```

### Footer

```html
<div class="report-footer">
    Generated by Architecture Governance · <TIMESTAMP>
</div>
```

## Action Tier Color Reference

- **Compliant**: green (`var(--green)`)
- **Verify**: blue (`var(--blue)`)
- **Investigate**: yellow (`var(--yellow)`)
- **Plan**: orange (`var(--orange)`)
- **Remediate**: red (`var(--red)`)
