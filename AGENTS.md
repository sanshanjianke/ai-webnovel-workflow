# AGENTS.md

## Project Overview

AI-assisted web novel creation system. 4-layer waterfall model: L1 (seed/vision) → L2 (architecture/outline) → L3 (narrative/chapter plan) → L4 (rendering/final text). B/S architecture with Python/FastAPI backend and Vue frontend. Modular plugin system — every component is an ABC interface with swappable implementations registered via plugin directory auto-discovery.

## Tech Stack

| Layer | Tech |
|-------|------|
| Backend | Python 3.11+, FastAPI |
| Frontend | Vue 3, markdown-it |
| Realtime | SSE (Server-Sent Events), browser-native EventSource |
| Vector DB | Chroma (embedded, no standalone service) |
| Data | JSON files (core data) + SQLite (logs) |
| LLM | OpenAI-compatible API, unified `BaseLLMProvider` interface |
| Deployment | `start.sh`/`start.bat`, no Docker |

## Directory Structure

```
backend/
├── main.py                    # FastAPI app, SSE endpoints
├── core/
│   ├── protocols/             # ABC interfaces
│   │   ├── rag.py             # BaseRAGAgent
│   │   ├── worldbook.py       # BaseWorldBook
│   │   ├── llm.py             # BaseLLMProvider
│   │   ├── expert.py          # BaseExpert
│   │   ├── meeting.py         # BaseMeetingProtocol
│   │   ├── l1.py              # BaseSeedGenerator
│   │   ├── l2.py              # BaseL2Architect
│   │   ├── l3.py              # BaseL3Narrative
│   │   └── l4.py              # BaseL4Renderer
│   ├── registry.py            # Plugin auto-discovery + registration
│   └── pipeline.py            # PipelineEngine (L1→L2→L3→L4 orchestration)
├── modules/
│   ├── rag/                   # RAG implementations
│   │   ├── hybrid.py          # HybridRetriever (向量+关键词)
│   │   └── simple.py          # SimpleVectorRetriever
│   ├── worldbook/
│   │   └── st_style.py        # SillyTavern-style World Book
│   ├── llm/
│   │   └── openai_compat.py   # OpenAI-compatible provider
│   ├── l1/
│   │   └── guided_form.py     # GuidedFormGenerator
│   ├── l2/
│   │   ├── expert_meeting.py  # ExpertMeetingL2
│   │   └── experts/           # Expert implementations
│   │       ├── architect.py   # PlotArchitect (v1=Propp, v2=multi-dim)
│   │       ├── editor.py      # WebEditor
│   │       └── character.py   # CharacterDesigner
│   ├── l3/
│   │   └── mapping_compiler.py  # MappingCompilerL3
│   └── l4/
│       └── constrained.py     # ConstrainedRenderer
├── meeting_protocols/         # Auto-discovered meeting protocols
│   ├── character_driven.py
│   ├── plot_driven.py
│   └── market_driven.py
├── api/
│   ├── projects.py
│   ├── l1.py
│   ├── l2.py                  # SSE streaming endpoints
│   ├── l3.py
│   ├── l4.py
│   ├── worldbook.py
│   └── tags.py
└── services/
    ├── worldbook_manager.py   # Administrator Agent logic
    └── rag_indexer.py         # Dual-layer indexing (keyword + vector)

data/                          # Runtime data (user-level + project-level)
├── user/
│   ├── config.yaml
│   ├── tags/l3_tags.json, l4_tags.json
│   ├── prompts/
│   └── templates/
└── projects/{name}/
    ├── project.json
    ├── worldbook.json
    ├── outputs/
    └── logs/meeting.db

frontend/
├── src/
│   ├── pages/
│   │   ├── Dashboard.vue
│   │   ├── L1Seed.vue
│   │   ├── L2Meeting.vue      # Chat-style expert meeting
│   │   ├── L3Narrative.vue    # Tag-based instruction editor
│   │   ├── L4Render.vue
│   │   ├── WorldBook.vue
│   │   └── Settings.vue
│   ├── components/
│   │   ├── chat/              # Chat bubble, expert card, decision buttons
│   │   ├── tags/              # Tag library panel, tag badge, drag-drop
│   │   └── outline/           # Outline tree, preview
│   └── lib/
│       └── sse.js             # EventSource wrapper
└── package.json
```

## Core Abstractions (ABCs)

Every pluggable component implements one of these abstract base classes. New implementations go in `backend/modules/` and are auto-discovered.

### BaseRAGAgent
```python
class BaseRAGAgent(ABC):
    def retrieve(self, query: str, context: dict) -> list[RetrievedDoc]: ...
    def index(self, documents: list[Document]) -> None: ...
```
Two roles: `rag_history` (indexes current work, dynamic) and `rag_technique` (pre-built static knowledge base).

