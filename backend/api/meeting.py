from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, Literal
import json
from datetime import datetime
from pathlib import Path
import asyncio

from backend.services.project_manager import get_project_manager
from backend.services.meeting_logger import MeetingLogger
from backend.core.config import get_config
from backend.core.registry import discover_modules, MODULE_REGISTRY
from backend.core.protocols.meeting import MeetingConfig, ExpertConfig, ContainerConfig, ExpertRole, Granularity
from backend.modules.orchestration import MeetingEngine, PRESET_CONFIGS

router = APIRouter()
CUSTOM_EXPERTS_DIR = Path("data/user/custom_experts")

_pending_feedback: dict[str, asyncio.Queue] = {}

DISCOVERED = False


def _ensure_discovered():
    global DISCOVERED
    if not DISCOVERED:
        discover_modules()
        DISCOVERED = True


def sse_format(event_type: str, data: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# ── Request/Response models ──────────────────────────────────


class ExpertConfigRequest(BaseModel):
    expert_id: str
    role: Literal["main", "review", "supplement"] = "main"
    custom_prompt: Optional[str] = None
    container_id: Optional[str] = None


class ContainerConfigRequest(BaseModel):
    container_id: str
    name: str = "容器"
    concurrency: Literal["serial", "parallel"] = "serial"
    speaking_mode: Literal["ordered", "mention_driven"] = "ordered"
    context_layers: Optional[int] = None
    context_tokens: Optional[int] = None
    repeat: int = 1
    exit_mode: Literal["manual", "consensus", "ratio", "gatekeeper"] = "manual"
    exit_ratio: float = 0.6
    exit_gatekeeper: Optional[str] = None
    exit_max_speeches: int = 20
    children: list[str] = []
    edges: list[dict] = []


class MeetingStartRequest(BaseModel):
    meeting_name: str = "专家会议"
    experts: list[ExpertConfigRequest]
    containers: list[ContainerConfigRequest] = []


class MeetingFeedback(BaseModel):
    action: str  # approve | modify | stop | call_expert | restart
    message: str = ""
    expert_id: Optional[str] = None  # for call_expert action


# ── API Endpoints ────────────────────────────────────────────


@router.get("/presets")
async def get_presets():
    return {"presets": PRESET_CONFIGS}


@router.get("/experts")
async def list_experts():
    from backend.core.registry import list_modules
    builtin = list_modules("expert")
    
    custom = {}
    if CUSTOM_EXPERTS_DIR.exists():
        for f in sorted(CUSTOM_EXPERTS_DIR.glob("*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                custom[data["id"]] = {
                    "id": data["id"],
                    "label": data.get("name", data["id"]),
                    "icon": data.get("icon", "📄"),
                    "desc": data.get("description", ""),
                    "builtin": False
                }
            except Exception:
                pass
    
    return {
        "experts": list(builtin),
        "custom_experts": custom
    }


class CustomExpertRequest(BaseModel):
    id: str
    name: str
    icon: str = "📄"
    description: str = ""
    prompt_template: str


@router.post("/experts/custom")
async def create_custom_expert(data: CustomExpertRequest):
    CUSTOM_EXPERTS_DIR.mkdir(parents=True, exist_ok=True)
    filepath = CUSTOM_EXPERTS_DIR / f"{data.id}.json"
    if filepath.exists():
        raise HTTPException(status_code=409, detail="Expert ID already exists")
    
    expert_data = {
        "id": data.id,
        "name": data.name,
        "icon": data.icon,
        "description": data.description,
        "prompt_template": data.prompt_template,
        "created_at": datetime.now().isoformat()
    }
    filepath.write_text(json.dumps(expert_data, ensure_ascii=False, indent=2), encoding="utf-8")
    
    _register_custom_expert(data.id, expert_data)
    return {"status": "created", "expert": expert_data}


@router.delete("/experts/custom/{expert_id}")
async def delete_custom_expert(expert_id: str):
    filepath = CUSTOM_EXPERTS_DIR / f"{expert_id}.json"
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Custom expert not found")
    filepath.unlink()
    MODULE_REGISTRY["expert"].pop(expert_id, None)
    return {"status": "deleted"}


def _register_custom_expert(expert_id: str, expert_data: dict):
    """动态注册自定义专家到 registry"""
    from backend.core.protocols.expert import BaseExpert, ExpertOpinion
    
    class DynamicCustomExpert(BaseExpert):
        _id = expert_id
        _data = expert_data
        
        @property
        def expert_id(self) -> str:
            return self._id
        
        @property
        def expert_type(self) -> str:
            return self._data.get("name", self._id)
        
        def speak(self, outline, context: dict) -> ExpertOpinion:
            from backend.core.config import get_config
            from backend.core.registry import get_module
            
            config = get_config()
            llm_cls = get_module("llm", config.llm.primary)
            llm = llm_cls()
            
            template = self._data.get("prompt_template", "")
            
            vision = context.get("vision", {})
            vision_text = ""
            if isinstance(vision, dict):
                vision_text = "\n".join([f"- {k}: {v}" for k, v in vision.items() if v])
            else:
                vision_text = str(vision)
            
            author_proposal = context.get("author_proposal", "")
            reader_opinion = context.get("reader_opinion", "")
            worldbook = context.get("worldbook", "")
            user_feedback = context.get("user_feedback", "")
            custom_prompt = context.get("custom_prompt", "")
            
            history = context.get("history", [])
            history_text = ""
            if history:
                history_text = "\n".join([
                    f"[{getattr(op, 'expert_type', '?')}] {getattr(op, 'content', '')[:300]}..."
                    for op in history[-3:]
                ])
            
            prompt = template.replace("{vision}", vision_text)\
                             .replace("{worldbook}", worldbook)\
                             .replace("{author_proposal}", author_proposal)\
                             .replace("{reader_opinion}", reader_opinion)\
                             .replace("{user_feedback}", user_feedback)\
                             .replace("{history}", history_text)\
                             .replace("{custom_prompt}", custom_prompt)
            
            content = llm.invoke(prompt, temperature=0.8)
            
            return ExpertOpinion(
                expert_id=self._id,
                expert_type=self._data.get("name", self._id),
                content=content,
                suggestions=[]
            )
    
    MODULE_REGISTRY["expert"][expert_id] = DynamicCustomExpert


def _load_custom_experts():
    """启动时加载已有自定义专家"""
    if not CUSTOM_EXPERTS_DIR.exists():
        return
    for f in sorted(CUSTOM_EXPERTS_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            _register_custom_expert(data["id"], data)
        except Exception:
            pass


# 启动时加载
_load_custom_experts()


@router.post("/projects/{project_id}/meeting/start")
async def meeting_start(project_id: str, request: MeetingStartRequest):
    _ensure_discovered()

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
        ExpertConfig(expert_id=e.expert_id, role=ExpertRole(e.role), custom_prompt=e.custom_prompt, container_id=e.container_id)
        for e in request.experts
    ]

    container_configs = [
        ContainerConfig(
            container_id=c.container_id,
            name=c.name,
            concurrency=c.concurrency,
            speaking_mode=c.speaking_mode,
            context_layers=c.context_layers,
            context_tokens=c.context_tokens,
            repeat=c.repeat,
            exit_mode=c.exit_mode,
            exit_ratio=c.exit_ratio,
            exit_gatekeeper=c.exit_gatekeeper,
            exit_max_speeches=c.exit_max_speeches,
            children=c.children,
            edges=c.edges,
        )
        for c in request.containers
    ]

    meeting_config = MeetingConfig(
        meeting_name=request.meeting_name,
        granularity=Granularity("chapter"),
        experts=expert_configs,
        containers=container_configs,
        collaboration_mode="semi_auto",
        max_rounds=3,
        max_speeches=0
    )

    logger = MeetingLogger(project.project_path / "logs" / "meeting.db")
    engine = MeetingEngine(meeting_config)

    worldbook_text = _load_worldbook(project.project_path)

    async def generate():
        feedback_queue: asyncio.Queue = asyncio.Queue()
        _pending_feedback[project_id] = feedback_queue

        # Shared feedback state for engine
        feedback_state = {"action": None, "message": "", "expert_id": None}

        def human_feedback():
            fb = feedback_state.copy()
            feedback_state["action"] = None
            return fb if fb["action"] else None

        async def wait_for_feedback():
            try:
                fb = await asyncio.wait_for(feedback_queue.get(), timeout=600.0)
                feedback_state["action"] = fb.get("action", "")
                feedback_state["message"] = fb.get("message", "")
                feedback_state["expert_id"] = fb.get("expert_id")
                yield sse_format("user_feedback", fb)
            except asyncio.TimeoutError:
                yield sse_format("timeout", {"message": "等待用户反馈超时"})

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
                    async for fb_event in wait_for_feedback():
                        yield fb_event

                if event["type"] == "output_ready":
                    output = event["output"]
                    logger.log_version(
                        project_id=project_id,
                        layer="meeting",
                        content=output,
                        message=f"Meeting '{meeting_config.meeting_name}' completed in {event['rounds']} rounds"
                    )

                    output_path = project.project_path / "outputs" / "meeting_output.json"
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(output_path, "w", encoding="utf-8") as f:
                        json.dump(output, f, ensure_ascii=False, indent=2)

                    md_path = project.project_path / "outputs" / "meeting_output.md"
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


@router.get("/projects/{project_id}/meeting/stream")
async def meeting_stream(project_id: str, preset: str = "chapter_design"):
    """使用预置模板启动会议"""
    _ensure_discovered()

    if preset not in PRESET_CONFIGS:
        raise HTTPException(status_code=400, detail=f"Unknown preset: {preset}")

    preset_config = PRESET_CONFIGS[preset]
    request = MeetingStartRequest(**preset_config)
    return await meeting_start(project_id, request)


@router.post("/projects/{project_id}/meeting/feedback")
async def meeting_feedback(project_id: str, data: MeetingFeedback):
    queue = _pending_feedback.get(project_id)
    if queue is None:
        raise HTTPException(status_code=404, detail="No active meeting for this project")
    await queue.put(data.model_dump())
    return {"status": "feedback_received"}


@router.get("/projects/{project_id}/meeting/output")
async def get_meeting_output(project_id: str):
    pm = get_project_manager()
    project = pm.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    output_path = project.project_path / "outputs" / "meeting_output.json"
    if not output_path.exists():
        return {"output": None}

    with open(output_path, "r", encoding="utf-8") as f:
        return {"output": json.load(f)}


@router.put("/projects/{project_id}/meeting/output")
async def update_meeting_output(project_id: str, data: dict):
    pm = get_project_manager()
    project = pm.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    output_path = project.project_path / "outputs" / "meeting_output.json"
    if not output_path.exists():
        raise HTTPException(status_code=404, detail="Output not found")

    with open(output_path, "r", encoding="utf-8") as f:
        output = json.load(f)

    output.update(data)
    output["updated_at"] = datetime.now().isoformat()

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    return {"status": "updated", "output": output}


def _load_worldbook(project_path) -> str:
    worldbook_path = project_path / "worldbook.json"
    if worldbook_path.exists():
        try:
            with open(worldbook_path, "r", encoding="utf-8") as f:
                wb_data = json.load(f)
                entries = wb_data.get("entries", [])
                if entries:
                    return "\n".join([
                        f"- {e.get('keys', [''])[0]}: {e.get('content', '')[:100]}..."
                        for e in entries[:10]
                    ])
        except Exception:
            pass
    return "暂无世界书"


# ── 画布设计保存/加载 ─────────────────────────────────────────


@router.get("/projects/{project_id}/meeting/design")
async def get_meeting_design(project_id: str):
    pm = get_project_manager()
    project = pm.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    design_path = project.project_path / "pipeline" / "meeting_design.json"
    if not design_path.exists():
        return {"design": None}
    
    with open(design_path, "r", encoding="utf-8") as f:
        return {"design": json.load(f)}


@router.put("/projects/{project_id}/meeting/design")
async def save_meeting_design(project_id: str, data: dict):
    pm = get_project_manager()
    project = pm.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    design_path = project.project_path / "pipeline" / "meeting_design.json"
    design_path.parent.mkdir(parents=True, exist_ok=True)
    
    design = {
        "meeting_name": data.get("meeting_name", "专家会议"),
        "granularity": data.get("granularity", "chapter"),
        "collaboration_mode": data.get("collaboration_mode", "semi_auto"),
        "max_rounds": data.get("max_rounds", 3),
        "nodes": data.get("nodes", []),
        "edges": data.get("edges", []),
        "updated_at": datetime.now().isoformat()
    }
    
    with open(design_path, "w", encoding="utf-8") as f:
        json.dump(design, f, ensure_ascii=False, indent=2)
    
    return {"status": "saved", "design": design}
