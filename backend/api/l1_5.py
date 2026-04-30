from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import json
from datetime import datetime
import asyncio

from backend.services.project_manager import get_project_manager
from backend.services.meeting_logger import MeetingLogger
from backend.core.config import get_config
from backend.core.registry import get_module, discover_modules

router = APIRouter()


class L15StartRequest(BaseModel):
    collaboration_mode: str = "semi_auto"
    max_rounds: int = 3


class L15Decision(BaseModel):
    action: str
    message: str = ""


_pending_feedback = {}


def sse_format(event_type: str, data: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


class L15ExpertMeeting:
    def __init__(
        self,
        collaboration_mode: str = "semi_auto",
        max_rounds: int = 3
    ):
        self.collaboration_mode = collaboration_mode
        self.max_rounds = max_rounds
        self._experts = {}
        self._meeting_history = []
        self._current_round = 0
    
    def get_expert(self, expert_type: str):
        if expert_type not in self._experts:
            expert_map = {
                "author": "senior_author_v1",
                "reader": "reader_representative_v1"
            }
            expert_cls = get_module("expert", expert_map.get(expert_type, expert_type))
            self._experts[expert_type] = expert_cls()
        return self._experts[expert_type]
    
    def generate_volume_plan(
        self,
        vision: dict,
        worldbook_text: str = "暂无世界书",
        human_feedback=None
    ):
        self._meeting_history = []
        self._current_round = 0
        
        while self._current_round < self.max_rounds:
            self._current_round += 1
            
            yield {
                "type": "round_start",
                "round": self._current_round,
                "max_rounds": self.max_rounds
            }
            
            speaking_order = [
                ("author", "main"),
                ("reader", "review"),
                ("author", "supplement"),
            ]
            
            context = {
                "vision": vision,
                "worldbook": worldbook_text,
                "round": self._current_round
            }
            
            if self._meeting_history:
                for op in reversed(self._meeting_history):
                    if op.expert_type == "资深作者":
                        context["author_proposal"] = op.content
                        break
                for op in reversed(self._meeting_history):
                    if op.expert_type == "读者代表":
                        context["reader_opinion"] = op.content
                        break
            
            for expert_type, speak_type in speaking_order:
                expert = self.get_expert(expert_type)
                
                yield {
                    "type": "expert_start",
                    "expert_id": expert.expert_id,
                    "expert_type": expert.expert_type,
                    "speak_type": speak_type
                }
                
                opinion = expert.speak(None, context)
                self._meeting_history.append(opinion)
                
                yield {
                    "type": "expert_speak",
                    "expert_id": opinion.expert_id,
                    "expert_type": opinion.expert_type,
                    "content": opinion.content,
                    "suggestions": opinion.suggestions
                }
                
                if self.collaboration_mode == "semi_auto" and human_feedback:
                    yield {"type": "waiting_user"}
                    feedback = human_feedback()
                    if feedback:
                        if feedback.get("action") == "approve":
                            yield {"type": "meeting_complete"}
                            break
                        elif feedback.get("action") == "modify":
                            context["user_feedback"] = feedback.get("message", "")
            
            if self.collaboration_mode == "manual" and human_feedback:
                yield {"type": "waiting_user"}
                feedback = human_feedback()
        
        volume_plan = self._format_volume_plan()
        
        yield {
            "type": "volume_plan_ready",
            "volume_plan": volume_plan,
            "rounds": self._current_round
        }
    
    def _format_volume_plan(self) -> dict:
        volumes = []
        for opinion in self._meeting_history:
            if opinion.expert_type == "资深作者":
                for suggestion in opinion.suggestions:
                    if suggestion.startswith("卷"):
                        volumes.append({
                            "name": suggestion,
                            "description": opinion.content
                        })
        
        return {
            "volumes": volumes,
            "meeting_summary": "\n\n".join([
                f"**{op.expert_type}**:\n{op.content}"
                for op in self._meeting_history
            ])
        }


@router.get("/projects/{project_id}/l1_5/stream")
async def l1_5_stream(project_id: str, collaboration_mode: str = "semi_auto"):
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
    max_rounds = getattr(config.pipeline, "l1_5", None)
    if max_rounds is None:
        max_rounds = 3
    elif hasattr(max_rounds, "max_rounds"):
        max_rounds = max_rounds.max_rounds
    else:
        max_rounds = 3
    
    logger = MeetingLogger(project.project_path / "logs" / "meeting.db")
    
    meeting = L15ExpertMeeting(
        collaboration_mode=collaboration_mode,
        max_rounds=max_rounds
    )
    
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
        except:
            pass
    
    async def generate():
        feedback_queue = asyncio.Queue()
        _pending_feedback[project_id] = feedback_queue
        
        def human_feedback():
            return None
        
        try:
            for event in meeting.generate_volume_plan(vision, worldbook_text, human_feedback=human_feedback):
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
                
                if event["type"] == "volume_plan_ready":
                    logger.log_version(
                        project_id=project_id,
                        layer="l1_5",
                        content=event["volume_plan"],
                        message=f"L1.5 volume plan generated in {event['rounds']} rounds"
                    )
                    
                    plan_path = project.project_path / "outputs" / "l1_5_volume_plan.json"
                    plan_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(plan_path, "w", encoding="utf-8") as f:
                        json.dump(event["volume_plan"], f, ensure_ascii=False, indent=2)
                    
                    md_path = project.project_path / "outputs" / "l1_5_volume_plan.md"
                    md_content = f"# L1.5 卷纲规划\n\n"
                    md_content += f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                    md_content += event["volume_plan"].get("meeting_summary", "")
                    with open(md_path, "w", encoding="utf-8") as f:
                        f.write(md_content)
                    
                    yield sse_format("done", {"message": "L1.5 meeting completed"})
        
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


@router.post("/projects/{project_id}/l1_5/feedback")
async def l1_5_feedback(project_id: str, data: L15Decision):
    if project_id not in _pending_feedback:
        raise HTTPException(status_code=404, detail="No active L1.5 meeting for this project")
    
    queue = _pending_feedback[project_id]
    await queue.put(data.model_dump())
    
    return {"status": "feedback_received"}


@router.get("/projects/{project_id}/l1_5/volume_plan")
async def get_volume_plan(project_id: str):
    pm = get_project_manager()
    project = pm.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    plan_path = project.project_path / "outputs" / "l1_5_volume_plan.json"
    if not plan_path.exists():
        return {"volume_plan": None}
    
    with open(plan_path, "r", encoding="utf-8") as f:
        volume_plan = json.load(f)
    
    return {"volume_plan": volume_plan}


@router.put("/projects/{project_id}/l1_5/volume_plan")
async def update_volume_plan(project_id: str, data: dict):
    pm = get_project_manager()
    project = pm.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    plan_path = project.project_path / "outputs" / "l1_5_volume_plan.json"
    if not plan_path.exists():
        raise HTTPException(status_code=404, detail="Volume plan not found")
    
    with open(plan_path, "r", encoding="utf-8") as f:
        volume_plan = json.load(f)
    
    volume_plan.update(data)
    volume_plan["updated_at"] = datetime.now().isoformat()
    
    with open(plan_path, "w", encoding="utf-8") as f:
        json.dump(volume_plan, f, ensure_ascii=False, indent=2)
    
    return {"status": "updated", "volume_plan": volume_plan}
