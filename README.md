# Architecture Governance

Validate architecture documents against patterns, standards, and security rules.

## Setup

```bash
cp .env.example .env
# Edit .env and set COPILOT_TOKEN
```

## Usage

```bash
make validate                         # Validate sample document
make validate FILE=docs/myfile.html   # Validate specific file
make ingest FILE=docs/myfile.html     # Ingest file to markdown (no validation)
make release                          # Build, zip, push with auto tag
```

## Output

Reports in `governance/output/` - dashboard auto-opens in browser.
