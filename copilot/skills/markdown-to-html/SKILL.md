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
   - Header with page ID and timestamp
   - Score cards (overall, patterns, standards, security)
   - Executive Summary section
   - Score Breakdown table
   - Critical Issues section
   - Quick Wins section
   - Recommendations section
   - **Open** the Detailed Findings `<div>` but do NOT close `</body></html>` yet
3. Release the governance report from context

### Phase 2: Append patterns findings

1. Read `<PAGE_ID>-patterns-report.md`
2. Extract the Patterns Checked table rows and Anti-Patterns Check rows
3. Convert to HTML table rows
4. **Append** a `<details><summary>Pattern Validation</summary>...</details>` block to the HTML file
5. Release the patterns report from context

### Phase 3: Append standards findings

1. Read `<PAGE_ID>-standards-report.md`
2. Extract the Standards Checked table rows
3. Convert to HTML table rows
4. **Append** a `<details><summary>Standards Validation</summary>...</details>` block to the HTML file
5. Release the standards report from context

### Phase 4: Append security findings

1. Read `<PAGE_ID>-security-report.md`
2. Extract the Security Controls Checked table rows and Vulnerability Scan rows
3. Convert to HTML table rows
4. **Append** a `<details><summary>Security Validation</summary>...</details>` block to the HTML file
5. Release the security report from context

### Phase 5: Close HTML

Append closing tags to the HTML file:

```html
    </div><!-- end detailed findings -->
</body>
</html>
```

## Output

Write to `governance/output/<PAGE_ID>-governance-report.html`

## Styles

Embed this CSS in the `<style>` tag:

```css
* { box-sizing: border-box; margin: 0; padding: 0; }
body { 
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
    line-height: 1.6; color: #333; max-width: 1200px; 
    margin: 0 auto; padding: 20px; background: #f5f5f5; 
}
.header { 
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
    color: white; padding: 30px; border-radius: 10px; margin-bottom: 20px; 
}
.score-cards { 
    display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); 
    gap: 20px; margin-bottom: 20px; 
}
.card { 
    background: white; padding: 20px; border-radius: 10px; 
    box-shadow: 0 2px 10px rgba(0,0,0,0.1); text-align: center; 
}
.card.pass { border-left: 5px solid #10b981; }
.card.warn { border-left: 5px solid #f59e0b; }
.card.fail { border-left: 5px solid #ef4444; }
.card h3 { color: #666; font-size: 0.9em; text-transform: uppercase; }
.card .score { font-size: 2.5em; font-weight: bold; }
.card.pass .score { color: #10b981; }
.card.warn .score { color: #f59e0b; }
.card.fail .score { color: #ef4444; }
.section { 
    background: white; padding: 20px; border-radius: 10px; 
    box-shadow: 0 2px 10px rgba(0,0,0,0.1); margin-bottom: 20px; 
}
.section h2 { border-bottom: 2px solid #667eea; padding-bottom: 10px; margin-bottom: 15px; }
table { width: 100%; border-collapse: collapse; margin: 15px 0; }
th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
th { background: #f8f9fa; font-weight: 600; }
tr:hover { background: #f8f9fa; }
.pass-row { color: #10b981; }
.error-row { color: #ef4444; }
.warn-row { color: #f59e0b; }
.critical { background: #fef2f2; border-left: 4px solid #ef4444; padding: 15px; margin: 10px 0; border-radius: 5px; }
.quickwin { background: #f0fdf4; border-left: 4px solid #10b981; padding: 15px; margin: 10px 0; border-radius: 5px; }
.recommendation { background: #eff6ff; border-left: 4px solid #3b82f6; padding: 15px; margin: 10px 0; border-radius: 5px; }
details { margin: 10px 0; }
summary { cursor: pointer; padding: 12px; background: #f8f9fa; border-radius: 5px; font-weight: 600; }
summary:hover { background: #e9ecef; }
```

## HTML Structure Reference

Score cards section:

```html
<div class="score-cards">
    <div class="card [pass/warn/fail]">
        <h3>Overall</h3>
        <div class="score">[PASS/WARN/FAIL]</div>
    </div>
    <div class="card [pass/warn/fail]">
        <h3>Score</h3>
        <div class="score">[X]/100</div>
    </div>
    <!-- one card per category -->
</div>
```

Finding table rows -- apply CSS class based on status:

```html
<tr class="pass-row"><td>Pattern Name</td><td>R-001</td><td>source.md</td><td>PASS</td><td>Evidence quote</td></tr>
<tr class="error-row"><td>Pattern Name</td><td>R-002</td><td>source.md</td><td>ERROR</td><td>NOT FOUND</td></tr>
```

## Styling Rules

- Score >= 70: `pass` class (green)
- Score 50-69: `warn` class (yellow)
- Score < 50: `fail` class (red)
