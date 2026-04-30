from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from typing import Optional, Union
from datetime import datetime
import json

from backend.services.project_manager import get_project_manager
from backend.services.library_manager import (
    get_library_manager,
    DocEntry,
    DocSource,
    DocStatus,
)

router = APIRouter()


class CreateDocRequest(BaseModel):
    name: str
    layer: str
    content: Union[dict, str]
    source: Optional[str] = "manual"
    parent_uid: Optional[str] = None
    directory: str = "/"
    tags: list[str] = []


class UpdateDocRequest(BaseModel):
    name: Optional[str] = None
    directory: Optional[str] = None
    tags: Optional[list[str]] = None
    status: Optional[str] = None


class UpdateContentRequest(BaseModel):
    content: Union[dict, str]


class SetActiveRequest(BaseModel):
    uid: str


class CreateDirectoryRequest(BaseModel):
    path: str


@router.get("/projects/{project_id}/library")
async def list_library(project_id: str, include_archived: bool = False):
    pm = get_project_manager()
    project = pm.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    library = get_library_manager(project.project_path)
    
    tree = library.get_tree(include_archived=include_archived)
    directories = library.manifest.directories
    
    return {
        "directories": directories,
        "tree": tree,
        "documents": [e.model_dump() for e in library.list_documents(include_archived=include_archived)],
        "active_docs": library.manifest.active_docs,
    }


@router.get("/projects/{project_id}/library/{uid}")
async def get_document(project_id: str, uid: str):
    pm = get_project_manager()
    project = pm.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    library = get_library_manager(project.project_path)
    result = library.get_document(uid)
    
    if not result:
        raise HTTPException(status_code=404, detail="Document not found")
    
    entry, content = result
    children = library.get_children(uid)
    provenance = library.get_provenance_chain(uid)
    
    return {
        "entry": entry.model_dump(),
        "content": content,
        "children": [c.model_dump() for c in children],
        "provenance": [p.model_dump() for p in provenance],
    }


@router.post("/projects/{project_id}/library")
async def create_document(project_id: str, data: CreateDocRequest):
    pm = get_project_manager()
    project = pm.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    library = get_library_manager(project.project_path)
    
    source_map = {
        "generate": DocSource.GENERATE,
        "import": DocSource.IMPORT,
        "manual": DocSource.MANUAL,
    }
    source = source_map.get(data.source, DocSource.MANUAL)
    
    uid = library.add_document(
        name=data.name,
        layer=data.layer,
        content=data.content,
        source=source,
        parent_uid=data.parent_uid,
        directory=data.directory,
        tags=data.tags,
    )
    
    return {"uid": uid, "entry": library.get_entry(uid).model_dump()}


@router.put("/projects/{project_id}/library/{uid}")
async def update_document(project_id: str, uid: str, data: UpdateDocRequest):
    pm = get_project_manager()
    project = pm.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    library = get_library_manager(project.project_path)
    
    update_data = {}
    if data.name is not None:
        update_data["name"] = data.name
    if data.directory is not None:
        update_data["directory"] = data.directory
    if data.tags is not None:
        update_data["tags"] = data.tags
    if data.status is not None:
        update_data["status"] = DocStatus(data.status)
    
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    entry = library.update_entry(uid, **update_data)
    if not entry:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return {"status": "updated", "entry": entry.model_dump()}


@router.put("/projects/{project_id}/library/{uid}/content")
async def update_content(project_id: str, uid: str, data: UpdateContentRequest):
    pm = get_project_manager()
    project = pm.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    library = get_library_manager(project.project_path)
    
    success = library.update_content(uid, data.content)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")
    
    entry = library.get_entry(uid)
    return {"status": "updated", "entry": entry.model_dump()}


@router.delete("/projects/{project_id}/library/{uid}")
async def delete_document(project_id: str, uid: str):
    pm = get_project_manager()
    project = pm.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    library = get_library_manager(project.project_path)
    
    success = library.delete_document(uid)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return {"status": "deleted"}


@router.put("/projects/{project_id}/library/{uid}/archive")
async def archive_document(project_id: str, uid: str, archive: bool = True):
    pm = get_project_manager()
    project = pm.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    library = get_library_manager(project.project_path)
    
    entry = library.archive_document(uid, archive)
    if not entry:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return {"status": "archived" if archive else "unarchived", "entry": entry.model_dump()}


@router.get("/projects/{project_id}/library/active/{layer}")
async def get_active_document(project_id: str, layer: str):
    pm = get_project_manager()
    project = pm.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    library = get_library_manager(project.project_path)
    result = library.get_active_document(layer)
    
    if not result:
        return {"uid": None, "entry": None, "content": None}
    
    entry, content = result
    return {"uid": entry.uid, "entry": entry.model_dump(), "content": content}


@router.put("/projects/{project_id}/library/active/{layer}")
async def set_active_document(project_id: str, layer: str, data: SetActiveRequest):
    pm = get_project_manager()
    project = pm.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    library = get_library_manager(project.project_path)
    
    success = library.set_active(layer, data.uid)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot set active: document not found or layer mismatch")
    
    return {"status": "set", "layer": layer, "uid": data.uid}


@router.post("/projects/{project_id}/library/import")
async def import_file(project_id: str, file: UploadFile = File(...)):
    pm = get_project_manager()
    project = pm.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    library = get_library_manager(project.project_path)
    
    content = await file.read()
    filename = file.filename or "imported_file"
    
    format = "json" if filename.endswith(".json") else "md" if filename.endswith(".md") else "txt"
    
    try:
        if format == "json":
            parsed_content = json.loads(content.decode("utf-8"))
        else:
            parsed_content = content.decode("utf-8")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {str(e)}")
    
    uid = library.import_file(
        name=f"导入 — {filename}",
        content=parsed_content,
        format=format,
    )
    
    return {"uid": uid, "entry": library.get_entry(uid).model_dump()}


@router.post("/projects/{project_id}/library/directories")
async def create_directory(project_id: str, data: CreateDirectoryRequest):
    pm = get_project_manager()
    project = pm.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    library = get_library_manager(project.project_path)
    
    success = library.create_directory(data.path)
    if not success:
        return {"status": "exists", "path": data.path}
    
    return {"status": "created", "path": data.path}


@router.delete("/projects/{project_id}/library/directories/{path:path}")
async def delete_directory(project_id: str, path: str):
    pm = get_project_manager()
    project = pm.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    library = get_library_manager(project.project_path)
    
    dir_path = "/" + path
    success = library.delete_directory(dir_path)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot delete root or non-existent directory")
    
    return {"status": "deleted", "path": dir_path}


@router.get("/projects/{project_id}/library/export/{uid}")
async def export_document(project_id: str, uid: str, format: str = "json"):
    pm = get_project_manager()
    project = pm.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    library = get_library_manager(project.project_path)
    result = library.get_document(uid)
    
    if not result:
        raise HTTPException(status_code=404, detail="Document not found")
    
    entry, content = result
    
    if format == "txt":
        if isinstance(content, dict):
            content = json.dumps(content, ensure_ascii=False, indent=2)
        return PlainTextResponse(content=content, media_type="text/plain")
    else:
        return {"entry": entry.model_dump(), "content": content}
