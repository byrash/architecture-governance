"""
FastAPI application for the Architecture Governance page watcher.

Provides a web UI and REST API for managing watched Confluence pages,
triggering ingestion/indexing, previewing pages, and showing VS Code
Chat commands for governance validation.
"""

import asyncio
import os
import traceback
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from server.store import WatcherStore
from server.watcher import poll_loop

try:
    from dotenv import load_dotenv

    env_path = Path(".env")
    if not env_path.exists():
        for parent in Path.cwd().parents:
            candidate = parent / ".env"
            if candidate.exists():
                env_path = candidate
                break
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

app = FastAPI(title="Architecture Governance — Page Watcher")
store = WatcherStore()

templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


# ──────────────────────────────────────────────────────────────────
# Startup
# ──────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(poll_loop(store))


# ──────────────────────────────────────────────────────────────────
# HTML UI
# ──────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/pages/{page_id}/preview", response_class=HTMLResponse)
async def preview_page(page_id: str):
    """Render an ingested page.md as styled HTML."""
    md_path = Path("governance/output") / page_id / "page.md"
    if not md_path.exists():
        raise HTTPException(status_code=404, detail=f"page.md not found for {page_id}")

    md_content = md_path.read_text(encoding="utf-8")

    try:
        import markdown
        html_body = markdown.markdown(
            md_content,
            extensions=["tables", "fenced_code", "toc"],
        )
    except ImportError:
        html_body = f"<pre>{md_content}</pre>"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Page {page_id} — Preview</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         max-width: 960px; margin: 40px auto; padding: 0 20px; line-height: 1.6; color: #24292f; }}
  table {{ border-collapse: collapse; width: 100%; margin: 16px 0; }}
  th, td {{ border: 1px solid #d0d7de; padding: 8px 12px; text-align: left; }}
  th {{ background: #f6f8fa; font-weight: 600; }}
  tr:nth-child(even) {{ background: #f6f8fa; }}
  code {{ background: #f6f8fa; padding: 2px 6px; border-radius: 4px; font-size: 0.9em; }}
  pre {{ background: #f6f8fa; padding: 16px; border-radius: 6px; overflow-x: auto; }}
  h1, h2, h3, h4, h5, h6 {{ margin-top: 24px; }}
  a {{ color: #0969da; }}
  .back {{ display: inline-block; margin-bottom: 16px; color: #0969da; text-decoration: none; }}
  .back:hover {{ text-decoration: underline; }}
</style>
</head>
<body>
<a class="back" href="/">&larr; Back to Watcher</a>
{html_body}
</body>
</html>"""
    return HTMLResponse(content=html)


# ──────────────────────────────────────────────────────────────────
# REST API
# ──────────────────────────────────────────────────────────────────

@app.get("/api/pages")
async def list_pages():
    return JSONResponse(content=store.list_pages())


@app.post("/api/pages")
async def add_page(request: Request):
    body = await request.json()
    page_id = body.get("page_id")
    if not page_id:
        raise HTTPException(status_code=400, detail="page_id is required")
    mode = body.get("mode", "index")
    index = body.get("index")
    if mode == "index":
        if not index or index not in ("patterns", "standards", "security"):
            raise HTTPException(
                status_code=400,
                detail="index is required for index mode (patterns, standards, or security)",
            )
    entry = store.add_page(str(page_id), index=index, mode=mode)
    return JSONResponse(content=entry, status_code=201)


@app.delete("/api/pages/{page_id}")
async def remove_page(page_id: str):
    if store.remove_page(page_id):
        return JSONResponse(content={"removed": page_id})
    raise HTTPException(status_code=404, detail="Page not found")


@app.post("/api/pages/{page_id}/ingest")
async def trigger_ingest(page_id: str):
    """Ingest a page. In index mode, also indexes + extracts rules."""
    info = store.get_page(page_id)
    if not info:
        raise HTTPException(status_code=404, detail="Page not watched")

    store.update_page(page_id, status="ingesting", error=None)
    loop = asyncio.get_event_loop()

    try:
        result = await loop.run_in_executor(None, _run_ingest_sync, page_id, info)
        store.update_page(
            page_id,
            status="ingested",
            last_ingested=datetime.now().isoformat(),
            title=result.get("title"),
            output_path=result.get("output_path"),
            index_path=result.get("index_path"),
            rules_count=result.get("rules_count"),
            rules_summary=result.get("rules_summary"),
            error=None,
        )
        return JSONResponse(content=result)
    except Exception as exc:
        store.update_page(page_id, status="error", error=str(exc))
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc))


def _run_ingest_sync(page_id: str, info: dict) -> dict:
    """Synchronous ingest. Returns rich metadata for the UI."""
    import sys

    from ingest.confluence_ingest import ingest_page

    index = info.get("index")
    result = ingest_page(page_id=page_id, index=index)

    title = result.get("metadata", {}).get("title", page_id)
    output_path = f"governance/output/{page_id}/"

    response = {
        "status": "ingested",
        "page_id": page_id,
        "title": title,
        "output_path": output_path,
        "index_path": None,
        "rules_count": 0,
        "rules_summary": None,
    }

    if index:
        index_path = f"governance/indexes/{index}/{page_id}/"
        response["index_path"] = index_path

        rules_md = Path(index_path) / "rules.md"
        if rules_md.exists():
            rules_info = _parse_rules_summary(rules_md)
            response["rules_count"] = rules_info["total"]
            response["rules_summary"] = rules_info

        print(f"[ingest] Indexed {page_id} -> {index_path}", file=sys.stderr)
    else:
        print(f"[ingest] Ingested {page_id} -> {output_path}", file=sys.stderr)

    return response


def _parse_rules_summary(rules_md: Path) -> dict:
    """Parse a rules.md file and return a severity summary."""
    sev_counts = {"C": 0, "H": 0, "M": 0, "L": 0}
    total = 0
    rules = []

    in_table = False
    for line in rules_md.read_text(encoding="utf-8").split("\n"):
        if line.startswith("| ID") or line.startswith("|-"):
            in_table = True
            continue
        if in_table and line.startswith("|"):
            cols = [c.strip() for c in line.split("|")[1:-1]]
            if len(cols) >= 3:
                total += 1
                sev = cols[2]
                if sev in sev_counts:
                    sev_counts[sev] += 1
                rules.append({"id": cols[0], "rule": cols[1], "sev": sev})
        elif in_table and not line.startswith("|"):
            in_table = False

    return {"total": total, "severity": sev_counts, "rules": rules}


# ──────────────────────────────────────────────────────────────────
# Entrypoint
# ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server.app:app", host="0.0.0.0", port=8000, reload=True)
