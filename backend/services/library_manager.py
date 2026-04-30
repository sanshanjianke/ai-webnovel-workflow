import json
import uuid
import secrets
from pathlib import Path
from datetime import datetime
from typing import Optional, Union
from pydantic import BaseModel, Field
from enum import Enum


class DocSource(str, Enum):
    GENERATE = "generate"
    IMPORT = "import"
    MANUAL = "manual"


class DocStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DRAFT = "draft"


class DocEntry(BaseModel):
    uid: str = Field(default_factory=lambda: secrets.token_hex(4))
    name: str
    layer: str
    format: str = "json"
    source: DocSource = DocSource.GENERATE
    parent_uid: Optional[str] = None
    directory: str = "/"
    tags: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: Optional[str] = None
    word_count: int = 0
    status: DocStatus = DocStatus.ACTIVE
    checkpoint: Optional[dict] = None


class LibraryManifest(BaseModel):
    project_id: str
    directories: list[str] = Field(default_factory=lambda: ["/"])
    documents: list[DocEntry] = Field(default_factory=list)
    active_docs: dict[str, str] = Field(default_factory=dict)
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class LibraryManager:
    def __init__(self, project_path: Path):
        self.project_path = project_path
        self.library_path = project_path / "library"
        self.manifest_path = self.library_path / "manifest.json"
        self.files_path = self.library_path / "files"
        self.manifest: Optional[LibraryManifest] = None
        self._init()
    
    def _init(self):
        self.library_path.mkdir(parents=True, exist_ok=True)
        self.files_path.mkdir(parents=True, exist_ok=True)
        self._load_manifest()
        self._migrate_old_outputs()
    
    def _load_manifest(self):
        if self.manifest_path.exists():
            with open(self.manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.manifest = LibraryManifest(**data)
        else:
            self.manifest = LibraryManifest(project_id=self.project_path.name)
            self._save_manifest()
    
    def _save_manifest(self):
        self.manifest.updated_at = datetime.now().isoformat()
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(self.manifest.model_dump(), f, ensure_ascii=False, indent=2)
    
    def _migrate_old_outputs(self):
        migrated_marker = self.project_path / "outputs" / ".migrated"
        if migrated_marker.exists():
            return
        
        outputs_path = self.project_path / "outputs"
        if not outputs_path.exists():
            return
        
        old_files = {
            "l1_vision.json": ("l1", "L1 愿景"),
            "l2_outline.json": ("l2", "L2 大纲"),
            "l3_chapter_plan.json": ("l3", "L3 章纲"),
            "l4_text.json": ("l4", "L4 正文"),
        }
        
        for filename, (layer, prefix) in old_files.items():
            old_path = outputs_path / filename
            if old_path.exists():
                with open(old_path, "r", encoding="utf-8") as f:
                    content = json.load(f)
                
                word_count = self._count_words(content)
                
                entry = DocEntry(
                    uid=secrets.token_hex(4),
                    name=f"{prefix} — 迁移自旧版",
                    layer=layer,
                    source=DocSource.GENERATE,
                    word_count=word_count,
                    status=DocStatus.ACTIVE,
                )
                
                self.manifest.documents.append(entry)
                self._save_file(entry.uid, content)
                self.manifest.active_docs[layer] = entry.uid
        
        self._save_manifest()
        migrated_marker.touch()
    
    def _count_words(self, content: Union[dict, str]) -> int:
        if isinstance(content, str):
            return len(content.replace(" ", "").replace("\n", ""))
        elif isinstance(content, dict):
            text = json.dumps(content, ensure_ascii=False)
            return len(text.replace(" ", "").replace("\n", ""))
        return 0
    
    def _save_file(self, uid: str, content: Union[dict, str]):
        file_path = self.files_path / f"{uid}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            if isinstance(content, str):
                json.dump({"content": content}, f, ensure_ascii=False, indent=2)
            else:
                json.dump(content, f, ensure_ascii=False, indent=2)
    
    def _load_file(self, uid: str) -> Optional[dict]:
        file_path = self.files_path / f"{uid}.json"
        if not file_path.exists():
            return None
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def _delete_file(self, uid: str):
        file_path = self.files_path / f"{uid}.json"
        if file_path.exists():
            file_path.unlink()
    
    def add_document(
        self,
        name: str,
        layer: str,
        content: Union[dict, str],
        source: DocSource = DocSource.GENERATE,
        parent_uid: Optional[str] = None,
        directory: str = "/",
        tags: Optional[list[str]] = None,
        status: DocStatus = DocStatus.ACTIVE,
        checkpoint: Optional[dict] = None,
    ) -> str:
        uid = secrets.token_hex(4)
        word_count = self._count_words(content)
        
        entry = DocEntry(
            uid=uid,
            name=name,
            layer=layer,
            source=source,
            parent_uid=parent_uid,
            directory=directory,
            tags=tags or [],
            word_count=word_count,
            status=status,
            checkpoint=checkpoint,
        )
        
        self.manifest.documents.append(entry)
        self._save_file(uid, content)
        self._save_manifest()
        
        return uid
    
    def get_document(self, uid: str) -> Optional[tuple[DocEntry, dict]]:
        for entry in self.manifest.documents:
            if entry.uid == uid:
                content = self._load_file(uid)
                if content is not None:
                    return (entry, content)
        return None
    
    def get_entry(self, uid: str) -> Optional[DocEntry]:
        for entry in self.manifest.documents:
            if entry.uid == uid:
                return entry
        return None
    
    def update_entry(self, uid: str, **kwargs) -> Optional[DocEntry]:
        for i, entry in enumerate(self.manifest.documents):
            if entry.uid == uid:
                update_data = {k: v for k, v in kwargs.items() if hasattr(entry, k)}
                updated_entry = entry.model_copy(update=update_data)
                updated_entry.updated_at = datetime.now().isoformat()
                self.manifest.documents[i] = updated_entry
                self._save_manifest()
                return updated_entry
        return None
    
    def update_content(self, uid: str, content: Union[dict, str]) -> bool:
        entry = self.get_entry(uid)
        if entry:
            self._save_file(uid, content)
            word_count = self._count_words(content)
            self.update_entry(uid, word_count=word_count)
            return True
        return False
    
    def delete_document(self, uid: str) -> bool:
        for i, entry in enumerate(self.manifest.documents):
            if entry.uid == uid:
                self.manifest.documents.pop(i)
                self._delete_file(uid)
                for layer, active_uid in list(self.manifest.active_docs.items()):
                    if active_uid == uid:
                        del self.manifest.active_docs[layer]
                self._save_manifest()
                return True
        return False
    
    def archive_document(self, uid: str, archive: bool = True) -> Optional[DocEntry]:
        return self.update_entry(uid, status=DocStatus.ARCHIVED if archive else DocStatus.ACTIVE)
    
    def set_active(self, layer: str, uid: str) -> bool:
        entry = self.get_entry(uid)
        if entry and entry.layer == layer:
            self.manifest.active_docs[layer] = uid
            self._save_manifest()
            return True
        return False
    
    def get_active(self, layer: str) -> Optional[str]:
        return self.manifest.active_docs.get(layer)
    
    def get_active_document(self, layer: str) -> Optional[tuple[DocEntry, dict]]:
        uid = self.get_active(layer)
        if uid:
            return self.get_document(uid)
        return None
    
    def list_documents(
        self,
        layer: Optional[str] = None,
        directory: Optional[str] = None,
        include_archived: bool = False,
    ) -> list[DocEntry]:
        result = []
        for entry in self.manifest.documents:
            if layer and entry.layer != layer:
                continue
            if directory and entry.directory != directory:
                continue
            if not include_archived and entry.status == DocStatus.ARCHIVED:
                continue
            result.append(entry)
        return sorted(result, key=lambda e: e.created_at, reverse=True)
    
    def get_tree(self, include_archived: bool = False) -> dict:
        tree = {}
        for entry in self.manifest.documents:
            if not include_archived and entry.status == DocStatus.ARCHIVED:
                continue
            dir_path = entry.directory
            if dir_path not in tree:
                tree[dir_path] = []
            tree[dir_path].append(entry.model_dump())
        return tree
    
    def create_directory(self, path: str) -> bool:
        if not path.startswith("/"):
            path = "/" + path
        if path not in self.manifest.directories:
            self.manifest.directories.append(path)
            self._save_manifest()
            return True
        return False
    
    def delete_directory(self, path: str) -> bool:
        if path == "/":
            return False
        if path in self.manifest.directories:
            self.manifest.directories.remove(path)
            for entry in self.manifest.documents:
                if entry.directory == path:
                    entry.directory = "/"
            self._save_manifest()
            return True
        return False
    
    def get_children(self, parent_uid: str) -> list[DocEntry]:
        return [e for e in self.manifest.documents if e.parent_uid == parent_uid]
    
    def get_provenance_chain(self, uid: str) -> list[DocEntry]:
        chain = []
        current = self.get_entry(uid)
        while current:
            chain.append(current)
            if current.parent_uid:
                current = self.get_entry(current.parent_uid)
            else:
                break
        return chain
    
    def import_file(
        self,
        name: str,
        content: Union[dict, str],
        format: str = "json",
        directory: str = "/",
        tags: Optional[list[str]] = None,
    ) -> str:
        return self.add_document(
            name=name,
            layer="imported",
            content=content,
            source=DocSource.IMPORT,
            directory=directory,
            tags=tags,
        )


_library_managers: dict[str, LibraryManager] = {}


def get_library_manager(project_path: Path) -> LibraryManager:
    project_id = project_path.name
    if project_id not in _library_managers:
        _library_managers[project_id] = LibraryManager(project_path)
    return _library_managers[project_id]
