from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import json
from datetime import datetime
import asyncio

from backend.services.project_manager import get_project_manager
from backend.services.meeting_logger import MeetingLogger
from backend.modules.worldbook.st_style import STStyleWorldBook
from backend.modules.l2.expert_meeting import ExpertMeetingL2
from backend.core.config import get_config
from backend.core.registry import get_module, discover_modules

router = APIRouter()


class L2StartRequest(BaseModel):
    collaboration_mode: str = "semi_auto"
    max_rounds: int = 3


class L2Decision(BaseModel):
    action: str
    message: str = ""


_pending_feedback = {}


def sse_format(event_type: str, data: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.get("/projects/{project_id}/l2/stream")
async def l2_stream(project_id: str, collaboration_mode: str = "semi_auto"):
    discover_modules()
    
    pm = get_project_manager()
    project = pm.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    vision_path = project.project_path / "outputs" / "l1_vision.json"
    if not vision_path.exists():
        raise HTTPException(status_code=404, detail="Vision not found, please run L1 first")
    
    with open(vision_path, "r", encoding="utf-8") as f:
        vision = json.load(f)
    
    config = get_config()
    protocol_id = config.pipeline.l2.meeting_protocol
    
    world_book = STStyleWorldBook(project.project_path)
    logger = MeetingLogger(project.project_path / "logs" / "meeting.db")
    
    meeting = ExpertMeetingL2(
        protocol_id=protocol_id,
        collaboration_mode=collaboration_mode,
        max_rounds=config.pipeline.l2.max_rounds
    )
    
    async def generate():
        feedback_queue = asyncio.Queue()
        _pending_feedback[project_id] = feedback_queue
        
        def human_feedback():
            return None
        
        try:
            for event in meeting.generate_outline(vision, world_book, human_feedback=human_feedback):
                if event["type"] == "expert_speak":
                    logger.log_meeting(
                        project_id=project_id,
                        expert_id=event["expert_id"],
                        expert_type=event["expert_type"],
                        content=event["content"],
                        suggestions=event.get("suggestions", []),
                        round=meeting._current_round
                    )
                
                yield sse_format(event["type"], event)
                
                if event["type"] == "waiting_user":
                    try:
                        feedback = await asyncio.wait_for(
                            queue.get(),
                            timeout=300.0
                        )
                        yield sse_format("user_feedback", feedback)
                    except asyncio.TimeoutError:
                        yield sse_format("timeout", {"message": "Waiting for user feedback timed out"})
                        break
                
                if event["type"] == "outline_ready":
                    logger.log_version(
                        project_id=project_id,
                        layer="l2",
                        content=event["outline"],
                        message=f"L2 outline generated in {event['rounds']} rounds"
                    )
                    
                    outline_path = project.project_path / "outputs" / "l2_outline.json"
                    with open(outline_path, "w", encoding="utf-8") as f:
                        json.dump(event["outline"], f, ensure_ascii=False, indent=2)
                    
                    yield sse_format("done", {"message": "Meeting completed"})
        
        finally:
            if project_id in _pending_feedback:
                del _pending_feedback[project_id]
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.post("/projects/{project_id}/l2/feedback")
async def l2_feedback(project_id: str, data: L2Decision):
    if project_id not in _pending_feedback:
        raise HTTPException(status_code=404, detail="No active meeting for this project")
    
    queue = _pending_feedback[project_id]
    await queue.put(data.model_dump())
    
    return {"status": "feedback_received"}


@router.get("/projects/{project_id}/l2/outline")
async def get_outline(project_id: str):
    pm = get_project_manager()
    project = pm.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    outline_path = project.project_path / "outputs" / "l2_outline.json"
    if not outline_path.exists():
        raise HTTPException(status_code=404, detail="Outline not found")
    
    with open(outline_path, "r", encoding="utf-8") as f:
        outline = json.load(f)
    
    return {"outline": outline}


@router.put("/projects/{project_id}/l2/outline")
async def update_outline(project_id: str, data: dict):
    pm = get_project_manager()
    project = pm.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    outline_path = project.project_path / "outputs" / "l2_outline.json"
    if not outline_path.exists():
        raise HTTPException(status_code=404, detail="Outline not found")
    
    with open(outline_path, "r", encoding="utf-8") as f:
        outline = json.load(f)
    
    outline.update(data)
    outline["updated_at"] = datetime.now().isoformat()
    
    with open(outline_path, "w", encoding="utf-8") as f:
        json.dump(outline, f, ensure_ascii=False, indent=2)
    
    return {"status": "updated", "outline": outline}
