from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import json
from datetime import datetime

from backend.services.project_manager import get_project_manager
from backend.services.meeting_logger import MeetingLogger
from backend.core.registry import get_module
from backend.core.config import get_config

router = APIRouter()


class L1Input(BaseModel):
    idea: str = ""
    target_readers: str = ""
    core_appeal: str = ""
    style: str = ""
    outline: str = ""  # 兼容旧字段
    rough_outline: str = ""  # 新字段名，与 VisionDocument 一致
    world_setting: str = ""
    protagonist: str = ""
    golden_finger: str = ""
    hot_elements: str = ""
    expected_length: str = ""
    
    def get_outline(self) -> str:
        """获取大纲内容，优先使用 rough_outline"""
        return self.rough_outline or self.outline


@router.post("/projects/{project_id}/l1/generate")
async def generate_vision(project_id: str, data: L1Input):
    pm = get_project_manager()
    project = pm.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    config = get_config()
    generator_cls = get_module("l1", "guided_form")
    generator = generator_cls()
    
    # 构建输入数据，统一字段名
    input_data = data.model_dump()
    input_data["outline"] = data.get_outline()  # 使用统一的大纲字段
    
    vision = generator.generate(input_data)
    
    vision_path = project.project_path / "outputs" / "l1_vision.json"
    vision_path.parent.mkdir(parents=True, exist_ok=True)
    
    vision_data = vision.model_dump()
    vision_data["created_at"] = datetime.now().isoformat()
    
    with open(vision_path, "w", encoding="utf-8") as f:
        json.dump(vision_data, f, ensure_ascii=False, indent=2)
    
    logger = MeetingLogger(project.project_path / "logs" / "meeting.db")
    logger.log_version(project_id, "l1", vision_data, "L1 vision generated")
    
    return {"status": "generated", "vision": vision_data}


@router.get("/projects/{project_id}/l1/vision")
async def get_vision(project_id: str):
    pm = get_project_manager()
    project = pm.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    vision_path = project.project_path / "outputs" / "l1_vision.json"
    if not vision_path.exists():
        raise HTTPException(status_code=404, detail="Vision not found")
    
    with open(vision_path, "r", encoding="utf-8") as f:
        vision_data = json.load(f)
    
    return {"vision": vision_data}


@router.put("/projects/{project_id}/l1/vision")
async def update_vision(project_id: str, data: dict):
    pm = get_project_manager()
    project = pm.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    vision_path = project.project_path / "outputs" / "l1_vision.json"
    if not vision_path.exists():
        raise HTTPException(status_code=404, detail="Vision not found")
    
    with open(vision_path, "r", encoding="utf-8") as f:
        vision_data = json.load(f)
    
    vision_data.update(data)
    vision_data["updated_at"] = datetime.now().isoformat()
    
    with open(vision_path, "w", encoding="utf-8") as f:
        json.dump(vision_data, f, ensure_ascii=False, indent=2)
    
    return {"status": "updated", "vision": vision_data}


# L1 聊天引导
class ChatMessage(BaseModel):
    role: str
    content: str


class L1ChatRequest(BaseModel):
    messages: list[ChatMessage]
    currentForm: dict = {}


class L1ChatResponse(BaseModel):
    reply: str
    extracted: dict = {}


@router.post("/projects/{project_id}/l1/chat")
async def l1_chat(project_id: str, req: L1ChatRequest):
    pm = get_project_manager()
    project = pm.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    config = get_config()
    llm_cls = get_module("llm", config.llm.primary)
    llm = llm_cls()
    
    # 构建对话上下文
    system_prompt = """你是L1种子层的创作引导助手。你的任务是通过对话帮助用户梳理小说创意。

对话策略：
1. 每次只问一个问题，逐步引导
2. 根据用户回答，自然地追问下一个要素
3. 当收集到足够信息时，可以主动总结
4. 保持友好、专业的语气

需要收集的要素（按优先级）：
- 类型/题材（重生/玄幻/科幻等）
- 主角人设
- 金手指/核心能力
- 核心爽点
- 世界观背景
- 风格基调
- 粗略大纲

当前对话阶段：根据已有信息判断下一步该问什么。"""

    messages = [{"role": "system", "content": system_prompt}]
    
    for msg in req.messages:
        messages.append({"role": "user" if msg.role == "user" else "assistant", "content": msg.content})
    
    # 简单的信息提取逻辑
    extracted = {}
    last_user_msg = req.messages[-1].content if req.messages and req.messages[-1].role == "user" else ""
    
    # 提取类型
    genres = ["重生", "穿越", "玄幻", "修仙", "科幻", "都市", "历史", "架空", "网游", "末日"]
    for g in genres:
        if g in last_user_msg:
            extracted["genre"] = g
            break
    
    # 提取金手指关键词
    if "系统" in last_user_msg:
        extracted["golden_finger"] = "系统"
    elif "重生" in last_user_msg and "记忆" in last_user_msg:
        extracted["golden_finger"] = "前世记忆"
    
    # 提取核心梗（限制长度）
    if len(last_user_msg) > 10 and len(last_user_msg) < 100:
        extracted["idea"] = last_user_msg
    
    # 生成SSE流
    def generate():
        full_response = ""
        try:
            for chunk in llm.stream("", messages=messages, temperature=0.8):
                full_response += chunk
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk}, ensure_ascii=False)}\n\n"
            
            # 发送完成事件
            yield f"data: {json.dumps({'type': 'done', 'content': full_response, 'extracted': extracted}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/projects/{project_id}/l1/draft")
async def get_draft(project_id: str):
    pm = get_project_manager()
    project = pm.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    draft_path = project.project_path / "outputs" / "l1_draft.json"
    if not draft_path.exists():
        return {"draft": None}
    
    with open(draft_path, "r", encoding="utf-8") as f:
        draft_data = json.load(f)
    
    return {"draft": draft_data}


@router.post("/projects/{project_id}/l1/draft")
async def save_draft(project_id: str, data: dict):
    pm = get_project_manager()
    project = pm.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    draft_path = project.project_path / "outputs" / "l1_draft.json"
    draft_path.parent.mkdir(parents=True, exist_ok=True)
    
    data["updated_at"] = datetime.now().isoformat()
    
    with open(draft_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    return {"status": "saved"}


@router.get("/projects/{project_id}/l1/chat-history")
async def get_chat_history(project_id: str):
    pm = get_project_manager()
    project = pm.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    history_path = project.project_path / "outputs" / "l1_chat_history.json"
    if not history_path.exists():
        return {"messages": []}
    
    with open(history_path, "r", encoding="utf-8") as f:
        history_data = json.load(f)
    
    return {"messages": history_data.get("messages", [])}


@router.post("/projects/{project_id}/l1/chat-history")
async def save_chat_history(project_id: str, data: dict):
    pm = get_project_manager()
    project = pm.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    history_path = project.project_path / "outputs" / "l1_chat_history.json"
    history_path.parent.mkdir(parents=True, exist_ok=True)
    
    history_data = {
        "messages": data.get("messages", []),
        "updated_at": datetime.now().isoformat()
    }
    
    with open(history_path, "w", encoding="utf-8") as f:
        json.dump(history_data, f, ensure_ascii=False, indent=2)
    
    return {"status": "saved"}
