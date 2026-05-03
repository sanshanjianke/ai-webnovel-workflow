# AGENTS.md

## Project Overview

AI-assisted web novel creation system. 4-layer waterfall model: L1 (seed/vision) → L2 (architecture/outline) → L3 (narrative/chapter plan) → L4 (rendering/final text). B/S architecture with Python/FastAPI backend and Vue frontend. Modular plugin system — every component is an ABC interface with swappable implementations registered via plugin directory auto-discovery.

## How to Run

```bash
git clone {repo} && cd ai-webnovel
./start.sh     # creates venv, installs deps, starts server on :7860
```

Chroma runs embedded. SQLite zero-config. No Docker required.

## Tech Stack

| Layer | Tech |
|-------|------|
| Backend | Python 3.11+, FastAPI |
| Frontend | Vue 3, markdown-it |
| Realtime | SSE (Server-Sent Events), browser-native EventSource |
| Vector DB | Chroma (embedded) |
| Data | JSON (core data) + SQLite (logs) |
| LLM | OpenAI-compatible API, `BaseLLMProvider` interface |

## Directory Structure

> 标注 `TBD` 的目录为待创建。当前已有 `hybrid_rag_prototype/`、`.claude/skills/`、`papers/`、笔记及 L1-L4 技能文档。

```
backend/                       # TBD — Python/FastAPI
├── main.py                    # FastAPI app entry point
├── core/
│   ├── protocols/             # ABC interfaces (all pluggable components)
│   ├── registry.py            # Plugin auto-discovery + registration
│   └── pipeline.py            # PipelineEngine orchestrates L1→L4
├── modules/                   # Swappable implementations
│   ├── rag/                   # RAG retrievers
│   ├── worldbook/             # World Book implementations
│   ├── llm/                   # LLM providers
│   ├── l1/                    # Seed generators
│   ├── l2/                    # L2 strategies + experts
│   ├── l3/                    # L3 strategies
│   └── l4/                    # L4 strategies
├── meeting_protocols/         # Auto-discovered meeting protocols
├── api/                       # FastAPI route handlers
├── services/                  # Independent services (worldbook_manager, rag_indexer)
└── tests/                     # pytest test suite

data/                          # TBD — runtime data
├── user/                      # User-level: config, tags, prompts, templates
└── projects/{name}/           # Project-level: worldbook, outputs, logs

frontend/                      # TBD — Vue 3
├── src/
│   ├── pages/                 # 7 page components
│   ├── components/            # chat/, tags/, outline/
│   └── lib/sse.js             # EventSource wrapper
├── package.json
└── tests/

hybrid_rag_prototype/          # ✅ 已有 — 笔记7的RAG原型
.claude/skills/                # ✅ 已有 — L1-L4技能定义
papers/                        # ✅ 已有 — 参考论文
```

## Coding Conventions

### Python
- Type hints on all public methods
- Use `ABC` + `@abstractmethod` for all protocols
- All LLM calls go through `BaseLLMProvider` — never use provider SDKs directly
- Module registration keys: lowercase_snake_case of class name
- Config: YAML, loaded at startup, writable via Settings page
- SSE streams: always yield a final `done` event

### Frontend
- Vue 3 Composition API, single-file components
- Markdown rendering: markdown-it (buffer incomplete blocks during streaming)
- SSE: browser-native EventSource, no WebSocket library

## Adding a New Module

1. Create `.py` file in the appropriate `backend/modules/{category}/` subdirectory
2. Subclass the matching ABC from `backend/core/protocols/`
3. Registry auto-discovers it by scanning for ABC subclasses
4. Set the config key to use it: module key = class name in lowercase_snake_case

Example: `backend/modules/rag/graph_rag.py` → class `GraphRAGRetriever(BaseRAGAgent)` → config key `graph_rag_retriever`

## Running Tests

```bash
# Backend tests
cd backend && pytest

# Frontend tests
cd frontend && npm run test
```

## Reference Documents

Design specifications and implementation details:
- `系统设计文档.md` — Architecture, protocols, API specs, data structures
- `开发计划.md` — Task breakdown and implementation order
- `笔记1-10.md` — Theoretical foundations and design rationale (supplementary)
