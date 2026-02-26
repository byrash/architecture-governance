---
name: markdown-to-html
category: reporting
description: Convert governance report to HTML dashboard. Use when asked to generate HTML or create dashboard.
---

# Markdown to HTML Dashboard

Generate HTML dashboard from governance report using **incremental generation** -- read one source at a time, write HTML in phases.

## Input

- `governance/output/<PAGE_ID>-governance-report.md` (compact summary with scores)
- `governance/output/<PAGE_ID>-patterns-report.md` (detailed findings)
- `governance/output/<PAGE_ID>-standards-report.md` (detailed findings)
- `governance/output/<PAGE_ID>-security-report.md` (detailed findings)

## Instructions (Incremental -- one source at a time)

### Phase 1: Write HTML shell from governance report

1. Read `<PAGE_ID>-governance-report.md` (compact -- scores, critical issues, recommendations)
2. Write `<PAGE_ID>-governance-report.html` with:
   - Full `<head>` with embedded CSS (see Styles below)
   - Hero header with gradient, page title, generated timestamp, and overall verdict badge
   - Score ring gauges row: one large ring for Overall score, three smaller rings for Patterns / Standards / Security
   - Executive Summary callout card
   - Score Breakdown table with progress bars per category
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
.hero .verdict {
    display: inline-flex; align-items: center; gap: 8px;
    margin-top: 16px; padding: 8px 20px; border-radius: 999px;
    font-weight: 600; font-size: 0.95rem; backdrop-filter: blur(8px);
}
.verdict.pass { background: rgba(16,185,129,0.25); border: 1px solid rgba(16,185,129,0.4); }
.verdict.warn { background: rgba(245,158,11,0.25); border: 1px solid rgba(245,158,11,0.4); }
.verdict.fail { background: rgba(239,68,68,0.25); border: 1px solid rgba(239,68,68,0.4); }

/* ── Score rings ──────────────────────────────── */
.score-rings { display: flex; gap: 24px; justify-content: center; margin-bottom: 32px; flex-wrap: wrap; }
.ring-card {
    background: white; border-radius: var(--radius); padding: 28px 24px;
    box-shadow: var(--shadow); text-align: center; min-width: 180px; flex: 1;
    transition: transform 0.2s, box-shadow 0.2s;
}
.ring-card:hover { transform: translateY(-2px); box-shadow: var(--shadow-lg); }
.ring-card.main { flex: 1.4; }
.ring-wrap { position: relative; width: 120px; height: 120px; margin: 0 auto 16px; }
.ring-card.main .ring-wrap { width: 150px; height: 150px; }
.ring-svg { transform: rotate(-90deg); width: 100%; height: 100%; }
.ring-bg { fill: none; stroke: var(--gray-200); }
.ring-fg { fill: none; stroke-linecap: round; transition: stroke-dashoffset 0.8s ease; }
.ring-fg.pass { stroke: var(--green); }
.ring-fg.warn { stroke: var(--yellow); }
.ring-fg.fail { stroke: var(--red); }
.ring-value {
    position: absolute; inset: 0; display: flex; flex-direction: column;
    align-items: center; justify-content: center;
}
.ring-value .number { font-size: 2rem; font-weight: 700; line-height: 1; }
.ring-card.main .ring-value .number { font-size: 2.8rem; }
.ring-value .label { font-size: 0.75rem; color: var(--gray-500); text-transform: uppercase; letter-spacing: 0.05em; margin-top: 2px; }
.ring-card h3 { font-size: 0.85rem; font-weight: 600; color: var(--gray-500); text-transform: uppercase; letter-spacing: 0.05em; }

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

/* ── Score breakdown table ────────────────────── */
table { width: 100%; border-collapse: separate; border-spacing: 0; }
th { background: var(--gray-50); font-weight: 600; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.04em; color: var(--gray-500); }
th, td { padding: 12px 16px; text-align: left; }
tbody tr { border-bottom: 1px solid var(--gray-100); }
tbody tr:last-child { border-bottom: none; }
tbody tr:hover { background: var(--gray-50); }
.score-bar { display: flex; align-items: center; gap: 10px; }
.score-bar-track { flex: 1; height: 8px; background: var(--gray-200); border-radius: 4px; overflow: hidden; }
.score-bar-fill { height: 100%; border-radius: 4px; transition: width 0.6s ease; }
.score-bar-fill.pass { background: var(--green); }
.score-bar-fill.warn { background: var(--yellow); }
.score-bar-fill.fail { background: var(--red); }
.score-num { font-weight: 600; min-width: 42px; text-align: right; }
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

