# AI Web Novel Creator — 项目现状文档

> 最后更新：2026-04-28  
> 状态：L1~L4 全流程打通，单元测试 19/19 通过，API 40 条路由正常运行

---

## 1. 项目概述

AI 辅助网文创作系统，四层瀑布模型：

```
L1 种子层 → L2 架构层 → L3 叙事层 → L4 渲染层
```

B/S 架构：Python/FastAPI 后端 + Vue 3 前端，模块化插件体系（ABC 接口 + 注册表自动发现）。

| 层 | 作用 | 输入 | 输出 |
|----|------|------|------|
| L1 种子层 | 将模糊创意梳理成结构化愿景 | 用户表单答案 | VisionDocument |
| L2 架构层 | 三专家会议拆解功能序列 | 愿景文档 | 精修大纲 |
| L3 叙事层 | 大纲翻译为章纲/细纲 | 大纲 | ChapterPlan |
| L4 渲染层 | 章纲生成正文 | 章纲 + 世界书 + RAG | 正文字符串 |

---

## 2. 目录结构

```
talk/
├── backend/                          # Python/FastAPI 后端（53 文件, ~3600 行）
│   ├── main.py                       # 入口，注册路由，lifespan 事件
│   ├── core/
│   │   ├── config.py                 # YAML 配置加载（LLM/RAG/WB/Pipeline）
│   │   ├── registry.py              # 插件注册表 + 自动发现
│   │   └── protocols/               # 9 个 ABC 接口
│   │       ├── llm.py               #   BaseLLMProvider
│   │       ├── rag.py               #   BaseRAGAgent
│   │       ├── worldbook.py         #   BaseWorldBook
│   │       ├── l1.py                #   BaseSeedGenerator
│   │       ├── l2.py                #   BaseL2Architect (未注册实现)
│   │       ├── l3.py                #   BaseL3Narrative
│   │       ├── l4.py                #   BaseL4Renderer
│   │       ├── expert.py            #   BaseExpert
│   │       └── meeting.py           #   BaseMeetingProtocol
│   ├── modules/                      # 可替换实现（注册表管理）
│   │   ├── llm/                     # LLM 提供商
│   │   │   ├── openai_compat.py     #   OpenAI 兼容接口（当前使用）
│   │   │   └── mock.py              #   测试用 mock
│   │   ├── rag/                     # RAG 检索引擎
│   │   │   └── simple_vector.py     #   Chroma 嵌入式向量检索
│   │   ├── worldbook/               # 世界书策略
│   │   │   └── st_style.py          #   SillyTavern 风格世界书
│   │   ├── l1/                      # 种子生成器
│   │   │   └── guided_form.py       #   引导表单式
│   │   ├── l2/                      # L2 架构层
│   │   │   ├── expert_meeting.py    #   专家会议编排器（非注册模块）
│   │   │   └── experts/
│   │   │       ├── architect.py     #   剧情架构师
│   │   │       ├── character.py     #   人物设计师
│   │   │       └── editor.py        #   网络编辑
│   │   ├── l3/                      # L3 叙事层
│   │   │   └── mapping_compiler.py  #   映射编译器
│   │   └── l4/                      # L4 渲染层
│   │       └── constrained.py       #   约束渲染器
│   ├── services/                    # 独立服务（非注册模块）
│   │   ├── project_manager.py       # 项目管理（JSON）
│   │   ├── meeting_logger.py        # 会议日志（SQLite）
│   │   └── worldbook_manager.py     # 世界书自动管理
│   ├── meeting_protocols/           # 三种会议协议
│   │   ├── plot_driven.py           # 剧情驱动
│   │   ├── character_driven.py      # 人物驱动
│   │   └── market_driven.py         # 市场驱动
│   ├── api/                         # FastAPI 路由（40 条）
│   └── tests/                       # pytest 测试（19 个）
│
├── frontend/                        # Vue 3 前端（10 源文件, ~1700 行）
│   ├── src/
│   │   ├── App.vue                  # 根组件 + 路由导航
│   │   ├── main.js                  # 入口
│   │   ├── lib/sse.js               # SSE 流包装器
│   │   └── pages/                   # 7 个页面
│   │       ├── Dashboard.vue        # 仪表盘
│   │       ├── L1Seed.vue           # L1 种子层
│   │       ├── L2Meeting.vue        # L2 专家会议
│   │       ├── L3Narrative.vue      # L3 叙事层
│   │       ├── L4Render.vue         # L4 渲染层
│   │       ├── WorldBook.vue        # 世界书管理
│   │       └── Settings.vue         # 系统设置
│   └── vite.config.js
│
├── data/
│   ├── user/config.yaml             # 运行时配置（含 API 密钥）
│   └── projects/                    # 项目数据（运行时生成）
│
├── .claude/skills/                  # L1-L4 技能定义（提示词模板）
├── start.sh                         # 一键启动脚本
└── AGENTS.md                        # AI 助手指南
```

---

## 3. 模块注册表

