from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
import json
from datetime import datetime

from backend.services.project_manager import get_project_manager
from backend.services.meeting_logger import MeetingLogger
from backend.modules.worldbook.st_style import STStyleWorldBook
from backend.core.protocols.l3 import Outline
from backend.core.registry import get_module, discover_modules

router = APIRouter()


class SceneTag(BaseModel):
    name: str
    perspective: str = "外聚焦"
    pace: str = "等述"
    discourse_mode: str = "对话+动作"
    word_count: int = 500
    content_points: List[str] = []


class GenerateChapterRequest(BaseModel):
    scenes: List[SceneTag]
    chapter_name: str = ""
    emotion_curve: str = ""
    hooks: List[str] = []


def sse_format(event_type: str, data: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/projects/{project_id}/l3/generate")
async def generate_chapter_plan(project_id: str, request: GenerateChapterRequest):
    discover_modules()
    
    pm = get_project_manager()
    project = pm.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    outline_path = project.project_path / "outputs" / "l2_outline.json"
    if not outline_path.exists():
        raise HTTPException(status_code=404, detail="Outline not found, please run L2 first")
    
    with open(outline_path, "r", encoding="utf-8") as f:
        outline_data = json.load(f)
    
    outline = Outline(**outline_data)
    
    world_book = STStyleWorldBook(project.project_path)
    
    strategy_cls = get_module("l3", "mapping_compiler")
    strategy = strategy_cls()
    
    chapter_plan = strategy.generate_chapter_plan(outline, world_book=world_book)
    
    if request.scenes:
        chapter_plan.scenes = [s.model_dump() for s in request.scenes]
    if request.chapter_name:
        chapter_plan.chapter_name = request.chapter_name
    if request.emotion_curve:
        chapter_plan.emotion_curve = request.emotion_curve
    if request.hooks:
        chapter_plan.hooks = request.hooks
    
    plan_path = project.project_path / "outputs" / "l3_chapter_plan.json"
    with open(plan_path, "w", encoding="utf-8") as f:
        json.dump(chapter_plan.model_dump(), f, ensure_ascii=False, indent=2)
    
    logger = MeetingLogger(project.project_path / "logs" / "meeting.db")
    logger.log_version(project_id, "l3", chapter_plan.model_dump(), "L3 chapter plan generated")
    
    return {"status": "generated", "chapter_plan": chapter_plan.model_dump()}


@router.get("/projects/{project_id}/l3/plan")
async def get_chapter_plan(project_id: str):
    pm = get_project_manager()
    project = pm.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    plan_path = project.project_path / "outputs" / "l3_chapter_plan.json"
    if not plan_path.exists():
        raise HTTPException(status_code=404, detail="Chapter plan not found")
    
    with open(plan_path, "r", encoding="utf-8") as f:
        plan = json.load(f)
    
    return {"chapter_plan": plan}


@router.put("/projects/{project_id}/l3/plan")
async def update_chapter_plan(project_id: str, data: dict):
    pm = get_project_manager()
    project = pm.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    plan_path = project.project_path / "outputs" / "l3_chapter_plan.json"
    if not plan_path.exists():
        raise HTTPException(status_code=404, detail="Chapter plan not found")
    
    with open(plan_path, "r", encoding="utf-8") as f:
        plan = json.load(f)
    
    plan.update(data)
    plan["updated_at"] = datetime.now().isoformat()
    
    with open(plan_path, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)
    
    return {"status": "updated", "chapter_plan": plan}


@router.get("/projects/{project_id}/l3/tags")
async def get_l3_tags(project_id: str):
    tags_path = get_project_manager().data_path.parent / "data" / "user" / "tags" / "l3_tags.json"
    if not tags_path.exists():
        return {"tags": []}
    
    with open(tags_path, "r", encoding="utf-8") as f:
        tags = json.load(f)
    
    return {"tags": tags}
