# AI辅助网文创作系统 (AI Web Novel Creator)

> 将软件工程范式引入网文创作——分层解耦、多专家协作、数据驱动。
>
> 四层瀑布模型 (L1→L1.5→L2→L3→L4) + 三元数据支撑 (世界书 + RAG历史 + RAG技法)

---

## 项目现状

| 指标 | 数值 |
|------|------|
| 阶段 | 原型开发，L1~L4 全流程打通 |
| 后端文件 | 64 文件, ~5900 行 Python |
| 前端文件 | 18 源文件, ~8100 行 Vue 3 |
| 注册模块 | 17 个（LLM/RAG/WorldBook/L1/L3/L4/Expert×6/MeetingProtocol×4） |
| API 路由 | 73 条 |
| 单元测试 | 32/32 通过（含 L1 生成、L2 流、L3/L4 初始化、世界书、文档库） |
| 待完成 | L2 端到端集成测试、L3/L4 多技能体系、L3 向量映射库 |

---

## 快速开始

```bash
# 后端 (端口 :7860)
git clone <repo> && cd talk
source venv/bin/activate
./start.sh
# 或: uvicorn backend.main:app --host 0.0.0.0 --port 7860

# 前端 (端口 :5173)
cd frontend && npm install && npm run dev

# 配置 API
编辑 data/user/config.yaml 填入 api_key 和 base_url
```

---

## 一、创作模型：四层 + 卷纲层

### 核心设计理念

传统 AI 写作的根本问题是：用户输入模糊的创意，指望 AI 一步到位写出正文。这相当于跳过蓝图设计，直接指挥工人砌砖——没有图纸，工人（AI）只能盲目堆砌材料。

本方案借鉴软件工程的**瀑布模型**（需求分析→系统设计→编码→测试），将创作过程解耦为四个层级。核心第一性原理是**"故事"与"叙事"分离**：

- **故事**（Fabula）是客观发生的——"A 打败了 B"
- **叙事**（Discourse）是讲述方式——"从 A 视角的热血复仇 vs 从 B 视角的悲情退场"

第二层专注"讲什么"，第三层专注"怎么讲"。同一个故事，换一种叙事策略，可以产生完全不同的阅读体验。如果不分离这两层，AI 会在同一轮思考中既想结构又琢磨文笔，结果两头都做不好。

```
L1   种子层      故事愿景    "我要写一个什么样的故事"
L1.5 情节编排层   卷纲        "分成几卷，每卷走向如何"
L2   架构层      章纲        "每章的精确功能序列"
L3   叙事层      带标签草稿   "草稿嵌入叙事指令"
L4   渲染层      精修正文    "扩展打磨成终稿"
```

### L1 种子层

| 项目 | 说明 |
|------|------|
| 角色 | 创作顾问 |
| 输入 | 用户模糊创意 |
| 输出 | 《故事愿景文档》(VisionDocument) |
| 实现 | `GuidedFormGenerator`（引导表单式） |
| 技能 | `/L1-seed` |

**产出内容**：
- 核心梗/脑洞
- 阅读契约（目标读者、核心爽点、风格基调）
- 粗略大纲
- 核心设定（世界观、主角人设、金手指）
- 热点/潮流元素（可选）

### L1.5 情节编排层（部分实现，与 L2 统一编排中）

| 项目 | 说明 |
|------|------|
| 角色 | 两专家会议（资深作者 + 读者代表） |
| 输入 | L1 愿景文档 |
| 输出 | 卷纲 .md（每章 1-3 句方向性描述） |
| 实现 | `MeetingEngine` 统一编排 + `editor_reader` 协议 |
| 粒度 | 卷级方向决策，非功能序列 |

> **架构演进**（笔记16-17）：L1.5 和 L2 已合并为统一的**编排层**，专家（资深作者、读者代表、剧情架构师、人物设计师、网络编辑、章节拆分师）可在画布上自由拖拽组合。旧的 L1.5/L2 独立 API 保留为向后兼容，底层均委托给 `MeetingEngine`。预设模板（快速审核/卷纲规划/章纲设计）涵盖了原 L1.5 和 L2 的所有使用场景。

**为什么需要 L1.5**：L1 的粗略大纲通常是几百字的叙事散文（"主角加入宗门后慢慢变强，最后在大比夺冠"），而 L2 需要结构化功能序列。从散文到序列的跳跃太大。软件开发不会从需求文档直接跳到函数设计——中间必定有系统设计层处理模块划分。L1.5 就是创作中的系统设计层：决定分几卷、每卷主线、章节分配。