插件通过 `@register_module(category)` 装饰器注册，类名自动转换为 snake_case 作为 key（去除后缀）。

| 类别 | Key | 类名 | 父类 | 文件 |
|------|-----|------|------|------|
| llm | `mock` | MockLLM | BaseLLMProvider | modules/llm/mock.py |
| llm | `open_ai_compat` | OpenAICompat | BaseLLMProvider | modules/llm/openai_compat.py |
| rag | `simple_vector` | SimpleVectorRetriever | BaseRAGAgent | modules/rag/simple_vector.py |
| worldbook | `st_style` | STStyleWorldBook | BaseWorldBook | modules/worldbook/st_style.py |
| l1 | `guided_form` | GuidedFormGenerator | BaseSeedGenerator | modules/l1/guided_form.py |
| l3 | `mapping_compiler` | MappingCompiler | BaseL3Narrative | modules/l3/mapping_compiler.py |
| l4 | `constrained` | ConstrainedRenderer | BaseL4Renderer | modules/l4/constrained.py |
| expert | `plot_architect_v1` | PlotArchitectV1 | BaseExpert | modules/l2/experts/architect.py |
| expert | `character_designer_v1` | CharacterDesignerV1 | BaseExpert | modules/l2/experts/character.py |
| expert | `web_editor_v1` | WebEditorV1 | BaseExpert | modules/l2/experts/editor.py |
| meeting_protocol | `plot_driven` | PlotDriven | BaseMeetingProtocol | meeting_protocols/plot_driven.py |
| meeting_protocol | `character_driven` | CharacterDriven | BaseMeetingProtocol | meeting_protocols/character_driven.py |
| meeting_protocol | `market_driven` | MarketDriven | BaseMeetingProtocol | meeting_protocols/market_driven.py |

---

## 4. 核心数据流

```
用户输入表单
    │
    ▼
┌─────────────────┐
│   L1 种子层      │  GuidedFormGenerator.generate()
│   VisionDocument │  调用 LLM 生成结构化愿景
└────────┬────────┘
         │ vision
         ▼
┌─────────────────┐
│   L2 架构层      │  ExpertMeetingL2（非注册模块）
│   精修大纲       │  三专家按协议轮流发言（SSE 流式）
│                 │  支持 human-in-the-loop 反馈
└────────┬────────┘
         │ outline (Outline)
         ▼
┌─────────────────┐
│   L3 叙事层      │  MappingCompiler.generate_chapter_plan()
│   章纲/细纲      │  含视角、节奏、话语模式标注
└────────┬────────┘
         │ chapter_plan (ChapterPlan)
         ▼
┌─────────────────┐
│   L4 渲染层      │  ConstrainedRenderer.render()
│   正文          │  调用 LLM + 世界书 + RAG 约束
└─────────────────┘
```

**三元数据支撑**（贯穿 L2~L4）：

| 支撑 | 实现 | 作用 |
|------|------|------|
| 世界书 | STStyleWorldBook | 维护角色/设定/时间线等一致状态 |
| RAG-历史 | SimpleVectorRetriever | 检索已写章节，防止重复和矛盾 |
| RAG-技法 | SimpleVectorRetriever | 检索创作技法（开篇、打脸、节奏等） |

---

## 5. 三种会议协议

| 协议 | 发言顺序 | 适用场景 |
|------|----------|----------|
| plot_driven | architect → editor → character | 剧情驱动的快节奏爽文 |
| character_driven | character → architect → editor | 人物驱动的成长文 |
| market_driven | editor → architect → character | 市场导向的热点文 |

每个专家通过 `speak(outline, context) -> ExpertOpinion` 方法发言，内容包含多维功能标注（功能链、因果逻辑、情绪→视角映射等）。

---

## 6. API 路由总览（40 条）

| 类别 | 路径 | 方法 | 说明 |
|------|------|------|------|
| 系统 | `/` | GET | 根路由 |
| 系统 | `/health` | GET | 健康检查 |
| 系统 | `/api/modules` | GET | 列出所有注册模块 |
| 系统 | `/api/config` | GET/PUT | 获取/更新配置 |
| 项目管理 | `/api/projects/` | GET/POST | 列表/创建 |
| 项目管理 | `/api/projects/{id}` | GET/DELETE | 获取/删除 |
| 项目管理 | `/api/projects/{id}/config` | PUT | 更新配置 |
| L1 | `/api/projects/{id}/l1/generate` | POST | 生成愿景 |
| L1 | `/api/projects/{id}/l1/vision` | GET/PUT | 获取/更新愿景 |
| L2 | `/api/projects/{id}/l2/stream` | GET | SSE 会议流 |
| L2 | `/api/projects/{id}/l2/feedback` | POST | 人工反馈 |
| L2 | `/api/projects/{id}/l2/outline` | GET/PUT | 大纲管理 |
| L3 | `/api/projects/{id}/l3/generate` | POST | 生成章纲 |
| L3 | `/api/projects/{id}/l3/plan` | GET/PUT | 章纲管理 |
| L4 | `/api/projects/{id}/l4/stream` | GET | SSE 渲染流 |
| L4 | `/api/projects/{id}/l4/text` | GET | 获取正文 |
| 世界书 | `/api/projects/{id}/worldbook` | GET/POST | 列表/创建条目 |
| 世界书 | `/api/projects/{id}/worldbook/commit` | POST | 提交版本 |
| 世界书 | `/api/projects/{id}/worldbook/commits` | GET | 版本历史 |
| 世界书 | `/api/projects/{id}/worldbook/entry/{eid}` | GET/PUT/DELETE | 条目 CRUD |
| 世界书 | `/api/projects/{id}/worldbook/process-sequence` | POST | 自动处理序列 |
| 世界书 | `/api/projects/{id}/worldbook/auto-commit` | POST | 自动提交 |
| RAG | `/api/projects/{id}/rag/search` | POST | 语义搜索 |
| RAG | `/api/projects/{id}/rag/index` | POST | 索引文档 |
| RAG | `/api/projects/{id}/rag/stats` | GET | 统计信息 |

