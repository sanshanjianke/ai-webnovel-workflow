# 论文参考文献提取与下载报告

**报告时间：** 2026-04-30  
**数据来源：** /home/ssjk/talk/papers/ 目录中的7篇核心论文

---

## 一、已阅读的论文

| # | 论文标题 | 来源 | arXiv编号 | 状态 |
|---|---------|------|-----------|------|
| 1 | NarrativeLoom: Multi-Persona Collaborative Storytelling | CHI 2026 | arXiv:2603.07155 | 已读 |
| 2 | StorySage: Conversational Autobiography Writing | Stanford | arXiv:2506.14159 | 已读 |
| 3 | StoryScope: Investigating Idiosyncrasies in AI Fiction | Google DeepMind | arXiv:2604.03136 | 已读 |
| 4 | Spoiler Alert: Narrative Forecasting as a Metric for Tension | McGill | arXiv:2604.09854 | 已读 |
| 5 | ConStory-Bench: Consistency Bugs in Long Story Generation | Microsoft | arXiv:2603.05890 | 已读 |
| 6 | PlayWrite: Multimodal Narrative Co-Authoring in XR | CHI 2026 | arXiv:2603.02366 | 已读 |
| 7 | Narrative Theory-Driven LLM Methods (Survey) | UNSW | arXiv:2602.15851 | 已读(中文版) |

---

## 二、已下载的ArXiv论文

已下载 **6篇** 关键arXiv论文，总计约 **14MB**：

| 文件名 | 论文标题 | 大小 | 重要性 |
|--------|---------|------|--------|
| narrabench.pdf | NarraBench: Narrative Benchmarking | 603KB | ★★★★★ |
| chiron.pdf | CHIRON: Rich Character Representations | 841KB | ★★★★★ |
| evaluating_creative_story.pdf | Evaluating Creative Story Generation | 1.7MB | ★★★★★ |
| kimi_k2.pdf | Kimi K2: Open Agentic Intelligence | 5.9MB | ★★★★☆ |
| longwriter_zero.pdf | LongWriter-Zero: Ultra-Long Generation | 4.4MB | ★★★★☆ |
| llm_uncertainty.pdf | LLM Uncertainty in Creative Writing | 399KB | ★★★★☆ |

**存放位置：** `/home/ssjk/talk/arxiv_papers/`

---

## 三、参考文献清单

### ArXiv/开放获取论文清单
📄 **文件：** `to_download_arxiv.md`

包含 **8大类、60+篇** arXiv论文的下载列表：
1. 叙事理论与计算叙事学基础
2. AI写作与创造力
3. 多智能体系统
4. 叙事张力与结构
5. 人机协作创作
6. LLM能力与局限性
7. 长篇叙事生成
8. 心理学与认知科学

**附：** 批量下载命令示例

---

### 实体出版论文清单
📄 **文件：** `to_acquire_published.md`

包含 **8大类、60+篇** 需要后续获取的论文/书籍：
1. 叙事学经典理论（Genette, Chatman, Propp等）
2. 叙事张力与读者反应理论
3. 创造力理论（Boden, Torrance等）
4. HCI与人机协作（CHI论文）
5. NLP与计算语言学（ACL/EMNLP）
6. 游戏与互动叙事
7. 心理学与记忆
8. 文化研究与媒体

**获取优先级：**
- ★★★★★ 必读（10篇）
- ★★★★☆ 重要（10篇）
- ★★★☆☆ 补充（40+篇）

---

## 四、核心发现

### 1. 叙事学理论框架

从论文中提取的关键理论框架：

| 理论 | 来源 | 在本项目中的应用 |
|------|------|-----------------|
| **Fabula/Story vs Discourse** | Genette (1980), Chatman (1980) | L2架构层与L3叙事层分离 |
| **Blind Variation and Selective Retention** | Campbell (1960) | NarrativeLoom的核心机制 |
| **Narrative Tension** | Baroni (2007), Sternberg (2003) | Spoiler Alert的100-Endings指标 |
| **Narrative Consistency** | Propp (1968) | ConStory-Bench的错误分类 |
| **Embodied Cognition** | Huizinga (1938), Sicart (2014) | PlayWrite的设计基础 |