**专家分工**：
- 资深作者（创作方向把控）：提出分卷方案、判断热点方向、毒点预警。例如"卷一要安排强敌，没对手像流水账"、"30 章后必须开新地图，不然读者疲劳"
- 读者代表（体验审核）：模拟读者情绪、检测疲劳点、质疑合理性。只负责提"哪里可能有问题"，不提出解决方案

**L1.5 和 L2 的分工**：L1.5 决定"第 31-35 章写秘境探索"，L2 决定"具体功能链怎么排来实现这个探索"。L1.5 讨论方向对不对，L2 执行落地拆解。

### L2 架构层

| 项目 | 说明 |
|------|------|
| 角色 | 三专家会议（用户审稿），也可选两专家/五专家自由组合 |
| 输入 | L1 愿景 + L1.5 卷纲 + 世界书 + RAG |
| 输出 | 《精修故事大纲》(Outline)，含多维功能标注 |
| 实现 | `MeetingEngine`（SSE 流式，统一编排引擎）+ 画布拖拽 |
| 技能 | `/L2-architect` `/L2-editor` `/L2-character` |

**三专家**：

| 专家 | 职责 | 核心概念 |
|------|------|---------|
| **剧情架构师** | 构建故事骨架，逻辑把关 | 功能→序列→情节拆解，因果闭环 |
| **网络编辑** | 市场效果把控，爽点节奏 | 黄金三章、压抑-释放、毒点规避 |
| **人物设计师** | 人物行为合理性，人设一致 | 行动元分配、扁形/圆形人物、OOC 检测 |

**为什么需要三位异质化专家而非单一 Agent**：

单一 Agent 是一个"全科医生"——什么都懂一点，什么都不精。网文创作本质包含三类能力：
- 结构逻辑（架构师）：因果闭环、序列完整性——需要理性推演
- 市场嗅觉（编辑）：爽点密度、读者心理——需要商业直觉
- 角色共情（设计师）：人设一致性、行为动机——需要代入感

在一个 prompt 里同时要求这三种能力时，它们会互相干扰。追求逻辑时压制爽感（"这样更合理但不好看"），追求爽感时人物崩坏（"为了打脸强行降智配角"）。三位异质化专家各挂专属知识库（RAG），各自从专业角度发言，用户担任主编拥有最终决策权——这与真实出版业的选题会模式一致。

**三种驱动模式**：

| 模式 | 顺序 | 适用场景 |
|------|------|---------|
| 人物驱动流 | 人物 → 剧情 → 编辑 | 文青文、种田文、成长向 |
| 剧情驱动流 | 剧情 → 人物 → 编辑 | 无限流、系统文、副本向 |
| 市场驱动流 | 编辑 → 剧情 ↔ 人物 | 跟风热点、商业定制 |

**驱动模式的原理**：不同类型的网文有不同的约束优先级。人物驱动流中，角色性格是硬约束——先确定人物会怎么反应，再让情节围绕人物展开。市场驱动流中，爽点是硬约束——剧情和人物都要为爽点服务。选择正确的驱动模式决定了专家发言顺序和各自权重。

**多维功能标注**（笔记9核心创新）：

| 维度 | 标注内容 | 负责专家 |
|------|---------|---------|
| 内/剧情轴 | 推进/转折/铺垫/阻碍/回收/承接 | 剧情架构师 |
| 内/人物轴 | 揭示特性/触发成长/确立关系/制造矛盾/展示能力/施加压力 | 人物设计师 |
| 内/世界轴 | 展示设定/营造氛围/建立规则/拓展地图/强化画面感 | 架构师+人物 |
| 外/读者五感 | 期待感/满足感/代入感/爽感/惊喜感（标↑↓强度） | 网络编辑 |

**标注的实际价值**：传统标注只写一个"功能类型"（如"获得功能"），信息量极低。多维标注给每个叙事单位打上了完整的"效果标签"——如果某个功能只在剧情轴有作用，其他轴空白，说明这是"功能性但不好看"的节点，编辑该介入。如果读者效果在多个连续功能中缺失，说明存在情绪断层。多维标注直接降低了 L3 的工作难度：L3 不再需要自己推断"这段产生了什么读者效果"——这是 L3 最不可靠的一步，现在 L2 直接标注好了。

**协作模式**：`semi_auto`（半自动，专家发言后暂停）/ `full_auto`（全自动）/ `manual`（用户指定发言人）

### L3 叙事层

| 项目 | 说明 |
|------|------|
| 角色 | 翻译器（映射编译） |
| 输入 | L2 精修大纲 |
| 输出 | 带标签草稿（正文嵌入 `<视角>` `<节奏>` `<情绪>` 等叙事标签） |
| 实现 | `MappingCompiler` → 计划升级为 `TaggedDraftGenerator` |
| 技能 | `/L3-narrative` |

