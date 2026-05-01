"""
L1.5 compatibility layer — forwards to unified meeting API.
All old L1.5 endpoints are preserved and internally delegate to the MeetingEngine.
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, Literal
import json
from datetime import datetime
import asyncio

from backend.services.project_manager import get_project_manager
from backend.services.meeting_logger import MeetingLogger
from backend.core.registry import discover_modules
from backend.core.protocols.meeting import MeetingConfig, ExpertConfig, ExpertRole, Granularity
from backend.modules.orchestration import MeetingEngine, PRESET_CONFIGS

router = APIRouter()
_pending_feedback: dict[str, asyncio.Queue] = {}


class ExpertConfigRequest(BaseModel):
    expert_id: str
    role: Literal["main", "review", "supplement"] = "main"
    custom_prompt: Optional[str] = None


class L15StartRequest(BaseModel):
    meeting_name: str = "卷纲编排"
    granularity: Literal["volume", "chapter", "scene"] = "volume"
    experts: list[ExpertConfigRequest]
    collaboration_mode: Literal["semi_auto", "full_auto", "manual"] = "semi_auto"
    max_rounds: int = 3


class L15Decision(BaseModel):
    action: str
    message: str = ""


def sse_format(event_type: str, data: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/projects/{project_id}/l1_5/start")
async def l1_5_start(project_id: str, request: L15StartRequest):
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

    expert_configs = [
        ExpertConfig(expert_id=e.expert_id, role=ExpertRole(e.role), custom_prompt=e.custom_prompt)
        for e in request.experts
    ]

    meeting_config = MeetingConfig(
        meeting_name=request.meeting_name,
        granularity=Granularity(request.granularity),
        experts=expert_configs,
        collaboration_mode=request.collaboration_mode,
        max_rounds=request.max_rounds
    )

    logger = MeetingLogger(project.project_path / "logs" / "meeting.db")
    engine = MeetingEngine(meeting_config)

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
                    output = event["output"]
                    logger.log_version(
                        project_id=project_id,
                        layer="l1_5",
                        content=output,
                        message=f"Meeting '{meeting_config.meeting_name}' completed in {event['rounds']} rounds"
                    )

                    output_path = project.project_path / "outputs" / "l1_5_output.json"
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(output_path, "w", encoding="utf-8") as f:
                        json.dump(output, f, ensure_ascii=False, indent=2)

                    md_path = project.project_path / "outputs" / "l1_5_output.md"
                    md_content = f"# {meeting_config.meeting_name}\n\n"
                    md_content += f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                    md_content += f"粒度: {meeting_config.granularity.value}\n"
                    md_content += f"轮次: {event['rounds']}\n\n"
                    md_content += output.get("meeting_summary", "")
                    with open(md_path, "w", encoding="utf-8") as f:
                        f.write(md_content)

                    yield sse_format("done", {"message": "Meeting completed", "output": output})
        finally:
            _pending_feedback.pop(project_id, None)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )


@router.get("/projects/{project_id}/l1_5/stream")
async def l1_5_stream_legacy(project_id: str, preset: str = "volume_planning"):
    discover_modules()

    if preset not in PRESET_CONFIGS:
        raise HTTPException(status_code=400, detail=f"Unknown preset: {preset}")

    preset_config = PRESET_CONFIGS[preset]
    request = L15StartRequest(**preset_config)
    return await l1_5_start(project_id, request)


@router.post("/projects/{project_id}/l1_5/feedback")
async def l1_5_feedback(project_id: str, data: L15Decision):
    queue = _pending_feedback.get(project_id)
    if queue is None:
        raise HTTPException(status_code=404, detail="No active L1.5 meeting for this project")
    await queue.put(data.model_dump())
    return {"status": "feedback_received"}


@router.get("/projects/{project_id}/l1_5/output")
async def get_output(project_id: str):
    pm = get_project_manager()
    project = pm.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    output_path = project.project_path / "outputs" / "l1_5_output.json"
    if not output_path.exists():
        return {"output": None}

    with open(output_path, "r", encoding="utf-8") as f:
        return {"output": json.load(f)}


@router.put("/projects/{project_id}/l1_5/output")
async def update_output(project_id: str, data: dict):
    pm = get_project_manager()
    project = pm.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    output_path = project.project_path / "outputs" / "l1_5_output.json"
    if not output_path.exists():
        raise HTTPException(status_code=404, detail="Output not found")

    with open(output_path, "r", encoding="utf-8") as f:
        output = json.load(f)

    output.update(data)
    output["updated_at"] = datetime.now().isoformat()

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    return {"status": "updated", "output": output}
