import os
import sys
import json
import re
import logging

logger = logging.getLogger(__name__)

def get_base_dir() -> str:
    """
    Returns base directory: directory of exe when frozen with PyInstaller,
    or project root directory when running standard python script.
    """
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    # Return project root (one directory up from core/)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class MemoryStore:
    """
    Persistent key-value memory store for ECHO user facts stored in a local JSON file.
    """
    def __init__(self, config: dict):
        mem_cfg = config.get("memory", {})
        self.enabled = mem_cfg.get("enabled", True)
        file_name = mem_cfg.get("file_path", "memory.json")
        self.file_path = os.path.join(get_base_dir(), file_name)
        self._data = {}
        if self.enabled:
            self._load()

    def _load(self):
        """Loads JSON memory file from disk if it exists."""
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
                logger.info(f"[MemoryStore]: Loaded {len(self._data)} memories from '{self.file_path}'.")
            except Exception as e:
                logger.error(f"[MemoryStore Error]: Failed to load memory file '{self.file_path}': {e}")
                self._data = {}
        else:
            self._data = {}

    def _save(self):
        """Persists current memories to JSON file on disk."""
        if not self.enabled:
            return
        try:
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
            logger.info(f"[MemoryStore]: Saved memories to '{self.file_path}'.")
        except Exception as e:
            logger.error(f"[MemoryStore Error]: Failed to save memory file '{self.file_path}': {e}")

    def remember(self, key: str, value: str):
        """Stores key-value fact in memory store and persists to disk."""
        if not self.enabled:
            return
        self._data[key] = value
        self._save()

    def add_fact(self, fact_text: str) -> str:
        """
        Stores a raw fact sentence without overwriting previous facts.
        Extracts specific keys (e.g. 'name') if matching 'my name is <val>',
        otherwise auto-generates key like 'fact_1', 'fact_2', etc.
        Returns the key used.
        """
        if not self.enabled:
            return ""

        clean_text = fact_text.strip()
        if not clean_text:
            return ""

        # Check for explicit 'my name is <val>' pattern
        name_match = re.match(r"^my\s+name\s+is\s+(.+)$", clean_text, re.IGNORECASE)
        if name_match:
            key = "name"
            val = name_match.group(1).strip().title()
            self.remember(key, val)
            return key

        # Prevent duplicate values if exact sentence already stored
        for k, v in self._data.items():
            if v.lower() == clean_text.lower():
                return k

        # Auto-generate next available fact_N key
        fact_indices = []
        for k in self._data.keys():
            if k.startswith("fact_"):
                try:
                    fact_indices.append(int(k.split("_")[1]))
                except ValueError:
                    pass

        next_idx = max(fact_indices, default=0) + 1
        key = f"fact_{next_idx}"

        self.remember(key, clean_text)
        return key

    def recall(self, key: str) -> str | None:
        """Returns stored memory value for given key, or None if not found."""
        if not self.enabled:
            return None
        return self._data.get(key)

    def get_all(self) -> dict:
        """Returns a copy of all stored memory key-value pairs."""
        if not self.enabled:
            return {}
        return dict(self._data)

    def forget(self, key: str):
        """Removes a key from memory store if present and persists changes."""
        if not self.enabled:
            return
        if key in self._data:
            del self._data[key]
            self._save()