**L3 是整个系统的核心创新——效果到技术的确定性映射**。

**理论背景**：网文理论和叙事学是两套不同的语言体系。网文理论属于"效果学"——"欲扬先抑"、"装逼打脸"这些概念描述的是读者心理反应，语言是模糊的、经验主义的。叙事学属于"结构学"——"外聚焦视角"、"慢速扩述"、"自由间接引语"这些概念描述的是文本组织方式，语言是精确的、结构主义的。

L3 的使命就是**把效果学指令编译为结构学指令**。这不是让 AI 临场推理哪个视角适合打脸——每次推理结果不同，质量不稳定。而是建立一套**确定性的映射规则库**：

**核心映射**：

| 效果目标 | 视角选择 | 节奏控制 | 话语模式 | 原理 |
|---------|---------|---------|---------|------|
| 压抑（铺垫/期待） | 反派/路人内聚焦 | 慢速扩述（细节展开） | 大量对话+心理描写 | 信息差制造读者的优越感 |
| 爆发（打脸/反转） | 外聚焦（客观镜头） | 中速等述 | 短句动词密集 | 零度写作提升逼格，不解释 |
| 余韵（震惊/满足） | 自由间接引语 | 快速概述 | 震惊反应+留白 | 直接展示心理崩溃，不议论 |

**为什么对外聚焦写打脸**：内聚焦（进入角色心理）会稀释打脸的爽感——"他觉得很愤怒"不如"他握紧了拳头"有力。外聚焦只写可见的动作和对话，不写心理活动，读者需要自己脑补角色的内心活动，这种"脑补参与感"才是网文爽感的来源。这是叙事学原理在网文创作中的具体应用，不是凭空猜测。

**多技能体系**（笔记13设计）：初稿生成 / 迭代修正 / 换方向重写 / 保守写作 / 加速模式

### L4 渲染层

| 项目 | 说明 |
|------|------|
| 角色 | 执行者 |
| 输入 | L3 带标签草稿 |
| 输出 | 精修正文 |
| 实现 | `ConstrainedRenderer`（SSE 流式） |
| 技能 | `/L4-render` |

L4 不是自由创作，而是**带约束的文本扩展**。执行约束：视角（只写所见，不写所想）、节奏（字数控制）、话语模式（句式结构）。L3 的标签在 L4 阶段通过正则预处理转换为完整提示词，指导生成。

**多技能体系**：初稿扩展 / 文风调校 / 删改压缩 / 描写增强 / 对话打磨 / 保守修复 / 终稿润色

### 不是单行道，而是迭代闭环

四层不是不可回退的。L3 发现映射困难可打回 L2 重审，L2 发现方向问题可打回 L1.5 重排。每一层都有人的决策权——AI 提方案，人做决定。这和全自动生成有本质区别：系统是"副驾驶"不是"驾驶员"。

---

## 二、数据支撑：三元协同

AI 创作长篇小说的记忆问题，不能靠全部塞进上下文窗口解决（成本 + 注意力衰减）。设计了三种不同性质的记忆系统：

```
        世界书 (World Book)           RAG-历史回顾          RAG-技法参考
        当前状态管理                  过往记忆              写作素材
        "主角现在是金丹期"            "老周第45章说过..."     "打脸场景怎么写"
```

三者分工明确：世界书保证**不犯错**（当前状态确定性管理），RAG-历史回顾保证**不遗忘**（精准提取相关前文），RAG-技法参考保证**写得好**（参考范例和映射规则）。

### 世界书 (World Book)

灵感来自 SillyTavern 的触发词上下文注入系统，但扩展为完整的**跨层持久化状态层**。

**四层结构**：

| 层 | 内容 | 特性 |
|----|------|------|
| 核心层 | 世界观规则、力量体系、核心设定、阅读契约 | 永久条目，不随剧情变化 |
| 活跃层 | 人物状态、活跃伏笔、当前道具、势力状态 | 随剧情实时更新，权重机制 |
| 归档层 | 已完成序列摘要、已回收伏笔、退场人物、版本历史 | 压缩为一句话概括 |
| 索引层 | 条目-章节映射、关系图、触发词索引 | 元数据，用于检索 |

**关键机制**：
- **版本链非覆写**：主角修为不写"现在是元婴期"，而是 `[1-30:筑基]→[31-80:金丹]→[81-今:元婴]`。保留完整版本历史比只写当前状态多不了多少 token，但极端关键——AI 能借由版本链理解角色成长弧光
- **重要性衰减**：权重 +1 被引用，-1 连续 10 章未引用，归零归档。防止世界书无限制膨胀
- **自动压缩**：已完成序列从详细描述压缩为摘要

