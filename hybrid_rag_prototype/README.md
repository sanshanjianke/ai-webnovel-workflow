# 笔记6混合检索方案原型

基于笔记6提出的混合检索方案，使用LangChain实现的原型项目。

## 核心概念

### 传统RAG的问题

笔记6分析了传统RAG在网文创作场景中的核心缺陷：

1. **叙事完整性破坏** - 机械切片导致序列碎片化
2. **序列逻辑断裂** - 情绪曲线被切断
3. **边界切割问题** - 关键信息切在边界处
4. **检索结果失真** - 无法支撑创作决策

### 混合检索方案

#### 1. 多维度切片

放弃机械重叠切片，采用叙事学概念驱动的多维度切分：

| 维度 | 切片单位 | 切片边界 | 适用场景 |
|------|---------|---------|---------|
| **剧情维度** | 序列/事件 | 序列开始/结束 | 剧情架构师查询完整情节 |
| **人物维度** | 角色相关段落 | 人物出场/退场 | 人物设计师查询角色行为 |
| **爽点维度** | 情绪段落 | 压抑→爆发→余韵转折点 | 网络编辑评估爽点节奏 |
| **功能维度** | 叙事功能 | 铺垫/转折/反馈边界 | 分析剧情结构 |

#### 2. 双库分离

```
向量数据库（摘要+标签+指针）  <--->  MD文本库（完整切片）
        ↓                              ↓
    快速检索                       提供完整上下文
```

#### 3. Agent检索专家

Agent作为检索专家，负责：
- 理解专家会议语境
- 判断需要检索的维度
- 调用向量数据库获取标签
- 根据指针获取完整文本
- 智能加工后返回给专家会议

## 项目结构

```
hybrid_rag_prototype/
├── config.py              # 配置文件
├── sample_data.py         # 示例数据（拍卖会打脸序列）
├── text_processor.py      # 多维度切片模块
├── dual_storage.py        # 双库存储模块
├── retrieval_agent.py     # Agent检索专家
├── main.py                # 主入口（演示流程）
├── requirements.txt       # 依赖文件
├── README.md              # 本文件
└── data/                  # 数据存储目录
    ├── vector_db/         # 向量数据库
    └── text_db/           # MD文本库
```

## 快速开始

### 1. 安装依赖

```bash
cd hybrid_rag_prototype

# 安装核心依赖（简化演示）
pip install langchain langchain-core langchain-chroma chromadb

# 安装完整依赖（需要OpenAI API）
pip install -r requirements.txt
```

### 2. 运行演示（简化版）

当前原型为简化演示版本，无需embedding和LLM：

```bash
python main.py
```

演示内容包括：
- 加载示例数据（拍卖会打脸序列）
- 多维度切片处理
- 双库存储演示
- Agent检索专家工作流
- 与L2专家会议集成

### 3. 运行完整版（需要OpenAI API）

```bash
# 设置API密钥
export OPENAI_API_KEY=your_openai_api_key

# 运行（需要修改main.py中的参数）
python main.py --with-embedding --with-llm
```

完整版特性：
- 向量数据库检索功能
- LLM智能加工
- 自动切片（待实现）

## 模块说明

### text_processor.py - 多维度切片

```python
from text_processor import SliceProcessorAgent

# 创建切片处理器
processor = SliceProcessorAgent()

# 处理切片（使用预标注数据）
slices = processor.process_with_annotation(
    raw_text=AUCTION_SEQUENCE,
    annotated_data=ANNOTATED_SLICES
)

# slices包含四个维度的切片：
# - plot: 剧情维度
# - character: 人物维度
# - emotion: 爽点维度
# - function: 功能维度
```

### dual_storage.py - 双库存储

```python
from dual_storage import DualStorageManager

# 创建存储管理器（需要embedding）
from langchain_openai import OpenAIEmbeddings
embedding = OpenAIEmbeddings()

storage = DualStorageManager(
    embedding=embedding,
    use_local_storage=True
)

# 存储切片
stats = storage.store_slices(slices)

# 检索
results = storage.retrieve(
    query="拍卖会打脸的爽点节奏",
    dimension="emotion",
    k=3
)
```

### retrieval_agent.py - Agent检索专家

