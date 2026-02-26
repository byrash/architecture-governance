"""
State persistence for the page watcher.

In-memory dict persisted to governance/watcher_state.json on every mutation.
Progress log is kept in-memory only (not persisted) to avoid bloating the state file.
Uses an asyncio.Event to notify SSE listeners of changes (zero polling).
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


STATE_FILE = Path("governance/watcher_state.json")


def parse_rules_summary(rules_md: Path) -> dict:
    """Parse a rules.md file and return a severity summary.

    Shared by app.py and watcher.py to avoid duplication.
    """
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


class WatcherStore:
    def __init__(self, path: Optional[Path] = None):
        self._path = path or STATE_FILE
        self._pages: Dict[str, Dict[str, Any]] = {}
        self._progress: Dict[str, List[Dict[str, Any]]] = {}
        self._version = 0
        self._event: Optional[asyncio.Event] = None
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                with open(self._path, "r") as f:
                    self._pages = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._pages = {}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w") as f:
            json.dump(self._pages, f, indent=2, default=str)

    def save(self) -> None:
        """Explicit save for shutdown / flush."""
        self._save()

    def _notify(self) -> None:
        """Bump version and wake any SSE listeners."""
        self._version += 1
        if self._event is not None:
            self._event.set()

    @property
    def version(self) -> int:
        return self._version

    async def wait_for_change(self, since_version: int) -> int:
        """Block until the store version exceeds *since_version*. Returns new version."""
        if self._event is None:
            self._event = asyncio.Event()
        while self._version <= since_version:
            self._event.clear()
            await self._event.wait()
        return self._version

    def list_pages(self) -> Dict[str, Dict[str, Any]]:
        result = {}
        for pid, info in self._pages.items():
            entry = dict(info)
            entry["progress_log"] = self._progress.get(pid, [])
            result[pid] = entry
        return result

    def get_page(self, page_id: str) -> Optional[Dict[str, Any]]:
        return self._pages.get(page_id)

    def add_page(self, page_id: str, index: Optional[str] = None, mode: str = "index") -> Dict[str, Any]:
        if page_id in self._pages:
            if index is not None:
                self._pages[page_id]["index"] = index
            self._pages[page_id]["mode"] = mode
            self._save()
            self._notify()
            return self._pages[page_id]

        entry = {
            "page_id": page_id,
            "mode": mode,
            "index": index,
            "title": None,
            "last_version": None,
            "last_ingested": None,
            "validated_at": None,
            "status": "pending",
            "added_at": datetime.now().isoformat(),
            "error": None,
            "report_scores": None,
        }
        self._pages[page_id] = entry
        self._save()
        self._notify()
        return entry

    def remove_page(self, page_id: str) -> bool:
        if page_id in self._pages:
            del self._pages[page_id]
            self._progress.pop(page_id, None)
            self._save()
            self._notify()
            return True
        return False

    def clear_all(self) -> int:
        """Remove all pages and progress. Returns count of pages removed."""
        count = len(self._pages)
        self._pages.clear()
        self._progress.clear()
        self._save()
        self._notify()
        return count

    def update_page(self, page_id: str, **kwargs: Any) -> None:
        if page_id not in self._pages:
            return
        self._pages[page_id].update(kwargs)
        self._save()
        self._notify()

    # ── Progress log (in-memory only) ──────────────────────────────

    def append_progress(self, page_id: str, entry: Dict[str, Any]) -> None:
        if page_id not in self._pages:
            return
        entry["timestamp"] = datetime.now().isoformat()
        self._progress.setdefault(page_id, []).append(entry)
        self._notify()

    def get_progress(self, page_id: str) -> List[Dict[str, Any]]:
        return self._progress.get(page_id, [])

    def clear_progress(self, page_id: str) -> None:
        self._progress.pop(page_id, None)
        self._notify()