**世界书管理员 Agent**：作为元层后处理，不参与创作讨论。每序列完成后读取产出 → 提取变化 → 更新条目 → 冲突检测 → 产出变更摘要。角色类似档案管理员，而非第四位专家。

### RAG 系统（双重职能）

**理论上区分 RAG 的两种使用场景**：

| 职能 | RAG-历史回顾 | RAG-技法参考 |
|------|-------------|-------------|
| 内容 | 已生成章节的摘要/片段 | 爽点公式、映射规则、参考范例 |
| 触发时机 | 创作过程中持续查询 | L3/L4 执行时定向查询 |
| 数据来源 | 当前作品（动态增长） | 静态知识库 |
| 解决的问题 | "之前发生了什么" | "怎么写更好" |
| 更新频率 | 每完成序列即索引 | 很少更新 |

**混合检索方案**（笔记6设计、笔记7原型验证）：

单纯 RAG 的问题：
- **叙事完整性破坏**：机械切片破坏序列逻辑——"打脸"序列被切成碎片，检索返回的片段无法支撑完整决策
- **检索噪音**：向量相似度不等于语义相关，中文专有名词检索效果尤其差

改进方案：
- **多维度语义切片**：同一文本按 plot(序列)/character(人物)/emotion(情绪)/function(功能) 四种维度切分，不同专家检索不同维度
- **文档增强**：每个序列生成 5 视角改写（情节概述/爽点分析/人物关系/情感弧线/读者问题），增加检索命中入口
- **混合得分**：`vector_score × 0.6 + keyword_score × 0.4`
- **双库分离**：向量库存摘要+标签（快速检索），MD 文本库存完整切片（完整上下文）

原型用 300 章小说验证，总耗时 ~25 分钟（7 步 pipeline），检索准确率显著优于纯向量方案。

### 数据构建流程（三道过滤，待实施）

```
数据海 (400G-100G) → 第一道过滤(质量筛选) → 第二道过滤(标注+摘取) → 第三道过滤(检验) → 向量数据库
```

每道过滤由专门的 Agent 团队执行：质量评估师 + 标签标注师 → 序列识别师 + 叙事标注师 + 片段提取师 → 一致性检验师 + 完整性检验师 + 质量检验师。最终产出 L3 映射关系库和 L4 微观技法库两个向量数据库。

### RAG 困境与微调路线

**RAG 的四个根本问题**：上下文挤占（检索片段占用窗口空间）、注意力分散（在参考文本与当前任务间切换）、检索噪音（不相关片段干扰）、知识外挂（无法内化为写作直觉——每次都要查）。

**微调成本估算**（AutoDL 租用价格）：

| 方案 | 成本 | 时间 | 说明 |
|------|------|------|------|
| **RAG（当前）** | 低 | — | 向量数据库 + 混合检索 |
| **QLoRA 微调 7B** | ~100元 | ~10小时 | 注入风格/语感，个人可承担 |
| **LoRA 微调 7B** | ~500-1000元 | ~50小时 | 更深调整 |
| **增量预训练 (10B Token)** | ~4000-10000元 | ~100小时 | 注入领域知识 |
| **完整训练（四阶段）** | ~7-15万元 | ~500-1000小时 | 领域特化模型，需专业团队 |

**策略**：短期以 RAG 为主（即时可用），中期 QLoRA 微调注入风格和语感，长期混合使用——微调负责"直觉"（爽点判断力、语感），RAG 负责"知识"（具体概念、范例查询）。

---

## 三、技术栈与架构

| 层 | 技术 |
|----|------|
| 后端框架 | Python 3.13, FastAPI 0.121 |
| 前端框架 | Vue 3 (Composition API), Vite 5.4, vue-router 4.x |
| 实时通信 | SSE (Server-Sent Events), 浏览器原生 EventSource |
| 向量数据库 | Chroma（嵌入式） |
| 数据存储 | JSON (核心数据) + SQLite (日志) |
| 配置 | YAML + Pydantic |
| LLM | OpenAI 兼容接口, GLM-5, `BaseLLMProvider` 抽象 |
| Markdown | markdown-it（流式渲染缓冲不完整块） |

### 模块化插件体系

所有功能组件定义 ABC 抽象接口，实现通过 `@register_module` 装饰器自动发现：

