---
name: doc-to-markdown
description: Convert PDF or HTML documents to normalized Markdown. Use when asked to parse, convert, or ingest documents.
---

# Document to Markdown Conversion

Convert documents to normalized Markdown using BOTH model intelligence AND Python scripts.

## Approach: Model + Script

| Step | Who | What |
|------|-----|------|
| 1. Identify | Model | Determine input format |
| 2. Convert | Script | Parse and extract content |
| 3. Normalize | Model | Clean up, structure, improve |
| 4. Validate | Model | Ensure quality output |

## Step 1: Identify Input Format (Model)

Check the input file:
- `.md` → Already Markdown, just copy
- `.pdf` → Use PDF parser
- `.html` → Use HTML parser
- `http*` → Fetch from URL first

## Step 2: Convert Document (Script)

**For PDF/HTML:**
```bash
python governance/scripts/doc_to_markdown.py \
    --input <input_file> \
    --output governance/output/architecture.md
```

**For Markdown (just copy):**
```bash
cp <input_file> governance/output/architecture.md
```

## Step 3: Normalize Content (Model)

After script converts, read the output and:
- Fix formatting issues from conversion
- Add missing section headings
- Ensure consistent markdown structure
- Clean up artifacts from PDF/HTML parsing

## Step 4: Validate Output (Model)

Check that output has:
- Clear document title
- Logical section structure
- No broken formatting
- Preserved technical content

## Output

`governance/output/architecture.md` - Clean, normalized markdown
