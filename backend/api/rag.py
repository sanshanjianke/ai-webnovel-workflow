from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import json
from pathlib import Path

from backend.services.project_manager import get_project_manager
from backend.core.registry import get_module, discover_modules
from backend.core.protocols.rag import Document

router = APIRouter()


class SearchRequest(BaseModel):
    query: str
    k: int = 5


class IndexRequest(BaseModel):
    documents: List[dict]


@router.post("/projects/{project_id}/rag/search")
async def rag_search(project_id: str, request: SearchRequest):
    discover_modules()
    
    pm = get_project_manager()
    project = pm.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    rag_path = project.project_path / "rag"
    rag_path.mkdir(parents=True, exist_ok=True)
    
    retriever_cls = get_module("rag", "simple_vector")
    retriever = retriever_cls(persist_dir=str(rag_path))
    
    results = retriever.retrieve(request.query, k=request.k)
    
    return {
        "query": request.query,
        "results": [r.model_dump() for r in results]
    }


@router.post("/projects/{project_id}/rag/index")
async def rag_index(project_id: str, request: IndexRequest):
    discover_modules()
    
    pm = get_project_manager()
    project = pm.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    rag_path = project.project_path / "rag"
    rag_path.mkdir(parents=True, exist_ok=True)
    
    retriever_cls = get_module("rag", "simple_vector")
    retriever = retriever_cls(persist_dir=str(rag_path))
    
    documents = [
        Document(**doc) for doc in request.documents
    ]
    
    retriever.index(documents)
    
    return {
        "status": "indexed",
        "count": len(documents),
        "total": retriever.count()
    }


@router.get("/projects/{project_id}/rag/stats")
async def rag_stats(project_id: str):
    discover_modules()
    
    pm = get_project_manager()
    project = pm.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    rag_path = project.project_path / "rag"
    if not rag_path.exists():
        return {"count": 0}
    
    retriever_cls = get_module("rag", "simple_vector")
    retriever = retriever_cls(persist_dir=str(rag_path))
    
    return {"count": retriever.count()}