```
backend/modules/
├── llm/               OpenAICompat, MockLLM
├── rag/               SimpleVectorRetriever (Chroma)
├── worldbook/         STStyleWorldBook (SillyTavern 风格)
├── l1/                GuidedFormGenerator
├── experts/           专家池 (6 位: SeniorAuthor, Reader, PlotArchitect, CharacterDesigner, WebEditor, ChapterSplitter)
├── orchestration/     MeetingEngine 统一编排引擎
├── l3/                MappingCompiler
└── l4/                ConstrainedRenderer
```

### 17 个已注册模块

| 类别 | Key | 类 | 文件 |
|------|-----|-----|------|
| llm | `mock_llm` | MockLLM | modules/llm/mock.py |
| llm | `open_ai_compat` | OpenAICompat | modules/llm/openai_compat.py |
| rag | `simple_vector` | SimpleVectorRetriever | modules/rag/simple_vector.py |
| worldbook | `st_style` | STStyleWorldBook | modules/worldbook/st_style.py |
| l1 | `guided_form` | GuidedFormGenerator | modules/l1/guided_form.py |
| l3 | `mapping_compiler` | MappingCompiler | modules/l3/mapping_compiler.py |
| l4 | `constrained` | ConstrainedRenderer | modules/l4/constrained.py |
| expert | `plot_architect_v1` | PlotArchitectV1 | modules/experts/__init__.py |
| expert | `character_designer_v1` | CharacterDesignerV1 | modules/experts/__init__.py |
| expert | `web_editor_v1` | WebEditorV1 | modules/experts/__init__.py |
| expert | `senior_author_v1` | SeniorAuthorV1 | modules/experts/__init__.py |
| expert | `reader_representative_v1` | ReaderRepresentativeV1 | modules/experts/__init__.py |
| expert | `chapter_splitter_v1` | ChapterSplitterV1 | modules/experts/__init__.py |
| meeting_protocol | `plot_driven` | PlotDriven | meeting_protocols/plot_driven.py |
| meeting_protocol | `character_driven` | CharacterDriven | meeting_protocols/character_driven.py |
| meeting_protocol | `market_driven` | MarketDriven | meeting_protocols/market_driven.py |
| meeting_protocol | `editor_reader_driven` | EditorReaderDriven | meeting_protocols/editor_reader.py |

---

## 四、API 路由总览（73 条）

> 旧 L1.5/L2 端点保留向后兼容，底层委托给统一 `/meeting` 引擎。

| 类别 | 路径 | 方法 | 说明 |
|------|------|------|------|
| 系统 | `/` `/health` | GET | 根路由 / 健康检查 |
| 系统 | `/api/modules` | GET | 列出所有注册模块 |
| 系统 | `/api/config` | GET/PUT | 获取/更新配置 |
| 系统 | `/api/tags/l3` `/api/tags/l4` | GET | 标签库（空桩） |
| 项目管理 | `/api/projects/` | GET/POST | 列表/创建项目 |
| 项目管理 | `/api/projects/{id}` | GET/DELETE | 获取/删除项目 |
| 项目管理 | `/api/projects/{id}/config` | PUT | 更新项目配置 |
| 项目管理 | `/api/projects/{id}/logs` | GET | 会议日志 |
| L1 | `/api/projects/{id}/l1/chat` | POST | SSE 对话流 |
| L1 | `/api/projects/{id}/l1/generate` | POST | 生成愿景 |
| L1 | `/api/projects/{id}/l1/vision` | GET/POST/PUT | 愿景 CRUD |
| L1 | `/api/projects/{id}/l1/draft` | GET/POST | 草稿自动保存 |
| L1 | `/api/projects/{id}/l1/chat-history` | GET/POST | 聊天历史 |
| L1.5(旧) | `/api/projects/{id}/l1_5/stream` | GET | SSE 两专家会议流 |
| L1.5(旧) | `/api/projects/{id}/l1_5/feedback` | POST | 人工反馈 |
| L1.5(旧) | `/api/projects/{id}/l1_5/output` | GET/PUT | 卷纲管理 |
| L2(旧) | `/api/projects/{id}/l2/stream` | GET | SSE 三专家会议流 |
| L2(旧) | `/api/projects/{id}/l2/feedback` | POST | 人工反馈 |
| L2(旧) | `/api/projects/{id}/l2/outline` | GET/PUT | 大纲管理 |
| 编排(新) | `/api/presets` | GET | 列出预设模板 |
| 编排(新) | `/api/experts` | GET/POST | 专家列表/创建自定义 |
| 编排(新) | `/api/projects/{id}/meeting/stream` | GET | 统一 SSE 会议流 |
| 编排(新) | `/api/projects/{id}/meeting/feedback` | POST | 会议反馈 |
| 编排(新) | `/api/projects/{id}/meeting/output` | GET/PUT | 会议产出管理 |
| 编排(新) | `/api/projects/{id}/meeting/design` | GET/PUT | 画布设计持久化 |
| L3 | `/api/projects/{id}/l3/generate` | POST | 生成章纲 |
| L3 | `/api/projects/{id}/l3/plan` | GET/PUT | 章纲管理 |
| L4 | `/api/projects/{id}/l4/stream` | GET | SSE 渲染流 |
| L4 | `/api/projects/{id}/l4/text` | GET | 获取正文 |
| 世界书 | `/api/projects/{id}/worldbook` | GET/POST | 列表/创建条目 |
| 世界书 | `/api/projects/{id}/worldbook/entry/{eid}` | GET/PUT/DELETE | 条目 CRUD |
| 世界书 | `/api/projects/{id}/worldbook/commit` | POST | 提交版本 |
| 世界书 | `/api/projects/{id}/worldbook/commits` | GET | 版本历史 |
| 世界书 | `/api/projects/{id}/worldbook/process-sequence` | POST | AI 自动处理序列 |
| 世界书 | `/api/projects/{id}/worldbook/auto-commit` | POST | 自动提交 |
| RAG | `/api/projects/{id}/rag/search` | POST | 语义搜索 |
| RAG | `/api/projects/{id}/rag/index` | POST | 索引文档 |
| RAG | `/api/projects/{id}/rag/stats` | GET | 统计信息 |
| 文档库 | `/api/projects/{id}/library` | GET/POST | 列表/创建文档 |
| 文档库 | `/api/projects/{id}/library/{uid}` | GET/PUT/DELETE | 文档 CRUD |
| 文档库 | `/api/projects/{id}/library/{uid}/content` | PUT | 更新内容 |
| 文档库 | `/api/projects/{id}/library/{uid}/archive` | PUT | 归档/取消 |
| 文档库 | `/api/projects/{id}/library/{uid}/export` | GET | 导出文档 |
| 文档库 | `/api/projects/{id}/library/active/{layer}` | GET/PUT | 活跃文档管理 |
| 文档库 | `/api/projects/{id}/library/import` | POST | 导入文件 |
| 文档库 | `/api/projects/{id}/library/directories` | POST/DELETE | 目录管理 |

