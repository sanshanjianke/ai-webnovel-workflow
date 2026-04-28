from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from backend.services.project_manager import get_project_manager
from backend.modules.worldbook.st_style import STStyleWorldBook
from backend.core.protocols.worldbook import Entry

router = APIRouter()


class EntryCreate(BaseModel):
    id: str
    keys: list[str]
    content: str
    secondary_keys: list[str] = []
    constant: bool = False
    priority: int = 10
    position: str = "before_char"
    metadata: dict = {}


class EntryUpdate(BaseModel):
    keys: Optional[list[str]] = None
    content: Optional[str] = None
    secondary_keys: Optional[list[str]] = None
    constant: Optional[bool] = None
    priority: Optional[int] = None
    position: Optional[str] = None
    metadata: Optional[dict] = None


def get_worldbook(project_id: str) -> STStyleWorldBook:
    pm = get_project_manager()
    project = pm.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return STStyleWorldBook(project.project_path)


@router.get("/projects/{project_id}/worldbook")
async def list_entries(project_id: str):
    wb = get_worldbook(project_id)
    entries = wb.list_all_entries()
    return {"entries": [e.model_dump() for e in entries]}


@router.post("/projects/{project_id}/worldbook")
async def create_entry(project_id: str, data: EntryCreate):
    wb = get_worldbook(project_id)
    entry = Entry(**data.model_dump())
    wb.create_entry(entry)
    return {"status": "created", "entry": entry.model_dump()}


@router.post("/projects/{project_id}/worldbook/commit")
async def commit_worldbook(project_id: str, message: str = ""):
    wb = get_worldbook(project_id)
    commit_hash = wb.commit(message or "Manual commit")
    return {"status": "committed", "hash": commit_hash}


@router.get("/projects/{project_id}/worldbook/commits")
async def list_commits(project_id: str):
    wb = get_worldbook(project_id)
    return {"commits": wb.list_commits()}


@router.get("/projects/{project_id}/worldbook/entry/{entry_id}")
async def get_entry(project_id: str, entry_id: str):
    wb = get_worldbook(project_id)
    entry = wb.get_entry(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    return entry.model_dump()


@router.put("/projects/{project_id}/worldbook/entry/{entry_id}")
async def update_entry(project_id: str, entry_id: str, data: EntryUpdate):
    wb = get_worldbook(project_id)
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    wb.update_entry(entry_id, update_data)
    entry = wb.get_entry(entry_id)
    return {"status": "updated", "entry": entry.model_dump() if entry else None}


@router.delete("/projects/{project_id}/worldbook/entry/{entry_id}")
async def delete_entry(project_id: str, entry_id: str):
    wb = get_worldbook(project_id)
    wb.delete_entry(entry_id)
    return {"status": "deleted"}
