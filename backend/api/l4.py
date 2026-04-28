from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import json
from datetime import datetime

from backend.services.project_manager import get_project_manager
from backend.services.meeting_logger import MeetingLogger
from backend.modules.worldbook.st_style import STStyleWorldBook
from backend.core.protocols.l4 import ChapterPlan
from backend.core.registry import get_module, discover_modules

router = APIRouter()


def sse_format(event_type: str, data: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.get("/projects/{project_id}/l4/stream")
async def l4_stream(project_id: str):
    discover_modules()
    
    pm = get_project_manager()
    project = pm.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    plan_path = project.project_path / "outputs" / "l3_chapter_plan.json"
    if not plan_path.exists():
        raise HTTPException(status_code=404, detail="Chapter plan not found, please run L3 first")
    
    with open(plan_path, "r", encoding="utf-8") as f:
        plan_data = json.load(f)
    
    chapter_plan = ChapterPlan(**plan_data)
    world_book = STStyleWorldBook(project.project_path)
    
    strategy_cls = get_module("l4", "constrained")
    strategy = strategy_cls()
    
    async def generate():
        yield sse_format("start", {"chapter_name": chapter_plan.chapter_name})
        
        full_text = ""
        
        for i, scene in enumerate(chapter_plan.scenes):
            yield sse_format("scene_start", {
                "scene_index": i,
                "scene_name": scene.get("name", f"场景{i+1}")
            })
            
            for chunk in strategy.stream_render(chapter_plan, world_book=world_book):
                if chunk:
                    full_text += chunk
                    yield sse_format("text", {"content": chunk})
            
            yield sse_format("scene_end", {"scene_index": i})
        
        word_count = len(full_text.replace(" ", "").replace("\n", ""))
        
        generated_text = {
            "chapter_name": chapter_plan.chapter_name,
            "content": full_text,
            "word_count": word_count
        }
        
        output_path = project.project_path / "outputs" / "l4_text.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(generated_text, f, ensure_ascii=False, indent=2)
        
        text_path = project.project_path / "outputs" / f"{chapter_plan.chapter_name}.txt"
        with open(text_path, "w", encoding="utf-8") as f:
            f.write(full_text)
        
        logger = MeetingLogger(project.project_path / "logs" / "meeting.db")
        logger.log_version(project_id, "l4", generated_text, f"L4 text generated: {word_count} chars")
        
        yield sse_format("done", {
            "word_count": word_count,
            "message": "Chapter generated successfully"
        })
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.get("/projects/{project_id}/l4/text")
async def get_text(project_id: str):
    pm = get_project_manager()
    project = pm.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    text_path = project.project_path / "outputs" / "l4_text.json"
    if not text_path.exists():
        raise HTTPException(status_code=404, detail="Text not found")
    
    with open(text_path, "r", encoding="utf-8") as f:
        text = json.load(f)
    
    return {"text": text}