/* ── Status pills in tables ───────────────────── */
.status-pill {
    display: inline-block; padding: 2px 10px; border-radius: 999px;
    font-size: 0.8rem; font-weight: 600; text-transform: uppercase;
}
.status-pill.pass { background: var(--green-bg); color: var(--green); }
.status-pill.error { background: var(--red-bg); color: var(--red); }
.status-pill.warn { background: var(--yellow-bg); color: var(--yellow); }

/* ── Footer ───────────────────────────────────── */
.report-footer {
    text-align: center; padding: 24px; color: var(--gray-500);
    font-size: 0.8rem; margin-top: 24px; border-top: 1px solid var(--gray-200);
}

/* ── Responsive ───────────────────────────────── */
@media (max-width: 768px) {
    .score-rings { flex-direction: column; align-items: center; }
    .ring-card { min-width: unset; width: 100%; max-width: 300px; }
    .hero { padding: 24px; }
}
```

## HTML Structure Reference

### Hero Header

```html
<div class="hero">
    <h1>🏛️ Architecture Governance Report</h1>
    <div class="meta">Page ID: <PAGE_ID> · Generated: <TIMESTAMP></div>
    <div class="verdict [pass/warn/fail]">
        [✅ PASS / ⚠️ NEEDS WORK / ❌ FAILING] — Overall Score: [X]/100
    </div>
</div>
```

### Score Ring Gauges

Use SVG circle with `stroke-dasharray` and `stroke-dashoffset` for the gauge ring. The circumference for a circle with `r=50` centered at `60,60` is ~314. Set `stroke-dasharray="314"` and `stroke-dashoffset` to `314 - (score/100 * 314)`.

```html
<div class="score-rings">
    <div class="ring-card main">
        <div class="ring-wrap">
            <svg class="ring-svg" viewBox="0 0 120 120">
                <circle class="ring-bg" cx="60" cy="60" r="50" stroke-width="10"/>
                <circle class="ring-fg [pass/warn/fail]" cx="60" cy="60" r="50" stroke-width="10"
                    stroke-dasharray="314" stroke-dashoffset="[314 - score/100*314]"/>
            </svg>
            <div class="ring-value">
                <span class="number">[X]</span>
                <span class="label">/ 100</span>
            </div>
        </div>
        <h3>Overall Score</h3>
    </div>
    <!-- Repeat for Patterns (30%), Standards (30%), Security (40%) -->
    <div class="ring-card">
        <div class="ring-wrap">
            <svg class="ring-svg" viewBox="0 0 120 120">
                <circle class="ring-bg" cx="60" cy="60" r="50" stroke-width="8"/>
                <circle class="ring-fg [pass/warn/fail]" cx="60" cy="60" r="50" stroke-width="8"
                    stroke-dasharray="314" stroke-dashoffset="[314 - score/100*314]"/>
            </svg>
            <div class="ring-value">
                <span class="number">[X]</span>
                <span class="label">/ 100</span>
            </div>
        </div>
        <h3>Patterns <small style="font-weight:400;color:var(--gray-500)">(30%)</small></h3>
    </div>
</div>
```

### Executive Summary Card

```html
<div class="exec-summary">
    [2-3 sentences from the governance report executive summary]
</div>
```

### Score Breakdown Table with Progress Bars

```html
<div class="section">
    <h2><span class="icon">📊</span> Score Breakdown</h2>
    <table>
        <thead><tr><th>Category</th><th>Score</th><th>Weight</th><th>Weighted</th><th>Checks</th><th>Errors</th><th>Warnings</th></tr></thead>
        <tbody>
            <tr>
                <td>Patterns</td>
                <td><div class="score-bar"><div class="score-bar-track"><div class="score-bar-fill [pass/warn/fail]" style="width:[X]%"></div></div><span class="score-num">[X]</span></div></td>
                <td>30%</td><td>[X.X]</td><td>[n]</td><td>[n]</td><td>[n]</td>
            </tr>
            <!-- Standards, Security rows -->
            <tr class="total-row">
                <td>Total</td><td></td><td></td><td><strong>[X]/100</strong></td><td><strong>[n]</strong></td><td><strong>[n]</strong></td><td><strong>[n]</strong></td>
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

Apply status pill based on status:

```html
<tr>
    <td>Pattern Name</td>
    <td>R-001</td>
    <td>source.md</td>
    <td><span class="status-pill pass">PASS</span></td>
    <td>Evidence quote</td>
</tr>
<tr>
    <td>Pattern Name</td>
    <td>R-002</td>
    <td>source.md</td>
    <td><span class="status-pill error">ERROR</span></td>
    <td>NOT FOUND</td>
</tr>
```

### Footer

```html
<div class="report-footer">
    Generated by Architecture Governance · <TIMESTAMP>
</div>
```

## Styling Rules

- Score >= 70: `pass` class (green)
- Score 50-69: `warn` class (yellow)
- Score < 50: `fail` class (red)
