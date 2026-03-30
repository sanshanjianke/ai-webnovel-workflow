# 工作状态保存 - 2026-03-30

## 当前任务

构建分层大纲提取器，将原始小说转换为L2格式大纲。

## 已完成工作

### 1. 代码结构重构
将600行的单文件类拆分为5个独立脚本：
- `steps/step1_split_chapters.py` - 章节切片
- `steps/step2_create_sequences.py` - 序列分组（每7章一组）
- `steps/step3_generate_drafts.py` - LLM生成草稿（并行版，可配置并发数）
- `steps/step4_merge_blocks.py` - 按50KB切分成块
- `steps/step5_generate_outline.py` - LLM生成L2大纲

### 2. 关键修复
- Step 3: 添加并行处理（默认5并发，可配置）、超时重试机制
- Step 4: 修复中文字符/字节计算问题；移除章节标题
- Step 5: 串行处理保持上下文；断点续传；提示词优化要求plot≥300字
- Step 6: 多维度切片（剧情/人物/爽点/功能）+ 文档增强
- Step 7: 向量存储（text-embedding-v3, 1024维）

### 3. 测试结果（300章都市剑说）
| 步骤 | 输入 | 输出 | 耗时 |
|------|------|------|------|
| Step 1 | 小说文件 | 300章 | <1秒 |
| Step 2 | 300章 | 43序列 | <1秒 |
| Step 3 | 43序列 | 43草稿(101KB) | 17分钟(10并发) |
| Step 4 | 43草稿 | 6块(每块~50KB) | <1秒 |
| Step 5 | 6块 | 40序列+91人物 | ~7分钟 |
| Step 6 | L2大纲 | 258切片+文档增强 | ~7分钟 |
| Step 7 | 切片 | 向量库3.5MB | ~1分钟 |

文档增强：每个序列5个视角（情节/爽点/人物关系/情感弧线/读者问题）
检索效果："郑屠"正确命中seq_001（得分0.614）

### 4. L2输出格式（符合笔记6.md）
```json
{
  "characters": [
    {"name": "李白", "desc": "主角，从大武朝穿越归来"}
  ],
  "sequences": [{
    "name": "拍卖会打脸",
    "functions": ["铺垫", "转折"],
    "emotion": "压抑→爆发→余韵",
    "appeal_types": ["打脸", "装逼"],
    "characters": ["李白", "姚兵"],
    "plot": "详细剧情描述..."
  }]
}
```

## 环境配置

### API配置
- Base URL: `https://coding.dashscope.aliyuncs.com/v1`
- API Key: `your-api-key`（从环境变量获取）
- Model: `glm-5`
- 超时: 150-180秒（GLM5很慢，单次请求约67秒）

### Python环境
- 路径: `/home/ssjk/talk/hybrid_rag_prototype/venv/`
- 使用: `./venv/bin/python`

### Git状态
- 本地领先远程 8 个提交
- 最新提交: `81c1072 Fix step5: correct L2 output format with sequences`

## 文件位置

### 代码
- 主目录: `/home/ssjk/talk/hybrid_rag_prototype/`
- 步骤脚本: `hybrid_rag_prototype/steps/`

### 数据
- 小说文件: `/home/ssjk/talk/都市剑说.txt`, `/home/ssjk/talk/1627崛起南海.txt`
- 测试输出: `hybrid_rag_prototype/test_output/`

### 文档
- 笔记6.md: `/home/ssjk/talk/笔记6.md`（混合检索方案设计）

## 用法示例

```bash
cd /home/ssjk/talk/hybrid_rag_prototype

# 单独运行每一步
./venv/bin/python steps/step1_split_chapters.py /home/ssjk/talk/都市剑说.txt --output output/01_chapters --max 300
./venv/bin/python steps/step2_create_sequences.py --input output/01_chapters --output output/02_sequences --size 7
./venv/bin/python steps/step3_generate_drafts.py --input output/02_sequences --output output/03_drafts --workers 10 --timeout 180
./venv/bin/python steps/step4_merge_blocks.py --input output/03_drafts --output output/04_blocks --size 50
./venv/bin/python steps/step5_generate_outline.py --input output/04_blocks --output output/05_outline --name "都市剑说"
```

## 下一步计划

1. 根据笔记6.md，将L2输出进行多维度切片（剧情/人物/爽点/功能维度）
2. 构建双库存储（向量数据库 + MD文本库）
3. 实现知识库检索专家Agent
4. 与L2专家会议流程集成

## 注意事项

1. GLM5很慢，每次请求约60-70秒，timeout设置150秒以上
2. 并发数建议5-10个，太高可能触发API限制
3. 中文字符UTF-8编码约3字节，切分时要注意
4. step3支持断点续传，已完成的草稿会跳过