import json
import hashlib
from pathlib import Path
from typing import Optional
from datetime import datetime
from backend.core.protocols.worldbook import BaseWorldBook, Entry
from backend.core.registry import register_module


@register_module("worldbook")
class STStyleWorldBook(BaseWorldBook):
    def __init__(self, project_path):
        self.project_path = Path(project_path)
        self.worldbook_path = self.project_path / "worldbook.json"
        self.commits_path = self.project_path / "commits.json"
        self._entries: dict[str, Entry] = {}
        self._commits: list[dict] = []
        self._load()

    def _load(self):
        if self.worldbook_path.exists():
            with open(self.worldbook_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._entries = {
                    k: Entry(**v) for k, v in data.get("entries", {}).items()
                }
        
        if self.commits_path.exists():
            with open(self.commits_path, "r", encoding="utf-8") as f:
                self._commits = json.load(f)

    def _save(self):
        self.worldbook_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "entries": {k: v.model_dump() for k, v in self._entries.items()}
        }
        with open(self.worldbook_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _save_commits(self):
        self.commits_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.commits_path, "w", encoding="utf-8") as f:
            json.dump(self._commits, f, ensure_ascii=False, indent=2)

    def get_active_entries(self, context_tokens: list[str]) -> list[Entry]:
        result = []
        for entry in self._entries.values():
            if entry.constant:
                result.append(entry)
                continue
            
            for key in entry.keys:
                if key in context_tokens:
                    if entry.secondary_keys:
                        if any(sk in context_tokens for sk in entry.secondary_keys):
                            result.append(entry)
                            break
                    else:
                        result.append(entry)
                        break
        
        result.sort(key=lambda x: x.priority, reverse=True)
        return result

    def get_entry(self, entry_id: str) -> Optional[Entry]:
        return self._entries.get(entry_id)

    def update_entry(self, entry_id: str, data: dict) -> None:
        if entry_id in self._entries:
            entry = self._entries[entry_id]
            updated = entry.model_copy(update=data)
            self._entries[entry_id] = updated
            self._save()

    def create_entry(self, entry: Entry) -> None:
        self._entries[entry.id] = entry
        self._save()

    def delete_entry(self, entry_id: str) -> None:
        if entry_id in self._entries:
            del self._entries[entry_id]
            self._save()

    def commit(self, message: str) -> str:
        content = json.dumps({k: v.model_dump() for k, v in self._entries.items()})
        commit_hash = hashlib.sha256(content.encode()).hexdigest()[:12]
        
        commit_record = {
            "hash": commit_hash,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "entry_count": len(self._entries)
        }
        
        self._commits.append(commit_record)
        self._save_commits()
        return commit_hash

    def revert(self, commit_hash: str) -> None:
        pass

    def list_commits(self) -> list[dict]:
        return self._commits

    def list_all_entries(self) -> list[Entry]:
        return list(self._entries.values())