---

## 五、目录结构

```
talk/
├── backend/                          # Python/FastAPI 后端
│   ├── main.py                       # 入口，路由注册，lifespan
│   ├── core/
│   │   ├── config.py                 # YAML 配置加载 (pydantic)
│   │   ├── registry.py              # 插件自动发现 + 注册表
│   │   └── protocols/               # 9 个 ABC 接口
│   │       ├── llm.py / rag.py / worldbook.py   # 数据层协议
│   │       ├── l1.py / l2.py / l3.py / l4.py    # 四层协议
│   │       └── expert.py / meeting.py           # 专家/会议协议
│   ├── modules/                      # 可替换实现
│   │   ├── llm/ rag/ worldbook/     # 数据层模块
│   │   ├── l1/ l3/ l4/              # 创作层模块
│   │   ├── experts/                  # 专家池 (6 位统一实现)
│   │   └── orchestration/            # MeetingEngine 统一编排引擎
│   ├── meeting_protocols/            # 4 种会议协议（自动发现）
│   ├── api/                          # 12 个路由文件 (73 条路由)
│   ├── services/                     # 独立服务
│   │   ├── project_manager.py        # 项目管理 (JSON)
│   │   ├── library_manager.py        # 文档库 (溯源链、目录、归档)
│   │   ├── worldbook_manager.py      # 世界书自动管理 Agent
│   │   ├── meeting_logger.py         # 会议日志 (SQLite)
│   │   └── generation_manager.py     # 生成任务启停控制
│   └── tests/                        # pytest 测试 (6 文件, 32 测试)
│
├── frontend/                         # Vue 3 前端
│   └── src/
│       ├── App.vue                   # 根组件 + 导航 + 文档侧边栏
│       ├── main.js                   # 入口 + vue-router 路由
│       ├── lib/sse.js                # SSE 流包装器
│       ├── pages/                    # 10 个页面
│       │   ├── Dashboard.vue         # 仪表盘
│       │   ├── L1Seed.vue            # L1 种子（对话 + 表单 + 愿景）
│       │   ├── Orchestration.vue     # 编排画布 + 会议
│       │   ├── L15Meeting.vue        # L1.5 两专家会议（未注册路由）
│       │   ├── L2Meeting.vue         # L2 三专家会议（未注册路由）
│       │   ├── L3Narrative.vue       # L3 叙事层
│       │   ├── L4Render.vue          # L4 渲染层
│       │   ├── WorldBook.vue         # 世界书管理
│       │   ├── Library.vue          # 文档库详情
│       │   └── Settings.vue          # 系统设置
│       └── components/
│           ├── OrchestrationCanvas.vue  # Vue Flow 编排画布
│           ├── ExpertNode.vue           # 专家节点
│           ├── GroupNode.vue            # 容器节点
│           ├── LoopNode.vue             # 循环节点
│           └── library/
│               └── DocumentSidebar.vue  # 文档库侧边栏
│
├── data/                             # 运行时数据
│   ├── user/config.yaml              # 全局配置（含 API 密钥）
│   ├── user/custom_experts/          # 用户自定义专家
│   └── projects/{id}/               # 项目数据
│       ├── project.json              # 项目配置
│       ├── worldbook.json            # 世界书条目
│       ├── library/                  # 文档库（manifest + files）
│       ├── outputs/                  # 活跃产出指针
│       └── logs/meeting.db           # 会议日志 (SQLite)
│
├── .claude/skills/                   # L1-L4 技能定义
│   ├── L1-seed/SKILL.md
│   ├── L2-architect/SKILL.md
│   ├── L2-editor/SKILL.md
│   ├── L2-character/SKILL.md
│   ├── L3-narrative/SKILL.md
│   └── L4-render/SKILL.md
│
├── hybrid_rag_prototype/             # 笔记7 RAG 原型（小说→大纲→多维度切片→向量库）
├── papers/                           # 参考论文
├── paper/                            # 论文写作
├── start.sh / start.bat              # 一键启动
├── AGENTS.md / CLAUDE.md             # AI 助手指南
├── 系统设计文档.md                     # 架构、协议、API 详细设计
├── 开发计划.md                        # 11 阶段开发计划
├── PROJECT_STATUS.md                  # 项目现状文档
├── 笔记1-17.md                       # 17 篇理论演进笔记
├── L1-L4.md + L2_*.md                # 各层详细设计文档
├── 论文深度分析.md                     # 7篇 arXiv 论文对比分析
├── 相关工作.md / RELATED_WORK.md      # 学界相关工作
└── README.md                         # 本文件
```

