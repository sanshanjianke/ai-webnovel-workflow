from fastapi import APIRouter
from backend.core.registry import list_modules, get_module, discover_modules
from backend.core.config import get_config, save_config, AppConfig

router = APIRouter()


@router.get("/modules")
async def list_all_modules():
    discover_modules()
    return {
        category: list_modules(category)
        for category in ["llm", "rag", "worldbook", "l1", "l2", "l3", "l4", "meeting_protocol"]
    }


@router.get("/config")
async def get_app_config():
    return get_config().model_dump()


@router.put("/config")
async def update_app_config(config: dict):
    current = get_config()
    updated = AppConfig(**{**current.model_dump(), **config})
    save_config(updated)
    return updated.model_dump()


@router.get("/tags/l3")
async def get_l3_tags():
    pass


@router.get("/tags/l4")
async def get_l4_tags():
    pass
