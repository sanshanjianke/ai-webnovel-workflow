from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from backend.services.project_manager import get_project_manager
from backend.services.meeting_logger import MeetingLogger
from pathlib import Path

router = APIRouter()


class ProjectCreate(BaseModel):
    name: str
    description: str = ""
    genre: str = ""
    target_platform: str = ""
    driving_mode: str = "plot_driven"


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    genre: Optional[str] = None
    target_platform: Optional[str] = None
    driving_mode: Optional[str] = None


@router.post("/")
async def create_project(data: ProjectCreate):
    pm = get_project_manager()
    project = pm.create_project(
        name=data.name,
        description=data.description,
        genre=data.genre,
        target_platform=data.target_platform,
        driving_mode=data.driving_mode
    )
    return {"id": project.id, "config": project.config.model_dump()}


@router.get("/")
async def list_projects():
    pm = get_project_manager()
    projects = pm.list_projects()
    return [
        {"id": p.id, "config": p.config.model_dump() if p.config else None}
        for p in projects
    ]


@router.get("/{project_id}")
async def get_project(project_id: str):
    pm = get_project_manager()
    project = pm.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"id": project.id, "config": project.config.model_dump() if project.config else None}


@router.put("/{project_id}/config")
async def update_project_config(project_id: str, data: ProjectUpdate):
    pm = get_project_manager()
    project = pm.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    project.update_config(**update_data)
    return {"id": project.id, "config": project.config.model_dump()}


@router.delete("/{project_id}")
async def delete_project(project_id: str):
    pm = get_project_manager()
    if pm.delete_project(project_id):
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Project not found")


@router.get("/{project_id}/logs")
async def get_project_logs(project_id: str, limit: int = 100):
    pm = get_project_manager()
    project = pm.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    db_path = project.project_path / "logs" / "meeting.db"
    if not db_path.exists():
        return {"meeting_logs": [], "version_history": []}
    
    logger = MeetingLogger(db_path)
    return {
        "meeting_logs": logger.get_meeting_logs(project_id, limit),
        "version_history": logger.get_version_history(project_id)
    }