---

## 六、使用技能系统

在 Claude Code 或 OpenCode 中按顺序调用：

```bash
# Step 1: 种子层
/L1-seed
# 输入创意 → 获得《故事愿景文档》

# Step 2: 架构层（按需调用）
/L2-architect    # 剧情架构师：拆解序列
/L2-editor       # 网络编辑：评估爽点
/L2-character    # 人物设计师：审核人设
# 三专家讨论 → 获得《精修故事大纲》

# Step 3: 叙事层
/L3-narrative
# 大纲 → 《章纲/细纲》

# Step 4: 渲染层
/L4-render
# 细纲 → 正文
```

---

## 七、理论演进（17 篇笔记）

| 笔记 | 内容 | 关键贡献 |
|------|------|---------|
| 笔记1 | 四层模型、双/三数据库理论 | 理论奠基 |
| 笔记2 | 叙事学关键词、问题清单 | 理论分层（L2 vs L3概念划分） |
| 笔记3 | 序列功能性思考 | 发现功能有归类可能 |
| 笔记4 | L2 三专家会议详细设计 | 三种驱动流（人物/剧情/市场） |
| 笔记5 | 向量数据库方案、RAG困境、微调成本 | 数据构建三道过滤；微调成本估算 |
| 笔记6 | 混合检索方案：Agent+RAG、多维度切片 | 双库分离、检索专家、文档增强 |
| 笔记7 | 混合检索方案实现（hybrid_rag_prototype） | 7步pipeline，25分钟300章，测试通过 |
| 笔记8 | 世界书：持久化状态管理与RAG协同 | 四层结构、管理员Agent、三元协同 |
| 笔记9 | 功能的多维拆解模型 | 5轴标注矩阵，L2输出格式升级 |
| 笔记10 | 软件框架设计：模块化B/S架构 | 插件协议、注册表、标签化指令系统 |
| 笔记11 | 文档库：版本管理与组织 | 溯源链、草稿机制、双轨存储 |
| 笔记12 | L1.5：情节编排层 | 卷纲层、两专家会议（资深作者+读者） |
| 笔记13 | L3/L4：带标签草稿与多技能体系 | 标签嵌入草稿、5+7技能切换 |
| 笔记14 | 工作流画布：两级可编排的模块系统 | 芯片+PCB类比、全自动/手动模式 |
| 笔记15 | 消息系统：任务堆积与提醒 | 三级消息、堆积检测、Web Push |
| 笔记16 | L1.5/L2 合并：画布编排下的统一专家会议 | 统一编排层、专家池复用、节点画布、预设模板 |
| 笔记17 | 编排画布深化：从顺序发言到动态编排 | @提及点名、世界书/RAG画布节点、容器框、灵活退出 |

