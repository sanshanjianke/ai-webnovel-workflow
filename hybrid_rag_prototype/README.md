# 混合检索方案 - 完整实现

基于笔记6提出的混合检索方案，已实现完整的小说到知识库流程。

## 快速开始

### 完整流程（一键运行）

```bash
cd /home/ssjk/talk/hybrid_rag_prototype

./venv/bin/python steps/run_all.py \
    --novel /path/to/novel.txt \
    --name "小说名" \
    --output output
```

### 分步执行

```bash
# Step 1: 章节切片
./venv/bin/python steps/step1_split_chapters.py \
    /path/to/novel.txt --output output/01_chapters --max 300

# Step 2: 序列分组
./venv/bin/python steps/step2_create_sequences.py \
    --input output/01_chapters --output output/02_sequences --size 7

# Step 3: LLM生成草稿（并行，约17分钟）
./venv/bin/python steps/step3_generate_drafts.py \
    --input output/02_sequences --output output/03_drafts --workers 10

# Step 4: 切分成块
./venv/bin/python steps/step4_merge_blocks.py \
    --input output/03_drafts --output output/04_blocks --size 50

# Step 5: LLM生成L2大纲（串行，约7分钟）
./venv/bin/python steps/step5_generate_outline.py \
    --input output/04_blocks --output output/05_outline --name "小说名"

# Step 6: 文档增强+切片（约7分钟）
./venv/bin/python steps/step6_enrich_slices.py \
    --input output/05_outline --output output/06_slices

# Step 7: 向量存储（约1分钟）
./venv/bin/python steps/step7_vector_store.py \
    --input output/06_slices --output output/07_vector_db
```

## 核心设计

### 1. 多维度切片

同一内容按4个维度切分：

| 维度 | 切片单位 | 边界 | 适用场景 |
|------|---------|------|---------|
| plot | 序列 | 序列开始/结束 | 剧情架构师 |
| character | 人物段落 | 人物出场/退场 | 人物设计师 |
| emotion | 情绪段落 | 情绪转折点 | 网络编辑 |
| function | 叙事功能 | 功能边界 | 结构分析 |

### 2. 文档增强（核心创新）

每个序列生成5个视角的改写：

```
原始: "李白制服郑屠"

增强后:
├─ 情节概述: 李白凭借大魔头气场震慑发狂患者郑屠
├─ 爽点分析: 反差装逼与气场压制的完美结合
├─ 人物关系: 李白与郑屠是压制与被压制关系
├─ 情感弧线: 迷茫→紧张→惊讶→爽快
└─ 读者问题: ["郑屠被李白的气场震慑产生幻觉？", ...]
```

### 3. 混合检索

**问题**：向量检索对中文专有名词效果差

**方案**：向量搜索 + 关键词过滤

```python
# 混合得分计算
vector_score = 1 - min(distance / 1.5, 1)
keyword_score = matched_keywords / total_keywords
hybrid_score = vector_score * 0.6 + keyword_score * 0.4
```

### 4. 上下文记忆

Step5串行处理，保持上下文：

```
Block 1 → 提取 → 传递摘要
    ↓
Block 2 → 继续提取 → 传递摘要
    ↓
Block 3 → ...
```

## 检索使用

```python
from steps.retriever import create_retriever
from pathlib import Path

# 创建检索器
retriever = create_retriever(
    vector_db_path=Path('output/07_vector_db'),
    embedding_type='dashscope',
    api_key='your-api-key'
)

# 语义搜索
results = retriever.search('李白怎么制服郑屠', k=3)
for r in results:
    print(f"{r.name} (得分: {r.score:.3f})")

# 标签搜索
results = retriever.search_by_tags({'appeal_types': '打脸'}, k=5)

# 指定维度
results = retriever.search('穿越归来', dimension='plot', k=3)
```

## 测试结果

### 数据统计（300章都市剑说）

| 步骤 | 输入 | 输出 | 耗时 |
|------|------|------|------|
| Step 1 | 小说文件 | 300章 | <1秒 |
| Step 2 | 300章 | 43序列 | <1秒 |
| Step 3 | 43序列 | 43草稿(101KB) | 17分钟 |
| Step 4 | 43草稿 | 6块(每块50KB) | <1秒 |
| Step 5 | 6块 | 40序列+91人物 | 7分钟 |
| Step 6 | L2大纲 | 258切片+文档增强 | 7分钟 |
| Step 7 | 切片 | 向量库3.5MB | 1分钟 |

**总计**: ~25分钟

### 检索效果

| 查询 | 命中序列 | 得分 |
|------|---------|------|
| "郑屠" | 魔头苏醒与职场首秀 | 0.614 |
| "武疯子被枪毙" | 高速惊魂与田野对决 | 0.253 |
| "戏弄道士" | 直播斗法与当众处刑 | 0.291 |
| "穿越归来" | 魔头苏醒与职场首秀 | 0.294 |

## API配置

### LLM (GLM-5)

```python
OPENAI_API_KEY = "sk-xxx"
OPENAI_BASE_URL = "https://coding.dashscope.aliyuncs.com/v1"
LLM_MODEL = "glm-5"
```

### Embedding (text-embedding-v3)

```python
EMBEDDING_API_KEY = "sk-xxx"
EMBEDDING_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
EMBEDDING_MODEL = "text-embedding-v3"  # 1024维
```

## 目录结构

```
hybrid_rag_prototype/
├── config.py              # 配置
├── utils.py               # 工具函数
├── steps/
│   ├── step1_split_chapters.py      # 章节切片
│   ├── step2_create_sequences.py    # 序列分组
│   ├── step3_generate_drafts.py     # LLM生成草稿
│   ├── step4_merge_blocks.py        # 切分成块
│   ├── step5_generate_outline.py    # LLM生成L2大纲
│   ├── step6_enrich_slices.py       # 文档增强+切片
│   ├── step7_vector_store.py        # 向量存储
│   ├── retriever.py                 # 混合检索器
│   └── run_all.py                   # 一键运行
└── output/
    ├── 01_chapters/
    ├── 02_sequences/
    ├── 03_drafts/
    ├── 04_blocks/
    ├── 05_outline/
    ├── 06_slices/
    └── 07_vector_db/
```

## 关键特性

### 断点续传

所有LLM调用步骤都支持：

```python
# Step 3: 检查已完成的草稿
if draft_file.exists():
    continue

# Step 5: 检查已完成的outline
if outline_file.exists():
    load_and_continue()

# Step 6: 检查进度文件
progress_file = output_dir / ".progress.json"
```

### 进度显示

Step 6 带进度条：

```
[█████████████████████████░░░░░] 24/28 政治博弈与强制休假 ✓
```

### 超时重试

```python
for attempt in range(max_retries):
    try:
        response = llm.invoke(prompt)
        return parse_response(response)
    except:
        if attempt < max_retries - 1:
            time.sleep(2)
```

## 切换本地Embedding

```python
retriever = create_retriever(
    vector_db_path=Path('output/07_vector_db'),
    embedding_type='local',
    model_path='~/下载/llama-b8580/qwen3-embedding-4b-q4_k.gguf'
)
```

## 参考文档

- [笔记6.md](../笔记6.md) - 混合检索方案设计
- [笔记7.md](../笔记7.md) - 实现文档
- [WORK_STATE.md](WORK_STATE.md) - 工作状态

---

更新时间：2026-03-30
状态：实现完成，测试通过