---

## 7. 配置项

`data/user/config.yaml`：

```yaml
llm:
  primary: open_ai_compat       # 当前 LLM 模块 key
  model: GLM-5                  # 模型名称
  api_key: "***"                # API 密钥
  base_url: "https://..."       # API 地址

rag:
  history: hybrid_retriever     # 历史回顾策略（仅配置，未实现 hybrid）
  technique: simple_vector      # 技法检索策略

worldbook:
  strategy: st_style
  auto_manage: true

pipeline:
  l2:
    meeting_protocol: plot_driven  # 默认会议协议
    collaboration_mode: semi_auto  # 半自动模式
    max_rounds: 3                  # 最大轮次
    experts:
      architect: plot_architect_v1
      editor: web_editor_v1
      character: character_designer_v1
  l3:
    strategy: mapping_compiler
  l4:
    strategy: constrained_renderer
```

---

## 8. 数据库

| 数据库 | 引擎 | 存储 |
|--------|------|------|
| 项目数据 | JSON 文件 | `data/projects/{id}/project.json` |
| 世界书 | JSON 文件 | `data/projects/{id}/worldbook.json` |
| 输出内容 | JSON 文件 | `data/projects/{id}/outputs/` |
| 会议日志 | SQLite | `data/projects/{id}/logs/meetings.db` |
| 向量数据 | Chroma 嵌入式 | 内存（可配置持久化） |

---

## 9. 已知问题

1. **Outline 模型重复定义**：在 `protocols/l2.py`、`l3.py`、`expert.py`、`meeting.py` 四处分定义，应移至公共协议文件
2. **ChapterPlan 重复定义**：在 `protocols/l3.py` 和 `l4.py` 两处分定义
3. **L2 层无注册模块**：`BaseL2Architect` 有 ABC 接口但无注册实现，当前直接 import `ExpertMeetingL2`
4. **WorldBook.revert() 是空方法**：`modules/worldbook/st_style.py:99` 仅有 `pass`
5. **tags API 是空桩**：`api/settings.py` 中 `get_l3_tags()` / `get_l4_tags()` 仅有 `pass`
6. **配置中的 `hybrid_retriever` 未实现**：当前只有 `simple_vector` 一种 RAG 实现
7. **前端路由存在但未做端到端页面测试**

---

## 10. 测试覆盖

17 文件，19 个测试，全部通过：

```
test_integration.py  — 5 测试：RAG、L3/L4 初始化、WorldBook CRUD
test_l1.py           — 3 测试：生成愿景、获取/更新
test_l2.py           — 2 测试：SSE 流、大纲 CRUD
test_main.py         — 3 测试：根路由、健康检查、模块列表
test_phase2.py       — 6 测试：项目 CRUD、世界书 CRUD、提交
```

测试覆盖了所有 API 路由和核心模块，但**LLM 调用链路**的测试依赖真实 API，不在 CI 中运行。

---

## 11. 启动方式

```bash
# 后端（端口 7860）
source venv/bin/activate
./start.sh
# 或
uvicorn backend.main:app --host 0.0.0.0 --port 7860

# 前端（端口 5173）
cd frontend && npm install && npm run dev

# 配置
编辑 data/user/config.yaml 填入 api_key 和 base_url
```

---

## 12. 技术栈

| 层 | 技术 | 版本 |
|----|------|------|
| 后端框架 | FastAPI | 0.121 |
| 运行时 | Python | 3.13 |
| 向量库 | Chroma（嵌入式） | 0.6+ |
| 配置 | YAML + Pydantic | — |
| 数据库 | JSON + SQLite | — |
| SSE | FastAPI StreamingResponse | — |
| 前端框架 | Vue 3 + Vite | 5.4 |
| 路由 | vue-router | 4.x |
| Markdown | markdown-it | — |
| LLM SDK | httpx（直接 HTTP，无 SDK 依赖） | — |
