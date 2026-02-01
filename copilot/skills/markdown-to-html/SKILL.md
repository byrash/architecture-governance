---
name: markdown-to-html
description: Convert governance report to HTML dashboard. Use when asked to generate HTML or create dashboard.
---

# Markdown to HTML Dashboard

Generate HTML dashboard from governance report.

## Input

`governance/output/<PAGE_ID>-governance-report.md`

## Instructions

1. Read the governance report
2. Extract scores and findings
3. Generate complete HTML with embedded CSS
4. Write to output file

## Output

Write to `governance/output/<PAGE_ID>-governance-report.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Architecture Governance Report</title>
    <style>
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
        .section h2 { border-bottom: 2px solid #667eea; padding-bottom: 10px; }
        table { width: 100%; border-collapse: collapse; margin: 15px 0; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #f8f9fa; }
        .critical { background: #fef2f2; border-left: 4px solid #ef4444; padding: 15px; margin: 10px 0; }
        .recommendation { background: #eff6ff; border-left: 4px solid #3b82f6; padding: 15px; margin: 10px 0; }
        details { margin: 10px 0; }
        summary { cursor: pointer; padding: 10px; background: #f8f9fa; border-radius: 5px; font-weight: 600; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🏛️ Architecture Governance Report</h1>
        <p>Page ID: <PAGE_ID></p>
        <p>Generated: [timestamp]</p>
    </div>
    
    <div class="score-cards">
        <div class="card [pass/warn/fail]">
            <h3>Overall</h3>
            <div class="score">[STATUS]</div>
        </div>
        <div class="card [pass/warn/fail]">
            <h3>Score</h3>
            <div class="score">[X]/100</div>
        </div>
        <div class="card [pass/warn/fail]">
            <h3>Patterns</h3>
            <div class="score">[X]/100</div>
        </div>
        <div class="card [pass/warn/fail]">
            <h3>Standards</h3>
            <div class="score">[X]/100</div>
        </div>
        <div class="card [pass/warn/fail]">
            <h3>Security</h3>
            <div class="score">[X]/100</div>
        </div>
    </div>
    
    <div class="section">
        <h2>Executive Summary</h2>
        [Summary content]
    </div>
    
    <div class="section">
        <h2>Critical Issues</h2>
        [Critical issues with .critical class]
    </div>
    
    <div class="section">
        <h2>Recommendations</h2>
        [Recommendations with .recommendation class]
    </div>
    
    <div class="section">
        <h2>Detailed Findings</h2>
        <details><summary>Pattern Validation</summary>[content]</details>
        <details><summary>Standards Validation</summary>[content]</details>
        <details><summary>Security Validation</summary>[content]</details>
    </div>
</body>
</html>
```

## Styling Rules

- Score >= 70: `pass` class (green)
- Score 50-69: `warn` class (yellow)  
- Score < 50: `fail` class (red)
