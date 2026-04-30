from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from backend.core.registry import discover_modules
from backend.core.config import load_config


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_config()
    discover_modules()
    yield


app = FastAPI(
    title="AI Web Novel Creator",
    description="AI-assisted web novel creation system with 4-layer waterfall model",
    version="0.1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"status": "ok", "message": "AI Web Novel Creator API"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


from backend.api import projects, l1, l1_5, l2, l3, l4, worldbook, rag, settings, worldbook_manager, library

app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(l1.router, prefix="/api", tags=["l1"])
app.include_router(l1_5.router, prefix="/api", tags=["l1_5"])
app.include_router(l2.router, prefix="/api", tags=["l2"])
app.include_router(l3.router, prefix="/api", tags=["l3"])
app.include_router(l4.router, prefix="/api", tags=["l4"])
app.include_router(worldbook.router, prefix="/api", tags=["worldbook"])
app.include_router(worldbook_manager.router, prefix="/api", tags=["worldbook_manager"])
app.include_router(rag.router, prefix="/api", tags=["rag"])
app.include_router(settings.router, prefix="/api", tags=["settings"])
app.include_router(library.router, prefix="/api", tags=["library"])
