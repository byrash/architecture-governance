"""
Background change-detection poller for Confluence pages.

Only triggers ingestion when the page carries the trigger label
(default: governance-ready).  Version changes without the label are
tracked as change_detected so the UI can prompt the user to add the
label when ready.
"""

import asyncio
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path

from server.store import WatcherStore, parse_rules_summary

POLL_INTERVAL = int(os.environ.get("WATCHER_POLL_INTERVAL", "10"))
TRIGGER_LABEL = os.environ.get("TRIGGER_LABEL", "governance-ready")


# ──────────────────────────────────────────────────────────────────
# Confluence helpers
# ──────────────────────────────────────────────────────────────────

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


def _has_trigger_label(page_data: dict) -> bool:
    """Check whether the Confluence API response carries the trigger label."""
    labels = (
        page_data.get("metadata", {})
        .get("labels", {})
        .get("results", [])
    )
    return any(lbl.get("name") == TRIGGER_LABEL for lbl in labels)


def _remove_label(confluence, page_id: str) -> None:
    """Best-effort removal of the trigger label from a Confluence page."""
    try:
        confluence.remove_page_label(page_id, TRIGGER_LABEL)
        print(f"[watcher] Removed '{TRIGGER_LABEL}' label from {page_id}", file=sys.stderr)
    except Exception as exc:
        print(f"[watcher] Could not remove label from {page_id}: {exc}", file=sys.stderr)


def _add_label(confluence, page_id: str) -> None:
    """Best-effort addition of the trigger label to a Confluence page."""
    try:
        confluence.set_page_label(page_id, TRIGGER_LABEL)
        print(f"[watcher] Added '{TRIGGER_LABEL}' label to {page_id}", file=sys.stderr)
    except Exception as exc:
        print(f"[watcher] Could not add label to {page_id}: {exc}", file=sys.stderr)


# ── Public wrappers (called by app.py) ────────────────────────────

def remove_trigger_label(page_id: str) -> None:
    """Remove trigger label from a page.  Creates its own client."""
    confluence = _get_confluence_client()
    if confluence:
        _remove_label(confluence, page_id)


def add_trigger_label(page_id: str) -> None:
    """Add trigger label to a page.  Creates its own client.

    Raises RuntimeError if no Confluence client can be created.
    """
    confluence = _get_confluence_client()
    if confluence is None:
        raise RuntimeError("Confluence client not configured (check CONFLUENCE_URL and token)")
    _add_label(confluence, page_id)


# ──────────────────────────────────────────────────────────────────
# Ingest
# ──────────────────────────────────────────────────────────────────

def _run_ingest(page_id: str, store: WatcherStore) -> None:
    """Re-ingest a page after trigger label is detected.

    Clears stale validation/report data and refreshes index metadata.
    """
    try:
        from ingest.confluence_ingest import ingest_page

        info = store.get_page(page_id) or {}
        was_validated = info.get("status") == "validated"

        store.update_page(page_id, status="ingesting", error=None, change_detected=False)
        store.clear_progress(page_id)

        index = info.get("index")
        result = ingest_page(page_id=page_id, index=index)

        title = result.get("metadata", {}).get("title", page_id)
        output_path = f"governance/output/{page_id}/"

        update_fields = dict(
            status="ingested",
            last_ingested=datetime.now().isoformat(),
            title=title,
            output_path=output_path,
            error=None,
            report_scores=None,
            index_path=None,
            rules_count=0,
            rules_summary=None,
            stale_validation=was_validated,
            change_detected=False,
        )

        if index:
            index_path = f"governance/indexes/{index}/{page_id}/"
            update_fields["index_path"] = index_path
            rules_md = Path(index_path) / "rules.md"
            if rules_md.exists():
                rules_info = parse_rules_summary(rules_md)
                update_fields["rules_count"] = rules_info["total"]
                update_fields["rules_summary"] = rules_info
            print(f"[watcher] Re-indexed {page_id} -> {index_path}", file=sys.stderr)
        else:
            print(f"[watcher] Re-ingested {page_id} -> {output_path}", file=sys.stderr)

        if was_validated:
            print(f"[watcher] Page {page_id} was validated — marked stale", file=sys.stderr)

        store.update_page(page_id, **update_fields)
    except Exception as exc:
        store.update_page(page_id, status="error", error=str(exc))
        traceback.print_exc()


# ──────────────────────────────────────────────────────────────────
# Poll loop
# ──────────────────────────────────────────────────────────────────

_shutdown = asyncio.Event()


def request_shutdown() -> None:
    """Signal the poll loop to stop gracefully."""
    _shutdown.set()


async def poll_loop(store: WatcherStore) -> None:
    """Infinite async loop that polls Confluence for page changes.

    Ingestion is only triggered when the trigger label is present on the
    page.  Version changes without the label set change_detected=True so
    the UI can show a prompt.
    """
    print(
        f"[watcher] Starting poll loop (interval={POLL_INTERVAL}s, "
        f"trigger_label={TRIGGER_LABEL})",
        file=sys.stderr,
    )

    try:
        while not _shutdown.is_set():
            try:
                confluence = _get_confluence_client()
                if confluence is None:
                    try:
                        await asyncio.wait_for(_shutdown.wait(), timeout=POLL_INTERVAL)
                    except asyncio.TimeoutError:
                        pass
                    continue

                pages = store.list_pages()
                for page_id, info in pages.items():
                    if _shutdown.is_set():
                        break

                    status = info.get("status")
                    if status in ("ingesting", "validating"):
                        continue

                    try:
                        page = confluence.get_page_by_id(
                            page_id, expand="version,metadata.labels",
                        )
                        version = page.get("version", {}).get("number")
                        title = page.get("title", "")
                        has_label = _has_trigger_label(page)

                        if title and info.get("title") != title:
                            store.update_page(page_id, title=title)

                        stored_version = info.get("last_version")

                        # Always store baseline version on first poll
                        if stored_version is None:
                            store.update_page(page_id, last_version=version)
                            stored_version = version

                        version_changed = version != stored_version

                        if version_changed:
                            store.update_page(page_id, last_version=version)

                        already_ingested = (
                            info.get("ingested_version") is not None
                            and info.get("ingested_version") == version
                        )

                        if has_label and not already_ingested:
                            print(
                                f"[watcher] Trigger label found on {page_id} "
                                f"(v{stored_version} -> v{version})",
                                file=sys.stderr,
                            )

                            is_index = info.get("mode") == "index"
                            loop = asyncio.get_event_loop()
                            await loop.run_in_executor(
                                None, _run_ingest, page_id, store,
                            )
                            store.update_page(page_id, ingested_version=version)

                            if is_index:
                                await loop.run_in_executor(
                                    None, _remove_label, confluence, page_id,
                                )

                        elif version_changed and not info.get("change_detected"):
                            print(
                                f"[watcher] Change detected (no label): {page_id} "
                                f"v{stored_version} -> v{version}",
                                file=sys.stderr,
                            )
                            store.update_page(page_id, change_detected=True)

                    except Exception as exc:
                        store.update_page(page_id, status="error", error=str(exc))
                        print(f"[watcher] Error polling {page_id}: {exc}", file=sys.stderr)

            except Exception as exc:
                print(f"[watcher] Poll loop error: {exc}", file=sys.stderr)

            # Sleep but wake immediately on shutdown signal
            try:
                await asyncio.wait_for(_shutdown.wait(), timeout=POLL_INTERVAL)
            except asyncio.TimeoutError:
                pass

    except asyncio.CancelledError:
        pass

    print("[watcher] Poll loop stopped", file=sys.stderr)
