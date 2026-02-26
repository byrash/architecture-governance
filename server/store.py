"""
State persistence for the page watcher.

In-memory dict persisted to governance/watcher_state.json on every mutation.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


STATE_FILE = Path("governance/watcher_state.json")


class WatcherStore:
    def __init__(self, path: Optional[Path] = None):
        self._path = path or STATE_FILE
        self._pages: Dict[str, Dict[str, Any]] = {}
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

    def list_pages(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._pages)

    def get_page(self, page_id: str) -> Optional[Dict[str, Any]]:
        return self._pages.get(page_id)

    def add_page(self, page_id: str, index: Optional[str] = None, mode: str = "index") -> Dict[str, Any]:
        if page_id in self._pages:
            if index is not None:
                self._pages[page_id]["index"] = index
            self._pages[page_id]["mode"] = mode
            self._save()
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
        }
        self._pages[page_id] = entry
        self._save()
        return entry

    def remove_page(self, page_id: str) -> bool:
        if page_id in self._pages:
            del self._pages[page_id]
            self._save()
            return True
        return False

    def update_page(self, page_id: str, **kwargs: Any) -> None:
        if page_id not in self._pages:
            return
        self._pages[page_id].update(kwargs)
        self._save()