### BaseWorldBook
```python
class BaseWorldBook(ABC):
    def get_active_entries(self, tokens: list[str]) -> list[Entry]: ...
    def update_entry(self, id: str, data: dict) -> None: ...
    def commit(self, message: str) -> str: ...      # returns commit hash
    def revert(self, hash: str) -> None: ...
```
Reference implementation: ST-style (JSON + trigger key regex + recursive activation + version chain).

### BaseLLMProvider
```python
class BaseLLMProvider(ABC):
    def invoke(self, prompt: str, **kw) -> str: ...
    def stream(self, prompt: str, **kw) -> Iterator[str]: ...
```
User configures API endpoint/key via settings page. Internal code only calls `invoke`/`stream`, never deals with provider-specific APIs.

### BaseExpert
```python
class BaseExpert(ABC):
    def speak(self, outline: Outline, context: dict) -> ExpertOpinion: ...
```
Three experts: `PlotArchitect` (剧情架构师), `WebEditor` (网络编辑), `CharacterDesigner` (人物设计师). The architect has two versions: v1 uses Propp functions, v2 uses the multi-dimensional annotation matrix.

### BaseMeetingProtocol
```python
class BaseMeetingProtocol(ABC):
    def get_speaking_order(self, context: dict) -> list[tuple[str, str]]: ...
        # returns [(expert_id, speech_type)]  speech_type: main|review|supplement
    def should_continue(self, rounds: int, consensus: float) -> bool: ...
    def format_output(self, history: list[ExpertOpinion]) -> Outline: ...
```
Auto-discovered from `meeting_protocols/` directory. Three built-in: `character_driven`, `plot_driven`, `market_driven`.

### Pipeline Layers
```python
class BaseSeedGenerator(ABC):
    def generate(self, user_input: dict) -> VisionDocument: ...

class BaseL2Architect(ABC):
    def generate_outline(self, vision, world_book, rag_history, rag_technique, llm, human_feedback: Callable) -> Outline: ...

class BaseL3Narrative(ABC):
    def generate_chapter_plan(self, outline, rag_technique, world_book) -> ChapterPlan: ...

class BaseL4Renderer(ABC):
    def render(self, plan, rag_technique, world_book) -> GeneratedText: ...
```

## Plugin Registration

All modules are auto-discovered from `backend/modules/` and `backend/meeting_protocols/`. Implementation files must:
1. Import and subclass the appropriate ABC from `core/protocols/`
2. Export the implementation class (public name)

The registry scans `.py` files for classes that inherit from registered ABCs. Config file selects which implementation to use by its registry key, not by class path.

## Configuration

`user/config.yaml` controls module selection:
```yaml
pipeline:
  l2:
    meeting_protocol: plot_driven       # character_driven|plot_driven|market_driven
    collaboration_mode: semi_auto       # manual|semi_auto|full_auto
    max_rounds: 3
    experts:
      architect: plot_architect_v2
      editor: web_editor_v1
      character: character_designer_v1
  l3:
    strategy: mapping_compiler
  l4:
    strategy: constrained_renderer
rag:
  history: hybrid_retriever
  technique: simple_vector
worldbook:
  strategy: st_style
  auto_manage: true
llm:
  primary: glm-5
  embedding: text-embedding-v3
```

## API Conventions

- REST POST/GET for user operations (project CRUD, config, label submission, decision actions)
- SSE for all LLM streaming (expert speeches, L4 text generation)
- SSE format: `event: {type}\ndata: {json}\n\n`
- SSE event types: `expert_speak`, `user_message`, `rag_insert`, `worldbook_insert`, `waiting_user`, `error`, `done`
- Frontend uses browser-native `EventSource` (no WebSocket library needed)

## L2 Expert Meeting (Chat-Style UI)

The L2 page is a group-chat interface (like Discord/Slack), NOT a canvas/flowchart editor:
- Each role has a distinct color and avatar
- User can interject anytime (input box always active)
- Experts can `@mention` other experts
- RAG and World Book agents auto-insert as bot messages (not user-triggered)
- Bottom decision bar: 通过 ✓ / 要求修改 ✎ / 驳回 ↩
- Right panel shows real-time outline preview

Collaboration modes:
- `semi_auto`: pause after each expert speech, user clicks "继续" to advance
- `full_auto`: experts auto-speak; if user types a message, auto-switches to semi_auto
- `manual`: user specifies which expert speaks next

## L3/L4 Tag-Based Instruction System

