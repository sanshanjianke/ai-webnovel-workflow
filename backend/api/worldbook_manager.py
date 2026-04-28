from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import json

from backend.services.project_manager import get_project_manager
from backend.services.worldbook_manager import WorldBookManager
from backend.modules.worldbook.st_style import STStyleWorldBook

router = APIRouter()


class ProcessSequenceRequest(BaseModel):
    sequence_content: str
    sequence_id: str


@router.post("/projects/{project_id}/worldbook/process-sequence")
async def process_sequence(project_id: str, data: ProcessSequenceRequest):
    pm = get_project_manager()
    project = pm.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    worldbook = STStyleWorldBook(project.project_path)
    manager = WorldBookManager(worldbook)
    
    changes = manager.process_sequence(data.sequence_content, data.sequence_id)
    
    return {
        "status": "processed",
        "changes": changes,
        "conflicts": manager.get_conflicts(changes)
    }


@router.post("/projects/{project_id}/worldbook/auto-commit")
async def auto_commit(project_id: str, message: str = ""):
    pm = get_project_manager()
    project = pm.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    worldbook = STStyleWorldBook(project.project_path)
    manager = WorldBookManager(worldbook)
    
    commit_hash = manager.commit(message or "Auto commit after sequence completion")
    
    return {
        "status": "committed",
        "hash": commit_hash
    }