---

## 八、与学界的对比优势

| 维度 | 现有研究 | 本方案 |
|------|----------|--------|
| 目标领域 | 通用故事生成 | **网文（商业文学）** |
| 架构 | 单层或双层 | **四层瀑布模型 + L1.5** |
| 协作模式 | 多Agent生成选项（同质化） | **异质化专家会议 + 主编决策** |
| 理论基础 | 通用叙事学 | **叙事学 + 网文商业理论（双库映射）** |
| 数据支撑 | 单一RAG | **三元协同（世界书 + 历史RAG + 技法RAG）** |
| 工程化 | 较弱 | **软件工程思维（分层解耦、插件体系、SSE流式）** |

参考论文：NarrativeLoom (CHI 2026), StorySage (Stanford), ConStory-Bench (Microsoft), StoryScope (Google DeepMind), Spoiler Alert (McGill) 等 7 篇。

与 NarrativeLoom 的关键差异：他们的 AI 人物是"同质化"的（10 个通用人物各自生成选项，用户选择），本质是创意多样性工具。我们的三位专家是"异质化"的——架构师管逻辑、编辑管市场、设计师管人物，各自挂载不同知识库——本质是专业化协作。

---

## 九、已知问题与待办

### 已知问题
1. Outline/ChapterPlan 模型在多个 protocol 文件中重复定义，需统一
2. L2 层有 `BaseL2Architect` ABC 接口但无注册实现（已废弃，功能迁移至 `MeetingEngine`）
3. `WorldBook.revert()` 是空方法
4. tags API 是空桩 (`get_l3_tags()` / `get_l4_tags()`)
5. 配置中的 `hybrid_retriever` 未实现（仅有 `simple_vector`）
6. `modules/l2/` 目录仅剩空 `__init__.py` 和过期 `.pyc` 缓存（旧架构残留）

### 短期规划
- [ ] L2 专家会议端到端集成测试
- [ ] L3/L4 重构：带标签草稿 + 多技能体系（笔记13）
- [ ] 混合检索器 (`hybrid_retriever`) 实现
- [ ] WorldBook.revert() 方法填充
- [ ] L3 映射关系库（向量数据库构建，笔记5）
- [ ] 消息通知系统（笔记15）

### 中长期规划
- [ ] 用户研究（N=30-50）
- [ ] 网文专属评估指标体系（爽点密度、节奏评分、张力度量）
- [ ] 领域模型微调（QLoRA/LoRA）
- [ ] arXiv 论文投稿

---

## 十、核心文档索引

| 文档 | 内容 | 读我 |
|------|------|------|
| [PROJECT_STATUS.md](PROJECT_STATUS.md) | 最新项目实现状态 | 想知道当前能跑什么 |
| [系统设计文档.md](系统设计文档.md) | 架构、协议、API 详细设计 | 理解系统结构 |
| [开发计划.md](开发计划.md) | 11 阶段开发路线图 | 了解开发历程 |
| [笔记1.md](笔记1.md) | 四层模型理论基础 | 理解"为什么这么设计" |
| [笔记4.md](笔记4.md) | L2 三专家会议详细设计 | 理解 L2 核心 |
| [笔记9.md](笔记9.md) | 多维功能标注矩阵 | 理解 L2→L3 衔接 |
| [笔记8.md](笔记8.md) | 世界书 + 三元协同 | 理解数据支撑 |
| [笔记12.md](笔记12.md) | L1.5 情节编排层 | 理解卷纲层设计 |
| [笔记13.md](笔记13.md) | L3/L4 多技能体系 | 理解新版 L3/L4 |
| [笔记14.md](笔记14.md) | 工作流画布 | 理解前端长远愿景 |
| [笔记16.md](笔记16.md) | L1.5/L2 合并：统一编排层 | 理解最新的架构演进方向 |
| [笔记17.md](笔记17.md) | 编排画布深化 | 理解动态编排、@提及、世界书节点 |
| [论文深度分析.md](论文深度分析.md) | 7篇论文分析 | 了解学术定位 |
| [AGENTS.md](AGENTS.md) | 编码规范和开发指南 | 开发和贡献 |

---

版本：v3.3  
更新：2026-05-02  
涵盖：笔记1-17 + L1.5/L2 统一编排 + 文档库 + 编排画布 + PROJECT_STATUS + 系统设计文档 + 开发计划