L3/L4 use drag-and-drop tag system instead of free-text:
- Each tag is a JSON object with `id`, `name`, `category`, `layer`, `prompt`, `conflicts[]`, `synergies[]`, `example`
- Tags stored in `user/tags/l3_tags.json` and `user/tags/l4_tags.json` (user-level, shared across projects)
- Users can: (1) edit instruction text directly, (2) drag tags from panel, (3) delete tags, (4) click tag to edit its prompt
- Tag `conflicts` are enforced (mutually exclusive tags can't co-exist)
- Tag `synergies` are highlighted as recommendations
- Users can save tag combinations as custom templates

L3 tags: perspective, pacing, information control, discourse mode, emotion anchors
L4 tags: style, sentence patterns, descriptive techniques, narrative-to-text (★), reference examples

## Multi-Dimensional Function Annotation

L2 output table columns (upgraded from simple "功能+情绪"):
```
| # | 功能简述 | 剧情轴 | 人物轴 | 世界轴 | 读者效果 | 情绪 | 人物 | 说明 |
```

Annotation axes and who assigns them:
- 剧情轴 (推进/转折/铺垫/阻碍/回收/承接) → PlotArchitect
- 人物轴 (揭示特性/触发成长/确立关系/制造矛盾/展示能力/施加压力) → CharacterDesigner
- 世界轴 (展示设定/营造氛围/建立规则/拓展地图/强化画面感) → PlotArchitect + CharacterDesigner
- 读者效果 (期待感/满足感/代入感/爽感/惊喜感, with ↑↓ intensity) → WebEditor

The 读者效果 column is the L3 input — L3 no longer needs to reverse-engineer reader effects:
```
爽感+爆发  → 外聚焦 + 短句动词密集
期待感+压抑 → 反派内聚焦 + 慢速扩述 + 大量对话
满足+余韵  → 自由间接引语 + 快速概述
```

Propp's 6 functions are retained as shortcuts: 获得→推进, 禁令→铺垫, 违背→转折, 斗争→阻碍/推进, 胜利→转折/回收, 失败→阻碍.

## World Book (State Management)

4-layer structure: 核心层(permanent) → 活跃层(real-time updates) → 归档层(compressed summaries) → 索引层(metadata).

Entry format (ST-inspired JSON):
- `id`, `keys[]` (primary triggers), `secondary_keys[]`
- `content` (structured state text)
- `constant` (always active vs. selective), `priority`, `position` (injection placement), `selective`

Key behaviors:
- **Version chain**: character state stored as `[ch1-30:筑基]→[ch31-80:金丹]→[ch81-now:元婴]`, never overwritten
- **Importance decay**: weight +1 on reference, -1 after 10 unreferenced chapters, archive at zero
- **Auto-compression**: completed sequences compressed to one-line summaries in archive layer
- **Trigger word self-maintenance**: Administrator Agent monitors and optimizes triggers

## World Book Administrator Agent

Meta-layer agent, post-processing only. Runs after each sequence/chapter completion:
1. Read output → extract changes (characters, items, relationships, foreshadowing, factions)
2. Update entries
3. Conflict detection (vs. existing settings) → warn user if found
4. Compress/archive old entries
5. Produce: updated World Book + change summary

## RAG System

Two distinct RAG roles, each with separate index and lifecycle:
- **RAG-历史回顾**: indexes current work's generated content (dynamic, updated per sequence). Uses multi-dimensional slicing (plot/character/emotion/function). Results Agent-compressed before injection.
- **RAG-技法参考**: pre-built static knowledge base (L3 mapping rules, L4 technique examples). Rarely updated.

History indexing uses dual-layer strategy for real-time availability:
```
Sequence complete → immediate keyword inverted index (seconds, low precision)
                  → async background vector index pipeline (~25 min, high precision)
Retrieval: use vector if indexed, fall back to keyword
```

## Data Persistence

| Data | Format | Rationale |
|------|--------|-----------|
| World Book entries | JSON | Human-readable, small volume |
| Project config | JSON | Config files are naturally text |
| L1-L4 outputs | JSON/Markdown | Documents, not database records |
| Meeting logs | SQLite | Append-only, time-ordered queries, large volume |
| Version history | SQLite | Same |

User-level data (tags, prompts, templates) in `data/user/`, shared across projects.
Project-level data in `data/projects/{name}/`, isolated per book.

## Error Handling

Behavior depends on collaboration mode:
- `semi_auto`: retry once on timeout → show error in chat (NOT in prompt context) → user decides skip/retry
- `full_auto`: retry until success (unattended)

SSE interruption: EventSource auto-reconnects, frontend preserves received text. User chooses: continue (pass breakpoint as context, resume generation) or restart (delete, regenerate from scratch).

## Coding Conventions

- Python: type hints on all public methods, use `ABC` + `@abstractmethod` for protocols
- All LLM calls go through `BaseLLMProvider` — never use provider SDKs directly
- Module registration keys: lowercase_snake_case matching the class name minus implementation suffix
- Config: YAML, loaded at startup, mutable via Settings page
- Frontend: Vue 3 Composition API, single-file components
- SSE streams: always yield a final `done` event to signal stream completion to frontend

## Deployment

```bash
git clone {repo} && cd ai-webnovel
./start.sh     # creates venv, installs deps, starts server on :7860
```
Chroma runs embedded. SQLite zero-config.