```python
from retrieval_agent import L2RetrievalAgent

# 创建L2检索专家（需要LLM）
from langchain_openai import ChatOpenAI
llm = ChatOpenAI(model="gpt-4")

retrieval_agent = L2RetrievalAgent(
    storage_manager=storage,
    llm=llm
)

# 监听专家会议并检索
meeting_context = {
    "current_discussion": "评估拍卖会打脸的爽点节奏",
    "expert_role": "editor",
    "needs_retrieval": True
}

result = retrieval_agent.listen_and_retrieve(meeting_context)

# result包含：
# - 检索意图
# - 检索维度
# - 智能加工后的内容
```

## 与创作模型的集成

### L2专家会议集成

```python
# 专家会议流程
meeting_context = {
    "current_discussion": "讨论拍卖会打脸剧情",
    "expert_role": "architect",  # 剧情架构师
    "needs_retrieval": True
}

# 检索专家监听并响应
result = retrieval_agent.listen_and_retrieve(meeting_context)

# 检索专家会：
# 1. 根据专家角色判断维度（architect → plot维度）
# 2. 检索相关剧情切片
# 3. 智能加工后返回
```

### L3映射检索专家

```python
from retrieval_agent import L3MappingAgent

mapping_agent = L3MappingAgent(storage, llm)

# 检索映射规则
rules = mapping_agent.retrieve_mapping_rules("装逼打脸-压抑阶段")

# rules包含：
# {
#   "视角": "反派/路人内聚焦",
#   "节奏": "慢速扩述",
#   "话语模式": "对话+心理",
#   "理由": "通过无知者的傲慢视角，制造信息差"
# }
```

### L4技法检索专家

```python
from retrieval_agent import L4TechniqueAgent

technique_agent = L4TechniqueAgent(storage, llm)

# 检索技法示例
examples = technique_agent.retrieve_technique_examples(
    perspective="外聚焦",
    rhythm="中速等述",
    discourse_mode="动作+环境"
)

# examples包含参考文本片段
```

## 示例数据

项目使用"拍卖会打脸序列"作为示例数据，包含：

- **原始文本**：完整的拍卖会打脸剧情（约5000字）
- **标注数据**：四个维度的预标注切片
  - 剧情维度：1个完整序列
  - 人物维度：主角、反派、鉴定师戏份
  - 爽点维度：压抑、爆发、余韵三阶段
  - 功能维度：铺垫、转折、反馈三功能

## 业界方案对比

笔记6对比了业界相近的RAG增强方案：

| 方案 | 切片策略 | 索引结构 | 检索处理 | 适用场景 |
|------|---------|---------|---------|---------|
| Multi-Vector | 机械切分 | 摘要+原文分离 | 直接返回 | 通用 |
| Parent Document | 小切大返回 | 层级索引 | 直接返回 | 通用 |
| GraphRAG | 知识图谱 | 图结构 | 图遍历 | 复杂推理 |
| **本方案** | 多维度语义切分 | 双库+Agent | Agent智能加工 | 网文创作 |

## 待实现功能

1. **自动切片Agent**
   - 使用LLM自动识别序列边界
   - 自动识别情绪转折点
   - 自动识别人物出场/退场
   - 自动识别叙事功能边界

2. **完整版向量检索**
   - 集成OpenAI Embedding
   - 实现相似度检索
   - 实现标签过滤检索

3. **LLM智能加工**
   - 爽点评估：分析情绪曲线
   - 人物分析：提取行为模式
   - 剧情概述：提炼关键序列
   - 映射解析：从文本提取规则

4. **与创作流程深度绑定**
   - L1-L2-L3-L4全流程集成
   - 检索专家自动监听
   - 上下文传递机制

## 参考文档

- [笔记6.md](../笔记6.md) - 混合检索方案详细设计
- [README.md](../README.md) - AI辅助网文创作系统总览
- [LangChain Multi-Vector Retriever](https://python.langchain.com/docs/modules/data_connection/retrievers/multi_vector)
- [LangChain Parent Document Retriever](https://python.langchain.com/docs/modules/data_connection/retrievers/parent_document)
- [GraphRAG (Microsoft)](https://microsoft.github.io/graphrag/)

## 作者说明

本项目是笔记6混合检索方案的LangChain原型实现，用于验证方案的可行性。

当前版本：
- 简化演示版（无embedding，无LLM）
- 使用预标注数据
- 核心架构已实现

完整版需要：
- OpenAI API密钥
- 自动切片Agent
- LLM智能加工

---

创建时间：2026-03-29
状态：原型完成，待完善