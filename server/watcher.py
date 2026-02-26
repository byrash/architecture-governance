"""
Background change-detection poller for Confluence pages.

Polls the Confluence API at a configurable interval, compares page versions,
and triggers ingestion when a change is detected.
"""

import asyncio
import os
import sys
import traceback
from datetime import datetime

from server.store import WatcherStore

POLL_INTERVAL = int(os.environ.get("WATCHER_POLL_INTERVAL", "60"))


def _get_confluence_client():
    """Lazy import to avoid startup failure if env vars are missing."""
    try:
        from atlassian import Confluence
    except ImportError:
        return None

    url = os.environ.get("CONFLUENCE_URL")
    token = os.environ.get("CONFLUENCE_API_TOKEN") or os.environ.get("CONFLUENCE_TOKEN")
    if not url or not token:
        return None
    return Confluence(url=url, token=token)


def _run_ingest(page_id: str, store: WatcherStore) -> None:
    """Call ingest_page() synchronously, copying to index if configured."""
    try:
        from ingest.confluence_ingest import ingest_page
        store.update_page(page_id, status="ingesting", error=None)
        info = store.get_page(page_id) or {}
        index = info.get("index")
        result = ingest_page(page_id=page_id, index=index)
        store.update_page(
            page_id,
            status="ingested",
            last_ingested=datetime.now().isoformat(),
            title=result.get("metadata", {}).get("title"),
            error=None,
        )
        print(f"[watcher] Ingested page {page_id}", file=sys.stderr)
    except Exception as exc:
        store.update_page(page_id, status="error", error=str(exc))
        traceback.print_exc()


async def poll_loop(store: WatcherStore) -> None:
    """Infinite async loop that polls Confluence for page changes."""
    print(f"[watcher] Starting poll loop (interval={POLL_INTERVAL}s)", file=sys.stderr)

    while True:
        try:
            confluence = _get_confluence_client()
            if confluence is None:
                await asyncio.sleep(POLL_INTERVAL)
                continue

            pages = store.list_pages()
            for page_id, info in pages.items():
                if info.get("status") == "ingesting":
                    continue

                try:
                    page = confluence.get_page_by_id(page_id, expand="version")
                    version = page.get("version", {}).get("number")
                    title = page.get("title", "")

                    if title and info.get("title") != title:
                        store.update_page(page_id, title=title)

                    stored_version = info.get("last_version")
                    if stored_version is None or version != stored_version:
                        print(
                            f"[watcher] Change detected: {page_id} "
                            f"v{stored_version} -> v{version}",
                            file=sys.stderr,
                        )
                        store.update_page(page_id, last_version=version)
                        loop = asyncio.get_event_loop()
                        await loop.run_in_executor(None, _run_ingest, page_id, store)
                except Exception as exc:
                    store.update_page(page_id, status="error", error=str(exc))
                    print(f"[watcher] Error polling {page_id}: {exc}", file=sys.stderr)

        except Exception as exc:
            print(f"[watcher] Poll loop error: {exc}", file=sys.stderr)

        await asyncio.sleep(POLL_INTERVAL)