### 2. 关键研究趋势

1. **多智能体协作：** 从单一模型转向专业化智能体协作（StorySage的5个智能体）
2. **叙事层次分离：** Fabla/Story与Discourse/Narration的明确区分
3. **结构约束优于自由生成：** 厚中间层（thick intermediate plan）优于零样本生成
4. **评估指标创新：** 从BLEU到张力指标（100-Endings）再到一致性检查

### 3. 与本项目的关联

| 论文 | 本项目借鉴点 |
|------|-------------|
| NarrativeLoom | 多专家协作机制、BVSR理论应用 |
| StorySage | 多智能体架构、记忆银行设计 |
| StoryScope | 叙事特征提取、AI文本检测 |
| Spoiler Alert | 100-Endings张力指标、厚中间层规划 |
| ConStory-Bench | 一致性错误分类、五维度评估 |
| PlayWrite | 意图帧（Intent Frame）概念、多模态输入 |
| Narrative Theory Survey | 叙事学系统框架、任务分类 |

---

## 五、下一步建议

### 短期（立即执行）

1. **继续下载ArXiv论文**
   ```bash
   # 从 to_download_arxiv.md 中按优先级批量下载
   cd arxiv_papers
   wget https://arxiv.org/pdf/2410.02603.pdf  # Agents' Room
   wget https://arxiv.org/pdf/2402.17119.pdf  # Suspenseful Stories
   wget https://arxiv.org/pdf/2508.06471.pdf  # GLM-4.5
   ```

2. **阅读核心论文**
   - NarraBench（叙事基准框架）
   - CHIRON（角色表示）
   - Evaluating Creative Story（评估方法）

### 中期（本周内）

3. **获取实体出版论文**
   - 优先通过机构访问获取CHI/ACL论文
   - 购买或借阅叙事学经典（Genette, Chatman, Propp）

4. **整理笔记**
   - 将各论文的关键发现整理到笔记文件
   - 建立与L1-L4技能文档的关联

### 长期（本月内）

5. **构建知识库**
   - 将关键论文的PDF添加到向量数据库
   - 建立论文-概念-技能的三元索引

---

## 六、文件索引

```
papers/
├── README.md                    # 项目说明
├── download_report.md           # 本报告
├── to_download_arxiv.md         # ArXiv论文下载列表
├── to_acquire_published.md      # 实体出版论文列表
│
├── narrativeloom.{pdf,txt}      # CHI 2026
├── storysage.{pdf,txt}          # Stanford
├── storyscope.{pdf,txt}         # Google DeepMind
├── spoiler_alert.{pdf,txt}      # McGill
├── constory_bench.{pdf,txt}     # Microsoft
├── playwrite.{pdf,txt}          # CHI 2026
├── narrative_theory_survey_cn.md # 综述（中文版）
│
└── arxiv_papers/                # 已下载ArXiv论文
    ├── narrabench.pdf
    ├── chiron.pdf
    ├── evaluating_creative_story.pdf
    ├── kimi_k2.pdf
    ├── longwriter_zero.pdf
    └── llm_uncertainty.pdf
```

---

## 七、统计汇总

| 类别 | 数量 | 状态 |
|------|------|------|
| 原始核心论文 | 7篇 | 全部阅读完成 |
| 已下载ArXiv | 6篇 | 约14MB |
| ArXiv待下载 | 50+篇 | 见to_download_arxiv.md |
| 实体出版待获取 | 60+篇 | 见to_acquire_published.md |
| **参考文献总计** | **120+篇** | 分类整理完成 |

---

**报告生成者：** OpenCode  
**任务状态：** ✅ 第一阶段完成 - 参考文献提取与分类
