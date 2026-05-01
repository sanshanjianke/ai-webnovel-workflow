"""
L2 compatibility layer — forwards to unified meeting API.
All old L2 endpoints are preserved and internally delegate to the MeetingEngine.
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse, StreamingResponse
from pydantic import BaseModel
import json
from datetime import datetime
import asyncio

from backend.services.project_manager import get_project_manager
from backend.services.meeting_logger import MeetingLogger
from backend.core.registry import discover_modules
from backend.core.protocols.meeting import MeetingConfig, ExpertConfig, ExpertRole, Granularity
from backend.modules.orchestration import MeetingEngine

router = APIRouter()
_pending_feedback: dict[str, asyncio.Queue] = {}


class L2Decision(BaseModel):
    action: str
    message: str = ""


def sse_format(event_type: str, data: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.get("/projects/{project_id}/l2/stream")
async def l2_stream(project_id: str, collaboration_mode: str = "semi_auto"):
    """Legacy L2 endpoint — internally uses unified MeetingEngine"""
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

    config = MeetingConfig(
        meeting_name="章纲设计 (Legacy L2)",
        granularity=Granularity.CHAPTER,
        experts=[
            ExpertConfig(expert_id="plot_architect_v1", role=ExpertRole.MAIN),
            ExpertConfig(expert_id="web_editor_v1", role=ExpertRole.REVIEW),
            ExpertConfig(expert_id="character_designer_v1", role=ExpertRole.SUPPLEMENT),
        ],
        collaboration_mode=collaboration_mode,
        max_rounds=3
    )

    logger = MeetingLogger(project.project_path / "logs" / "meeting.db")
    engine = MeetingEngine(config)

    worldbook_text = "暂无世界书"
    worldbook_path = project.project_path / "worldbook.json"
    if worldbook_path.exists():
        try:
            with open(worldbook_path, "r", encoding="utf-8") as f:
                wb_data = json.load(f)
                entries = wb_data.get("entries", [])
                if entries:
                    worldbook_text = "\n".join([
                        f"- {e.get('keys', [''])[0]}: {e.get('content', '')[:100]}..."
                        for e in entries[:10]
                    ])
        except Exception:
            pass

    async def generate():
        feedback_queue: asyncio.Queue = asyncio.Queue()
        _pending_feedback[project_id] = feedback_queue

        def human_feedback():
            return None

        try:
            for event in engine.run(vision, worldbook_text, human_feedback=human_feedback):
                if event["type"] == "expert_speak":
                    logger.log_meeting(
                        project_id=project_id,
                        expert_id=event["expert_id"],
                        expert_type=event["expert_type"],
                        content=event["content"],
                        suggestions=event.get("suggestions", []),
                        round=engine.current_round
                    )

                yield sse_format(event["type"], event)

                if event["type"] == "waiting_user":
                    try:
                        feedback = await asyncio.wait_for(feedback_queue.get(), timeout=600.0)
                        yield sse_format("user_feedback", feedback)
                    except asyncio.TimeoutError:
                        yield sse_format("timeout", {"message": "等待用户反馈超时"})
                        break

                if event["type"] == "output_ready":
                    logger.log_version(
                        project_id=project_id,
                        layer="l2",
                        content=event["output"],
                        message=f"L2 outline generated in {event['rounds']} rounds"
                    )

                    outline_path = project.project_path / "outputs" / "l2_outline.json"
                    with open(outline_path, "w", encoding="utf-8") as f:
                        json.dump(event["output"], f, ensure_ascii=False, indent=2)

                    yield sse_format("done", {"message": "Meeting completed"})
        finally:
            _pending_feedback.pop(project_id, None)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )


@router.post("/projects/{project_id}/l2/feedback")
async def l2_feedback(project_id: str, data: L2Decision):
    queue = _pending_feedback.get(project_id)
    if queue is None:
        raise HTTPException(status_code=404, detail="No active meeting for this project")
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
        return {"outline": json.load(f)}


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
