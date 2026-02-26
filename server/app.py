"""
FastAPI application for the Architecture Governance page watcher.

Provides a web UI and REST API for managing watched Confluence pages,
triggering ingestion/indexing, live progress tracking from the
governance-agent via webhooks, and displaying reports.
"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
import sys
import traceback
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from server.store import WatcherStore, parse_rules_summary
from server.watcher import (
    add_trigger_label,
    poll_loop,
    remove_trigger_label,
    request_shutdown,
)

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

store = WatcherStore()
_watcher_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global _watcher_task
    _watcher_task = asyncio.create_task(poll_loop(store))
    print("[app] Watcher started", file=sys.stderr)
    try:
        yield
    finally:
        print("[app] Shutting down…", file=sys.stderr)
        request_shutdown()
        if _watcher_task and not _watcher_task.done():
            _watcher_task.cancel()
            try:
                await asyncio.wait_for(_watcher_task, timeout=3.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
        _watcher_task = None
        store.save()
        print("[app] Shutdown complete", file=sys.stderr)


app = FastAPI(title="Architecture Governance — Page Watcher", lifespan=lifespan)

templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


# ──────────────────────────────────────────────────────────────────
# HTML UI
# ──────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


def _md_to_html(path: Path) -> str:
    """Render a markdown file to HTML. Falls back to <pre> if markdown lib missing."""
    md_content = path.read_text(encoding="utf-8")
    try:
        import markdown
        return markdown.markdown(md_content, extensions=["tables", "fenced_code", "toc"])
    except ImportError:
        return f"<pre>{md_content}</pre>"


@app.get("/pages/{page_id}/preview", response_class=HTMLResponse)
async def preview_page(page_id: str):
    """Render an ingested page.md as styled HTML (used by modal overlay)."""
    md_path = Path("governance/output") / page_id / "page.md"
    if not md_path.exists():
        raise HTTPException(status_code=404, detail=f"page.md not found for {page_id}")
    return HTMLResponse(content=_md_to_html(md_path))


# ──────────────────────────────────────────────────────────────────
# SSE — Server-Sent Events (replaces polling)
# ──────────────────────────────────────────────────────────────────

@app.get("/api/events")
async def sse_events(request: Request):
    """SSE stream that pushes the full page list on every store change."""

    async def event_generator():
        last_version = -1
        try:
            while True:
                if await request.is_disconnected():
                    break
                data = json.dumps(store.list_pages(), default=str)
                yield f"data: {data}\n\n"
                last_version = store.version
                try:
                    await asyncio.wait_for(
                        store.wait_for_change(last_version),
                        timeout=30.0,
                    )
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            return

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ──────────────────────────────────────────────────────────────────
# REST API — Pages
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
    mode = body.get("mode", "validate")
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


@app.delete("/api/pages")
async def reset_all():
    """Remove all watched pages, clear output/index folders and state file."""
    count = store.clear_all()

    cleaned: list[str] = []
    p = Path("governance/output")
    if p.exists():
        shutil.rmtree(p)
        cleaned.append("governance/output")

    state_file = Path("governance/watcher_state.json")
    if state_file.exists():
        state_file.unlink()
        cleaned.append(str(state_file))

    print(
        f"[app] Reset: removed {count} page(s), cleaned {cleaned}",
        file=sys.stderr,
    )
    return JSONResponse(content={
        "removed_pages": count,
        "cleaned_folders": cleaned,
    })


@app.post("/api/pages/{page_id}/ingest")
async def trigger_ingest(page_id: str):
    """Ingest a page. In index mode, also indexes + extracts rules."""
    info = store.get_page(page_id)
    if not info:
        raise HTTPException(status_code=404, detail="Page not watched")

    store.update_page(
        page_id, status="ingesting", error=None,
        stale_validation=False, change_detected=False,
    )
    store.clear_progress(page_id)
    loop = asyncio.get_event_loop()

    try:
        result = await loop.run_in_executor(None, _run_ingest_sync, page_id, info)
        ver = result.get("page_version")
        store.update_page(
            page_id,
            status="ingested",
            last_ingested=datetime.now().isoformat(),
            title=result.get("title"),
            output_path=result.get("output_path"),
            index_path=result.get("index_path"),
            rules_count=result.get("rules_count"),
            rules_summary=result.get("rules_summary"),
            report_scores=None,
            stale_validation=False,
            change_detected=False,
            ingested_version=ver,
            last_version=ver,
            error=None,
        )
        return JSONResponse(content=result)
    except Exception as exc:
        store.update_page(page_id, status="error", error=str(exc))
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/pages/{page_id}/mark-ready")
async def mark_ready(page_id: str):
    """Add the trigger label to a Confluence page so the next poll triggers ingestion."""
    info = store.get_page(page_id)
    if not info:
        raise HTTPException(status_code=404, detail="Page not watched")

    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(None, add_trigger_label, page_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    return JSONResponse(content={"ok": True, "label_added": True})


# ──────────────────────────────────────────────────────────────────
# REST API — Progress (webhook from governance-agent)
# ──────────────────────────────────────────────────────────────────

@app.post("/api/pages/{page_id}/progress")
async def post_progress(page_id: str, request: Request):
    """Accept a progress log entry from the governance-agent.

    On the first entry, auto-transitions status from ingested -> validating.
    """
    info = store.get_page(page_id)
    if not info:
        raise HTTPException(status_code=404, detail="Page not watched")

    body = await request.json()
    store.append_progress(page_id, body)

    if info.get("status") == "ingested":
        store.update_page(page_id, status="validating", stale_validation=False)

    return JSONResponse(content={"ok": True})


@app.get("/api/pages/{page_id}/progress")
async def get_progress(page_id: str):
    """Return the full progress log for a page."""
    info = store.get_page(page_id)
    if not info:
        raise HTTPException(status_code=404, detail="Page not watched")
    return JSONResponse(content={
        "status": info.get("status"),
        "progress": store.get_progress(page_id),
    })


# ──────────────────────────────────────────────────────────────────
# REST API — Report (webhook from governance-agent)
# ──────────────────────────────────────────────────────────────────

@app.post("/api/pages/{page_id}/report")
async def post_report(page_id: str, request: Request):
    """Accept the final report scores from the governance-agent.

    Sets status to validated, stores the score breakdown, and removes the
    trigger label from the Confluence page (best-effort, non-blocking).
    """
    info = store.get_page(page_id)
    if not info:
        raise HTTPException(status_code=404, detail="Page not watched")

    body = await request.json()
    store.update_page(
        page_id,
        status="validated",
        validated_at=datetime.now().isoformat(),
        report_scores=body,
        change_detected=False,
    )
    store.append_progress(page_id, {
        "step": "done",
        "agent": "governance-agent",
        "status": "complete",
        "message": f"Validation complete — score {body.get('score', '?')}/100",
    })

    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, remove_trigger_label, page_id)

    return JSONResponse(content={"ok": True})


@app.get("/api/pages/{page_id}/report")
async def get_report(page_id: str):
    """Return the governance HTML report for the modal overlay.

    For standalone HTML reports, extracts body + re-scopes styles under
    a .report-root wrapper so they don't leak into the parent page.
    For markdown-only reports, builds inline-styled HTML via the
    Confluence comment builder (looks identical in the modal).
    """
    html_report = Path("governance/output") / f"{page_id}-governance-report.html"
    md_report = Path("governance/output") / f"{page_id}-governance-report.md"

    if html_report.exists():
        raw = html_report.read_text(encoding="utf-8")
        scoped = _scope_report_html(raw)
        return HTMLResponse(content=scoped)

    if md_report.exists():
        from ingest.confluence_ingest import _parse_md_report, _build_confluence_comment
        content = md_report.read_text(encoding="utf-8")
        data = _parse_md_report(content)
        if not data["page_id"]:
            data["page_id"] = page_id
        styled = _build_confluence_comment(data)
        return HTMLResponse(content=f'<div class="report-root">{styled}</div>')

    raise HTTPException(status_code=404, detail="Report not found")


def _scope_report_html(raw_html: str) -> str:
    """Extract body content and re-scope CSS under .report-root for modal use."""
    body_m = re.search(r"<body[^>]*>(.*)</body>", raw_html, re.DOTALL | re.IGNORECASE)
    body = body_m.group(1).strip() if body_m else raw_html

    style_m = re.search(r"<style[^>]*>(.*?)</style>", raw_html, re.DOTALL | re.IGNORECASE)
    if style_m:
        css = style_m.group(1)
        scoped_css = re.sub(
            r"(?m)^(\s*)(body|main)\b",
            r"\1.report-root",
            css,
        )
        scoped_css = re.sub(
            r"(?m)^(\s*)(\*)\s*\{",
            r"\1.report-root \2 {",
            scoped_css,
        )
        return f'<style>{scoped_css}</style><div class="report-root">{body}</div>'

    return f'<div class="report-root">{body}</div>'


@app.get("/api/pages/{page_id}/rules")
async def get_rules(page_id: str):
    """Return the rules.md rendered as HTML for the modal overlay."""
    info = store.get_page(page_id)
    if not info:
        raise HTTPException(status_code=404, detail="Page not watched")

    candidates = []
    index_path = info.get("index_path")
    if index_path:
        candidates.append(Path(index_path) / "rules.md")
    candidates.append(Path("governance/output") / page_id / "rules.md")

    for path in candidates:
        if path.exists():
            return HTMLResponse(content=_md_to_html(path))

    raise HTTPException(status_code=404, detail="rules.md not found")


# ──────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────

def _run_ingest_sync(page_id: str, info: dict) -> dict:
    """Synchronous ingest. Returns rich metadata for the UI."""
    import sys

    from ingest.confluence_ingest import ingest_page

    index = info.get("index")
    result = ingest_page(page_id=page_id, index=index)

    title = result.get("metadata", {}).get("title", page_id)
    output_path = f"governance/output/{page_id}/"

    page_version = result.get("metadata", {}).get("version")

    response = {
        "status": "ingested",
        "page_id": page_id,
        "title": title,
        "output_path": output_path,
        "index_path": None,
        "rules_count": 0,
        "rules_summary": None,
        "page_version": page_version,
    }

    if index:
        index_path = f"governance/indexes/{index}/{page_id}/"
        response["index_path"] = index_path

        rules_md = Path(index_path) / "rules.md"
        if rules_md.exists():
            rules_info = parse_rules_summary(rules_md)
            response["rules_count"] = rules_info["total"]
            response["rules_summary"] = rules_info

        print(f"[ingest] Indexed {page_id} -> {index_path}", file=sys.stderr)
    else:
        print(f"[ingest] Ingested {page_id} -> {output_path}", file=sys.stderr)

    return response


# ──────────────────────────────────────────────────────────────────
# Entrypoint
# ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server.app:app", host="0.0.0.0", port=8000, reload=True)
